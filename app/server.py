"""
StockerAI local SaaS Web Server
Dynamically runs stock analyzer pipeline and streams logs in real-time.
"""
import os
import sys
import re
import io
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# Fix Windows encoding issues for standard outputs
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Automatic check and installation of Flask
try:
    from flask import Flask, render_template, request, Response, send_file, redirect
except ImportError:
    logger.info("[*] Flask dependency is missing. Attempting automatic installation...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
        from flask import Flask, render_template, request, Response, send_file, redirect
        logger.info("[+] Flask successfully installed!")
    except Exception as e:
        logger.info(f"[-] Failed to automatically install Flask: {e}")
        logger.info("[-] Please run: pip install flask")
        sys.exit(1)

from flask_cors import CORS

app = Flask(__name__, template_folder="templates")
CORS(app, supports_credentials=True) # Allow credentials for cross-origin requests
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

def is_valid_ticker(ticker):
    return bool(re.match(r"^[A-Z0-9.\^-]{1,10}$", ticker))

def get_cache_size_str():
    """Calculate the total size of the output cached directories."""
    total = 0
    output_dir = Path("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output")
    if output_dir.exists():
        for p in output_dir.glob('**/*'):
            if p.is_file():
                total += p.stat().st_size
    for factor, unit in [(1024**3, "GB"), (1024**2, "MB"), (1024, "KB")]:
        if total >= factor:
            return f"{total/factor:.1f} {unit}"
    return f"{total} B"

def get_recent_stocks():
    """Scan output folder to extract verdict and name of previously analyzed tickers."""
    recent_stocks = []
    output_dir = Path("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output")
    if output_dir.exists():
        for d in output_dir.iterdir():
            if d.is_dir() and d.name.upper() not in ["RAW"]:
                ticker = d.name.upper()
                html_file = d / f"{ticker}_dashboard.html"
                if html_file.exists():
                     try:
                         # Rapid regex parse to find verdict & name without loading whole file
                         with open(html_file, "r", encoding="utf-8") as f:
                             content = f.read(128000) # Read first 128KB
                         
                         verdict_match = re.search(r'"verdict":\s*"([^"]+)"', content)
                         name_match = re.search(r'"company_name":\s*"([^"]+)"', content)
                         
                         verdict = verdict_match.group(1) if verdict_match else "HOLD"
                         name = name_match.group(1) if name_match else f"{ticker} Corp"
                         
                         recent_stocks.append({
                             "ticker": ticker,
                             "name": name,
                             "verdict": verdict
                         })
                     except Exception as e:
                         logger.info(f"Error parsing cache for {ticker}: {e}")
    # Sort alphabetically
    recent_stocks.sort(key=lambda x: x["ticker"])
    return recent_stocks

# home route removed to fix duplicate

@app.route("/api/stream")
def stream_logs():
    """Stream live terminal execution output using SSE (Server-Sent Events)."""
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker or not is_valid_ticker(ticker):
        return Response("data: ❌ Error: Invalid or no ticker provided.\n\n", mimetype="text/event-stream")

    def generate_events():
        from queue import Queue, Empty
        from threading import Thread

        logger.info(f"[*] Starting background analysis pipeline for: {ticker}")
        process = None
        try:
            # Force unbuffered Python stdout
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            # Start stock_analyzer.py as an unbuffered subprocess to stream standard outputs in UTF-8
            analyzer_path = os.path.join(os.path.dirname(__file__), "stock_analyzer.py")
            process = subprocess.Popen(
                [sys.executable, "-u", analyzer_path, ticker],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            q = Queue()
            def enqueue_output(out, queue):
                try:
                    for line in iter(out.readline, ''):
                        queue.put(line)
                except Exception:
                    pass
                finally:
                    out.close()
                    queue.put(None)  # EOF Sentinel

            t = Thread(target=enqueue_output, args=(process.stdout, q))
            t.daemon = True
            t.start()
            
            while True:
                try:
                    # Non-blocking get with a timeout of 1.0 second
                    line = q.get(timeout=1.0)
                    if line is None:  # EOF sentinel reached
                        break
                    
                    cleaned = line.rstrip('\n')
                    # Yield stdout line to the client
                    yield f"data: {cleaned}\n\n"
                except Empty:
                    # Subprocess is still executing, but stdout queue is empty.
                    # Yield keep-alive heartbeat comment pulse to keep HTTP connection alive
                    yield ": keepalive\n\n"
                    # Also double check if process died unexpectedly
                    if process.poll() is not None and q.empty():
                        break
                        
            return_code = process.wait()
            
            if return_code == 0:
                yield f"data: REDIRECT: /dashboard/{ticker}\n\n"
            else:
                yield f"data: ❌ Subprocess analysis crashed with exit code {return_code}\n\n"
        except GeneratorExit:
            logger.info(f"[-] Client disconnected while analyzing {ticker}. Terminating background subprocess...")
            if process and process.poll() is None:
                process.terminate()
                process.wait()
            raise
        except Exception as e:
            logger.info(f"[-] Error in event stream: {e}")
            yield f"data: ❌ Server error: {str(e)}\n\n"
            if process and process.poll() is None:
                process.terminate()
                process.wait()

    return Response(generate_events(), mimetype="text/event-stream")

@app.route("/api/stocks")
def get_stocks():
    """Scan output/database/ for analyzed stocks and return basic info for catalog."""
    import glob
    import json
    db_dir = os.path.join("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output", "database")
    if not os.path.exists(db_dir):
        return {"stocks": []}
    
    stocks = []
    for fpath in glob.glob(os.path.join(db_dir, "*.json")):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            ticker = data.get("ticker", "").upper()
            comp_name = data.get("company_name", "N/A")
            metrics = data.get("key_metrics", {})
            dcf_data = data.get("dcf_data", {})
            scores = data.get("financial_scores", {})
            analysis = data.get("analysis", {})
            
            curr_price = metrics.get("current_price") or metrics.get("currentPrice") or 0.0
            fair_mid = (analysis.get("valuation_assessment") or {}).get("fair_value_mid") or dcf_data.get("implied_price") or 0.0
            upside = ((fair_mid - curr_price) / curr_price) if curr_price > 0 else 0.0
            
            stocks.append({
                "ticker": ticker,
                "company_name": comp_name,
                "sector": metrics.get("sector", "N/A"),
                "verdict": analysis.get("verdict", "HOLD"),
                "current_price": curr_price,
                "fair_value_mid": fair_mid,
                "upside": upside,
                "altman_z": scores.get("altman_z", "N/A"),
                "altman_z_label": scores.get("altman_z_label", "Safe"),
                "piotroski_f": scores.get("piotroski_f", "N/A"),
                "beneish_m": scores.get("beneish_m", "N/A"),
                "totalCash": metrics.get("totalCash", 0),
                "totalDebt": metrics.get("totalDebt", 0),
                "bookValue": metrics.get("bookValue", 0),
                "debtToEquity": metrics.get("debtToEquity", 0),
                "currentRatio": metrics.get("currentRatio", 0),
                "quickRatio": metrics.get("quickRatio", 0),
                "marketCap": metrics.get("marketCap", 0),
                "freeCashflow": metrics.get("freeCashflow", 0),
                "totalRevenue": metrics.get("totalRevenue", 0),
                "returnOnEquity": metrics.get("returnOnEquity", 0),
                "returnOnAssets": metrics.get("returnOnAssets", 0),
                "confidence": analysis.get("verdict_confidence", "N/A"),
                "generated_at": data.get("generated_at", "")
            })
        except Exception as e:
            logger.info(f"Error parsing database file {fpath}: {e}")
            
    stocks.sort(key=lambda x: x["ticker"])
    return {"stocks": stocks}

@app.route("/api/stock/<ticker>")
def get_stock(ticker):
    """Retrieve detailed qualitative and quantitative JSON record for a ticker."""
    import json
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    db_path = os.path.join("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output", "database", f"{ticker}.json")
    if not os.path.exists(db_path):
        return {"error": f"Ticker {ticker} not found in local database"}, 404
        
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        return {"error": f"Failed to read database: {str(e)}"}, 500

@app.route("/api/stock/<ticker>/recalculate", methods=["POST"])
def recalculate_stock(ticker):
    """Recalculate dynamic DCF model inside JSON database and Excel file on disk."""
    import json
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    db_path = os.path.join("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output", "database", f"{ticker}.json")
    if not os.path.exists(db_path):
        return {"error": f"Ticker {ticker} not found in database"}, 404
        
    try:
        req_data = request.get_json() or {}
        
        # Extract inputs and validate
        wacc = float(req_data.get("wacc", 9.0)) / 100.0
        growth_1_5 = float(req_data.get("growth_1_5", 15.0)) / 100.0
        growth_6_10 = float(req_data.get("growth_6_10", 10.0)) / 100.0
        terminal_growth = float(req_data.get("terminal_growth", 2.5)) / 100.0
        
        # Load database file
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        metrics = data.get("key_metrics", {})
        dcf_data = data.get("dcf_data", {})
        
        fcf_base = float(dcf_data.get("fcf_base") or metrics.get("freeCashflow") or 0)
        total_cash = float(metrics.get("totalCash") or 0)
        total_debt = float(metrics.get("totalDebt") or 0)
        
        shares_out = metrics.get("sharesOutstanding")
        if not shares_out or shares_out <= 1:
            mc = metrics.get("marketCap")
            cp = metrics.get("current_price") or metrics.get("currentPrice") or 1.0
            if mc and cp:
                shares_out = float(mc / cp)
            else:
                shares_out = 1.0
        else:
            shares_out = float(shares_out)
            
        curr_price = float(metrics.get("current_price") or 0)
        
        # Projections
        npv = 0
        current_fcf = fcf_base
        for i in range(1, 11):
            gr = growth_1_5 if i <= 5 else growth_6_10
            current_fcf *= (gr + 1.0)  # Correct multiplication syntax
            pv = current_fcf / ((1 + wacc) ** i)
            npv += pv
            
        terminal_value = (current_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
        terminal_pv = terminal_value / ((1 + wacc) ** 10)
        
        enterprise_value = npv + terminal_pv
        net_debt = total_debt - total_cash
        equity_value = enterprise_value - net_debt
        implied_price = equity_value / shares_out
        
        # Update DCF results
        dcf_data["implied_price"] = round(implied_price, 2)
        dcf_data["wacc_used"] = round(wacc * 100, 2)
        dcf_data["terminal_growth"] = round(terminal_growth * 100, 2)
        dcf_data["growth_1_5_used"] = round(growth_1_5 * 100, 2)
        dcf_data["growth_6_10_used"] = round(growth_6_10 * 100, 2)
        dcf_data["valuation_basis"] = "Interactive Live Recalculation"
        
        data["dcf_data"] = dcf_data
        
        # Recheck weighted valuation coherence
        from ai_engine import _enforce_valuation_coherence
        data["analysis"] = _enforce_valuation_coherence(data["analysis"], data)
        
        # Save back to database
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        # Re-generate Excel file dynamically
        from excel_generator import generate_excel_model
        from pathlib import Path
        ticker_dir = Path("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output") / ticker
        generate_excel_model(ticker, data, ticker_dir, data["analysis"])
        
        logger.info(f"  [+] Recalculated DCF and refreshed Excel Model for {ticker}.")
        return data
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Recalculation failed: {str(e)}"}, 500

@app.route("/dashboard/<ticker>")
def serve_dashboard(ticker):
    """Serve the single master dynamic client dashboard template."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return "Invalid ticker format", 400
    db_path = os.path.join("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output", "database", f"{ticker}.json")
    if os.path.exists(db_path):
        return render_template("dashboard.html", ticker=ticker)
    return f"Database record for {ticker} not found. Try running a new analysis first.", 404

@app.route("/guide")
def serve_guide():
    """Serve the complete A to Z Institutional Quantitative Reference Guide."""
    return render_template("guide.html")

@app.route("/excel/<ticker>")
def download_excel(ticker):
    """Download the dynamic Excel financial model of a ticker."""
    ticker = ticker.upper().strip()
    path = os.path.join("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output", ticker, f"{ticker}_Financial_Model.xlsx")
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=f"{ticker}_Financial_Model.xlsx")
    return f"Excel model for {ticker} not found.", 404

@app.route("/json/<ticker>")
def download_json(ticker):
    """Download the raw JSON database record of a ticker."""
    ticker = ticker.upper().strip()
    path = os.path.join("C:\\Users\\Abdelli\\Desktop\\Projects\\STOCK_TERMINAL_ALONE\\output", "database", f"{ticker}.json")
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=f"{ticker}_Raw_Data.json")
    return f"JSON record for {ticker} not found.", 404

@app.route("/api/notion/sync/<ticker>", methods=["POST"])
def sync_notion(ticker):
    """Trigger a Notion workspace sync for a ticker."""
    ticker = ticker.upper().strip()
    try:
        from notion_integrator import auto_generate_notion_page
        result_id = auto_generate_notion_page(ticker)
        if result_id:
            return {"status": "success", "notion_id": result_id}
        else:
            return {"error": "Notion sync failed. Check credentials."}, 500
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/api/news/stock/<ticker>")
def get_stock_news(ticker):
    """Fetch live ticker-specific news."""
    ticker = ticker.upper().strip()
    import yfinance as yf
    try:
        raw_news = yf.Ticker(ticker).news
        news = []
        for n in raw_news:
            if "content" in n:
                c = n["content"]
                news.append({
                    "title": c.get("title", "News"),
                    "link": c.get("clickThroughUrl", {}).get("url", "#"),
                    "publisher": c.get("provider", {}).get("displayName", "Wire"),
                    "pubDate": c.get("pubDate", "")
                })
        return {"status": "success", "news": news[:15]}
    except Exception as e:
        return {"error": str(e)}, 500




ticker_tape_cache = {"data": None, "timestamp": 0}

def get_ticker_tape():
    import time
    import yfinance as yf
    
    if ticker_tape_cache["data"] and time.time() - ticker_tape_cache["timestamp"] < 300:
        return ticker_tape_cache["data"]
        
    tickers = {
        "S&P 500": "^GSPC",
        "NASDAQ 100": "^NDX",
        "DOW JONES": "^DJI",
        "CBOE VIX": "^VIX",
        "US 10-YR YIELD": "^TNX",
        "BTC/USD": "BTC-USD"
    }
    
    tape_data = []
    try:
        tickers_str = " ".join(tickers.values())
        data = yf.Tickers(tickers_str)
        for label, symbol in tickers.items():
            try:
                hist = data.tickers[symbol].history(period="5d")
                if len(hist) >= 2:
                    current = float(hist['Close'].iloc[-1])
                    prev = float(hist['Close'].iloc[-2])
                    change = current - prev
                    pct_change = (change / prev) * 100
                    
                    if symbol == "^TNX":
                        tape_data.append({"label": label, "val": f"{current:.3f}%", "pct": change, "is_yield": True})
                    else:
                        tape_data.append({"label": label, "val": f"{current:,.2f}", "pct": pct_change, "is_yield": False})
                else:
                    tape_data.append({"label": label, "val": "N/A", "pct": 0, "is_yield": False})
            except:
                tape_data.append({"label": label, "val": "N/A", "pct": 0, "is_yield": False})
                
        ticker_tape_cache["data"] = tape_data
        ticker_tape_cache["timestamp"] = time.time()
        return tape_data
    except Exception as e:
        logger.info(f"Failed to fetch ticker tape: {e}")
        return []

@app.route("/")
def stocks_terminal():
    """Stock Analysis Terminal — Execution Hub."""
    recent = get_recent_stocks()
    cache_size = get_cache_size_str()
    tape_data = get_ticker_tape()
    return render_template(
        "index.html",
        recent_stocks=recent,
        RECENT_COUNT=len(recent),
        CACHE_SIZE=cache_size,
        tape_data=tape_data
    )




@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

def run_server(port=5001):
    """Start the local web server."""
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info(f"\n=======================================================")
    logger.info(f"   StockerAI Standalone Classic Terminal")
    logger.info(f"   Starting server on http://127.0.0.1:{port}")
    logger.info(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

if __name__ == "__main__":
    run_server()
