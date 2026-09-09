"""
StockerAI Personal Stock Terminal — Local Only
Single-user Flask server. No auth, no billing, no premium gates.
Dynamically runs stock analyzer pipeline and streams logs in real-time.
"""
import os
import sys
import re
import io
import json
import math
import subprocess
import logging
from pathlib import Path

app_dir = str(Path(__file__).parent.resolve())
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

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
try:
    from config import OUTPUT_DIR
except ImportError:
    from .config import OUTPUT_DIR
import local_db

if os.environ.get("STOCKER_TEST_MODE") == "1":
    try:
        import data_fetcher
    except ImportError:
        from app import data_fetcher


app = Flask(__name__, template_folder="templates")
CORS(app, supports_credentials=False, resources={r"/api/*": {"origins": ["http://127.0.0.1:*", "http://localhost:*", "http://127.0.0.1:5001", "http://localhost:5001"]}})  # local-only, no credentials
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
OUTPUT_ROOT = Path(OUTPUT_DIR)
DB_DIR = OUTPUT_ROOT / "database"
# Persistent secret for personal single-user use — stable across restarts
_secret_path = OUTPUT_ROOT / ".flask_secret"
if os.environ.get('FLASK_SECRET_KEY'):
    app.secret_key = os.environ['FLASK_SECRET_KEY']
elif _secret_path.exists():
    try:
        app.secret_key = _secret_path.read_bytes()
    except Exception:
        app.secret_key = os.urandom(24)
else:
    _secret = os.urandom(32)
    try:
        _secret_path.parent.mkdir(parents=True, exist_ok=True)
        _secret_path.write_bytes(_secret)
    except Exception:
        pass
    app.secret_key = _secret
ALLOWED_PERIODS = {"1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max"}
MODULES = {"screener"}
VERDICT_BUCKETS = {
    "BUY": {"BUY", "STRONG BUY", "ACCUMULATE", "OUTPERFORM"},
    "HOLD": {"HOLD", "NEUTRAL", "UNDER_REVIEW", "WATCH"},
    "SELL": {"SELL", "STRONG SELL", "REDUCE", "AVOID", "UNDERPERFORM"},
}

def is_valid_ticker(ticker):
    if not isinstance(ticker, str):
        return False
    ticker = ticker.strip().upper()
    # Block path traversal / injection; allow A-Z,0-9,.,-,^ (BRK.B, BRK^A) length 1-12
    return bool(re.match(r"^[A-Z0-9.\-\^]{1,12}$", ticker)) and ".." not in ticker and not ticker.startswith((".", "-"))

def _safe_float(value, default=None):
    try:
        if value in [None, "", "N/A", "NA", "null"]:
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default

def _read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.info(f"Failed to read JSON {path}: {e}")
        return None

def _db_path(ticker):
    return local_db.DB_DIR / f"{ticker.upper()}.json"

def _load_stock_record(ticker):
    if not is_valid_ticker(ticker):
        return None
    return local_db.load_stock_record(ticker)

def _calc_upside_from_record(data):
    metrics = data.get("key_metrics", {})
    analysis = data.get("analysis", {})
    dcf_data = data.get("dcf_data", {})
    price = _safe_float(metrics.get("current_price") or metrics.get("currentPrice"), 0)
    fair = _safe_float((analysis.get("valuation_assessment") or {}).get("fair_value_mid") or dcf_data.get("implied_price"), 0)
    return ((fair - price) / price) if price else 0

def _catalog_rows():
    return local_db.catalog_rows()

def _verdict_matches(actual, expected):
    if not expected:
        return True
    actual = (actual or "").upper().strip()
    expected = expected.upper().strip()
    return actual == expected or actual in VERDICT_BUCKETS.get(expected, set())

def _num_token(text):
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([kmbt%]?)", text.lower())
    if not match:
        return None
    value = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        value *= 1e3
    elif suffix == "m":
        value *= 1e6
    elif suffix == "b":
        value *= 1e9
    elif suffix == "t":
        value *= 1e12
    elif suffix == "%":
        value /= 100
    return value

def _normalize_criteria(criteria):
    clean = {}
    if not isinstance(criteria, dict):
        return clean
    for key in ["sector", "industry", "verdict"]:
        value = str(criteria.get(key) or "").strip()
        if value:
            clean[key] = value
    for key in ["min_pe", "max_pe", "min_market_cap", "max_market_cap", "min_upside", "max_upside", "min_roe", "max_roa", "min_revenue_growth", "min_operating_margin", "min_current_ratio", "max_debt_to_equity", "min_piotroski"]:
        value = _safe_float(criteria.get(key), None)
        if value is not None:
            clean[key] = value
    return clean

def _parse_screener_query(query):
    q = query.lower()
    criteria = {}
    sector_aliases = {
        "technology": ["technology", "tech", "software", "semiconductor"],
        "healthcare": ["healthcare", "health", "medical", "pharma"],
        "financials": ["financial", "bank", "insurance"],
        "energy": ["energy", "oil", "gas"],
        "industrials": ["industrial", "aerospace"],
        "consumer cyclical": ["consumer cyclical", "retail", "auto"],
        "utilities": ["utility", "utilities"],
        "real estate": ["real estate", "reit"],
    }
    for sector, words in sector_aliases.items():
        if any(word in q for word in words):
            criteria["sector"] = sector.title()
            break
    if "strong buy" in q or re.search(r"\bbuy\b", q):
        criteria["verdict"] = "BUY"
    elif "sell" in q or "avoid" in q:
        criteria["verdict"] = "SELL"
    elif "hold" in q or "neutral" in q:
        criteria["verdict"] = "HOLD"
    for key, patterns in {
        "max_pe": [r"p/?e\s*(?:under|below|<|less than)\s*[\d.]+", r"pe\s*(?:under|below|<|less than)\s*[\d.]+"],
        "min_pe": [r"p/?e\s*(?:over|above|>|greater than)\s*[\d.]+", r"pe\s*(?:over|above|>|greater than)\s*[\d.]+"],
        "min_upside": [r"(?:upside|return)\s*(?:over|above|>|greater than|at least)\s*[\d.]+%?"],
        "min_roe": [r"(?:roe|return on equity)\s*(?:over|above|>|greater than|at least)\s*[\d.]+%?"],
        "max_debt_to_equity": [r"(?:debt.?to.?equity|d/e)\s*(?:under|below|<|less than)\s*[\d.]+%?"],
        "min_market_cap": [r"(?:market cap|mcap)\s*(?:over|above|>|greater than|at least)\s*[\d.]+\s*[kmbt]?"],
    }.items():
        for pattern in patterns:
            m = re.search(pattern, q)
            if m:
                value = _num_token(m.group(0))
                if value is not None:
                    if key in {"min_upside", "min_roe"} and value > 1:
                        value /= 100
                    criteria[key] = value
                break
    if "undervalued" in q or "cheap" in q:
        criteria.setdefault("min_upside", 0.15)
    if "quality" in q:
        criteria.setdefault("min_piotroski", 6)
    return _normalize_criteria(criteria)

def _stock_matches_criteria(stock, criteria):
    if criteria.get("sector") and criteria["sector"].lower() not in (stock.get("sector") or "").lower():
        return False
    if criteria.get("industry") and criteria["industry"].lower() not in (stock.get("industry") or "").lower():
        return False
    if criteria.get("verdict") and not _verdict_matches(stock.get("verdict"), criteria["verdict"]):
        return False
    checks = [
        ("pe_ratio", "min_pe", "max_pe"),
        ("marketCap", "min_market_cap", "max_market_cap"),
        ("upside", "min_upside", "max_upside"),
        ("returnOnEquity", "min_roe", None),
        ("returnOnAssets", "min_roa", None),
        ("revenueGrowth", "min_revenue_growth", None),
        ("operatingMargins", "min_operating_margin", None),
        ("currentRatio", "min_current_ratio", None),
        ("debtToEquity", None, "max_debt_to_equity"),
        ("piotroski_f", "min_piotroski", None),
    ]
    for field, min_key, max_key in checks:
        value = _safe_float(stock.get(field), None)
        if min_key in criteria and (value is None or value < criteria[min_key]):
            return False
        if max_key in criteria and (value is None or value > criteria[max_key]):
            return False
    return True

def _filter_catalog(criteria):
    criteria = _normalize_criteria(criteria)
    return [row for row in _catalog_rows() if _stock_matches_criteria(row, criteria)]

_cache_size_cache = {"value": None, "ts": 0}
def get_cache_size_str():
    """Calculate the total size of the output cached directories (memoized 60s)."""
    import time
    now = time.time()
    if _cache_size_cache["value"] is not None and now - _cache_size_cache["ts"] < 60:
        return _cache_size_cache["value"]
    total = 0
    if OUTPUT_ROOT.exists():
        try:
            for p in OUTPUT_ROOT.rglob("*"):
                try:
                    if p.is_file():
                        total += p.stat().st_size
                except Exception:
                    continue
        except Exception:
            pass
    for factor, unit in [(1024**3, "GB"), (1024**2, "MB"), (1024, "KB")]:
        if total >= factor:
            val = f"{total/factor:.1f} {unit}"
            _cache_size_cache["value"] = val
            _cache_size_cache["ts"] = now
            return val
    val = f"{total} B"
    _cache_size_cache["value"] = val
    _cache_size_cache["ts"] = now
    return val

def get_recent_stocks():
    """Scan output folder to extract verdict and name of previously analyzed tickers."""
    return [
        {"ticker": row["ticker"], "name": row["company_name"], "verdict": row["verdict"]}
        for row in _catalog_rows()
    ]

# home route removed to fix duplicate

@app.route("/api/stream")
def stream_logs():
    """Stream live terminal execution output using SSE (Server-Sent Events)."""
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker or not is_valid_ticker(ticker):
        return Response("data: ❌ Error: Invalid or no ticker provided.\n\n", mimetype="text/event-stream")
    # TEST_MODE: mock stream to avoid spawning analyzer + yfinance network (prevents pytest hangs)
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        def _mock_stream():
            yield f"data: [TEST_MODE] Mock analysis for {ticker}\n\n"
            # RATELIMIT sentinel triggers 429-like branch in tests
            if ticker == "RATELIMIT":
                yield "data: 429 rate limited (mock)\n\n"
            elif ticker == "MISSING":
                yield f"data: Ticker {ticker} not found (mock)\n\n"
            else:
                yield f"data: Analysis complete for {ticker} (mock)\n\n"
            yield f"data: REDIRECT: /dashboard/{ticker}\n\n"
        return Response(_mock_stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

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

    return Response(generate_events(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

@app.route("/api/stocks")
def get_stocks():
    """Scan output/database/ for analyzed stocks and return basic info for catalog."""
    try:
        return {"stocks": _catalog_rows()}
    except Exception as e:
        logger.exception(f"/api/stocks failed: {e}")
        return {"stocks": [], "error": str(e)}, 500


@app.route("/api/screener/filter")
def screener_filter():
    """Apply traditional filter criteria against the stocks catalog."""
    try:
        criteria = _normalize_criteria(request.args.to_dict())
        return {"stocks": _filter_catalog(criteria), "criteria": criteria}
    except Exception as e:
        logger.exception(f"/api/screener/filter failed: {e}")
        return {"stocks": [], "criteria": {}, "error": str(e)}, 500


@app.route("/api/screener/ai", methods=["POST"])
def screener_ai():
    """Use AI to parse a natural language query and filter the stocks catalog."""
    req_data = request.get_json() or {}
    q = req_data.get("query", "").strip()
    if not q:
        return {"error": "Empty query"}, 400

    filter_criteria = {}
    messages = [
        {"role": "system", "content": 'Convert a stock screener request into JSON only. Allowed fields: sector, industry, verdict, min_pe, max_pe, min_upside, max_upside, min_market_cap, max_market_cap, min_roe, max_debt_to_equity, min_piotroski. Percent values must be decimals, so 20% is 0.20. Verdict is BUY, HOLD, or SELL. Do not invent unsupported fields.'},
        {"role": "user", "content": q}
    ]
    try:
        from ai_engine import _call_llm
        filter_criteria = _call_llm(messages, max_tokens=500, temperature=0.0, route="easy") or {}
    except Exception as e:
        logger.info(f"Screener AI parser failed, using deterministic parser: {e}")

    criteria = _normalize_criteria(filter_criteria) or _parse_screener_query(q)
    return {"stocks": _filter_catalog(criteria), "criteria": criteria}


@app.route("/api/query/search")
def query_search():
    """Search across SEC filings, executive summaries, theses, and descriptions in database JSONs."""
    import glob
    import json
    q = request.args.get("q", "").strip().lower()
    types = request.args.get("types", "") # e.g. "10-K,10-Q"
    ticker_filter = request.args.get("ticker", "").strip().upper()
    
    if not q:
        return {"results": []}
    if len(q) > 200:
        q = q[:200]
    if ticker_filter and not is_valid_ticker(ticker_filter):
        return {"error": "Invalid ticker filter"}, 400
        
    type_list = [t.strip().upper() for t in types.split(",") if t.strip()]

    db_dir = DB_DIR
    if not db_dir.exists():
        return {"results": []}

    results = []
    search_words = q.split()[:10]  # cap words to prevent DoS

    for fpath in db_dir.glob("*.json"):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            ticker = data.get("ticker", "").upper()
            if ticker_filter and ticker != ticker_filter:
                continue
                
            comp_name = data.get("company_name", "N/A")
            metrics = data.get("key_metrics", {})
            analysis = data.get("analysis", {})
            sec_data = data.get("sec_data", {})
            
            # We search several fields and compute a score
            # 1. Company Description
            desc = metrics.get("longBusinessSummary") or data.get("longBusinessSummary") or ""
            # 2. Analysis Text
            exec_sum = analysis.get("executive_summary") or ""
            thesis = analysis.get("investment_thesis") or ""
            bull = analysis.get("bull_case_narrative") or analysis.get("bull_case") or ""
            bear = analysis.get("bear_case_narrative") or analysis.get("bear_case") or ""
            
            # Let's count word frequencies
            score = 0
            
            combined_text = f"{comp_name} {ticker} {desc} {exec_sum} {thesis} {bull} {bear}".lower()
            for w in search_words:
                count = combined_text.count(w)
                if count > 0:
                    score += count * 5
                    
            # 3. SEC Filings
            filings = sec_data.get("recent_filings", [])
            for f in filings:
                form_type = (f.get("form") or "").upper()
                if type_list and form_type not in type_list:
                    continue
                    
                # Search filing fields
                filing_desc = (f.get("primary_document") or "") + " " + (f.get("filing_date") or "")
                filing_score = 0
                for w in search_words:
                    if w in filing_desc.lower():
                        filing_score += 20
                        
                if filing_score > 0:
                    # Found match in specific filing
                    cik = sec_data.get("cik", "")
                    acc = f.get("accession_number", "").replace("-", "")
                    doc = f.get("primary_document", "")
                    link = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}" if cik and acc and doc else "#"
                    
                    results.append({
                        "ticker": ticker,
                        "company": comp_name,
                        "source": "filings",
                        "title": f"{form_type} SEC Filing ({f.get('filing_date')})",
                        "snippet": f"SEC Filing Form {form_type} filed on {f.get('filing_date')}.",
                        "link": link,
                        "date": f.get("filing_date", ""),
                        "score": score + filing_score
                    })
                    
            # If overall text matched but no specific filing, add as AI Analysis result
            if score > 0:
                snippet = exec_sum[:200] + "..." if len(exec_sum) > 200 else exec_sum
                if not snippet or snippet == "...":
                    snippet = desc[:200] + "..." if len(desc) > 200 else desc
                    
                results.append({
                    "ticker": ticker,
                    "company": comp_name,
                    "source": "transcripts" if "transcript" in q else "presentations",
                    "title": f"AI Investment Report - {comp_name}",
                    "snippet": snippet,
                    "link": f"/dashboard/{ticker}",
                    "date": data.get("generated_at", "").split("T")[0] if "T" in data.get("generated_at", "") else data.get("generated_at", ""),
                    "score": score
                })
        except Exception as e:
            logger.info(f"Error searching {fpath}: {e}")
            
    # Sort results by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:25]}


@app.route("/module/<module_name>")
def serve_module(module_name):
    module_name = module_name.lower().strip()
    if module_name not in MODULES:
        return {"error": "Unknown module"}, 404
    return render_template(f"modules/{module_name}.html")


@app.route("/watchlist")
@app.route("/reports")
@app.route("/market-feed")
@app.route("/system")
def serve_pro_page():
    page = request.path.strip("/") or "watchlist"
    titles = {
        "watchlist": ("WATCHLIST", "Live local coverage list"),
        "reports": ("REPORTS", "Generated model files"),
        "market-feed": ("MARKET FEED", "Macro tape and catalog pulse"),
        "system": ("SYSTEM", "Cache, API, and runtime health"),
    }
    title, eyebrow = titles.get(page, ("TERMINAL", "Command center"))
    if page == "watchlist":
        return render_template("watchlist.html")
    return render_template("pro_page.html", page=page, title=title, eyebrow=eyebrow, cache_size=get_cache_size_str())

@app.route("/earnings")
def serve_earnings():
    return render_template("earnings.html")


@app.route("/news-impact")
@app.route("/filings")
@app.route("/scenario-lab")
@app.route("/committee")
@app.route("/red-flags")
@app.route("/portfolio")
def serve_intel_page():
    page = request.path.strip("/") or "news-impact"
    titles = {
        "news-impact": ("NEWS IMPACT", "AI-ranked catalyst readout"),
        "filings": ("SEC FILINGS", "EDGAR metadata watch"),
        "scenario-lab": ("SCENARIO LAB", "Bull/base/bear valuation cases"),
        "committee": ("INVESTMENT COMMITTEE", "Buy-side debate memo"),
        "red-flags": ("RED FLAGS", "Forensic risk scan"),
        "portfolio": ("PORTFOLIO", "Position risk command center"),
    }
    title, eyebrow = titles.get(page, ("INTEL", "AI terminal"))
    if page == "portfolio":
        return render_template("portfolio.html")
    return render_template("intel_page.html", page=page, title=title, eyebrow=eyebrow)


@app.route("/api/intel/news-impact/<ticker>")
def api_news_impact(ticker):
    if not is_valid_ticker(ticker.upper()):
        return {"error": "Invalid ticker"}, 400
    from intelligence_terminal import get_news_impact
    return get_news_impact(ticker)


@app.route("/api/intel/filings/<ticker>")
def api_filings(ticker):
    if not is_valid_ticker(ticker.upper()):
        return {"error": "Invalid ticker"}, 400
    from intelligence_terminal import get_sec_filings
    return get_sec_filings(ticker)


@app.route("/api/intel/scenarios/<ticker>")
def api_scenarios(ticker):
    if not is_valid_ticker(ticker.upper()):
        return {"error": "Invalid ticker"}, 400
    from intelligence_terminal import get_valuation_scenarios
    return get_valuation_scenarios(ticker)


@app.route("/api/intel/committee/<ticker>")
def api_committee(ticker):
    if not is_valid_ticker(ticker.upper()):
        return {"error": "Invalid ticker"}, 400
    from intelligence_terminal import get_investment_committee
    return get_investment_committee(ticker)


@app.route("/api/intel/red-flags/<ticker>")
def api_red_flags(ticker):
    if not is_valid_ticker(ticker.upper()):
        return {"error": "Invalid ticker"}, 400
    from intelligence_terminal import get_red_flags
    return get_red_flags(ticker)


@app.route("/api/portfolio")
def api_portfolio():
    from intelligence_terminal import portfolio_summary
    return portfolio_summary()


@app.route("/api/portfolio/add", methods=["POST"])
def api_portfolio_add():
    from intelligence_terminal import load_portfolio, save_portfolio
    payload = request.get_json() or {}
    ticker = str(payload.get("ticker") or "").upper().strip()
    weight = _safe_float(payload.get("weight"), None)
    if not is_valid_ticker(ticker) or weight is None or weight <= 0:
        return {"error": "Ticker and positive weight are required."}, 400
    weight = min(weight, 100)
    portfolio = load_portfolio()
    positions = [p for p in portfolio.get("positions", []) if (p.get("ticker") or "").upper() != ticker]
    positions.append({"ticker": ticker, "weight": weight})
    save_portfolio(positions)
    return api_portfolio()


@app.route("/api/portfolio/remove", methods=["POST"])
def api_portfolio_remove():
    from intelligence_terminal import load_portfolio, save_portfolio
    ticker = str((request.get_json() or {}).get("ticker") or "").upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Valid ticker is required."}, 400
    portfolio = load_portfolio()
    positions = [p for p in portfolio.get("positions", []) if (p.get("ticker") or "").upper() != ticker]
    save_portfolio(positions)
    return api_portfolio()


@app.route("/api/terminal/execute", methods=["POST"])
def api_terminal_execute():
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command") or "").strip()
    if len(command) > 64:
        return {"html": "<span class=\"bbg-text-red\">Command too long (max 64).</span>"}, 400
    if not command:
        return {"text": ""}
    try:
        from terminal_commands import process_command
        return process_command(command)
    except Exception as e:
        logger.info(f"Terminal command failed: {e}")
        return {"error": "Terminal error"}, 500


@app.route("/api/reports")
def api_reports():
    reports = []
    for row in _catalog_rows():
        ticker = row["ticker"]
        ticker_dir = OUTPUT_ROOT / ticker
        for file in [ticker_dir / f"{ticker}_Financial_Model.xlsx", ticker_dir / f"{ticker}_dashboard.html", DB_DIR / f"{ticker}.json"]:
            if file.exists():
                reports.append({
                    "ticker": ticker,
                    "name": file.name,
                    "type": file.suffix.lstrip(".").upper(),
                    "size": file.stat().st_size,
                    "modified": file.stat().st_mtime,
                    "url": f"/excel/{ticker}" if file.suffix == ".xlsx" else (f"/json/{ticker}" if file.suffix == ".json" else f"/dashboard/{ticker}")
                })
    return {"reports": reports}


@app.route("/api/system/health")
def api_system_health():
    rows = _catalog_rows()
    return {
        "status": "ONLINE",
        "database_count": len(rows),
        "cache_size": get_cache_size_str(),
        "output_dir": str(OUTPUT_ROOT),
        "routes": ["dashboard", "screener", "query", "portfolio", "intel"],
    }


@app.route("/api/stock/<ticker>")
def get_stock(ticker):
    """Retrieve detailed qualitative and quantitative JSON record for a ticker."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    data = local_db.load_stock_record(ticker)
    if data is None:
        return {"error": f"Ticker {ticker} not found in database"}, 404
    return data


@app.route("/api/stock/<ticker>/financials")
def get_stock_financials(ticker):
    """Retrieve financial data (annual and quarterly) for a ticker."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    data = local_db.load_stock_record(ticker)
    if not data:
        return {"error": f"Ticker {ticker} not found in database"}, 404
        
    try:
        return {
            "financials": data.get("financials"),
            "balance_sheet": data.get("balance_sheet"),
            "cashflow": data.get("cashflow"),
            "q_financials": data.get("q_financials"),
            "q_balance_sheet": data.get("q_balance_sheet"),
            "q_cashflow": data.get("q_cashflow")
        }
    except Exception as e:
        return {"error": f"Failed to parse database: {str(e)}"}, 500


@app.route("/api/stock/<ticker>/history")
def get_stock_history(ticker):
    """Retrieve price history for a ticker with cache fallback."""
    import yfinance as yf
    import json
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    period = request.args.get("period", "1mo").strip()
    if period not in ALLOWED_PERIODS:
        period = "1mo"
    # In test mode, skip live yfinance (would timeout) and use DB fallback directly
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        # Fast path for tests — no network
        data = local_db.load_stock_record(ticker)
        if data and data.get("price_history_compact"):
            try:
                compact = data.get("price_history_compact")
                history_list = []
                for d_str, price in sorted(compact.items()):
                    history_list.append({"date": d_str, "close": float(price), "open": float(price), "high": float(price), "low": float(price), "volume": 0})
                return {"ticker": ticker, "history": history_list, "source": "local_database_test"}
            except Exception:
                pass
        # Return empty but not error for adversarial tickers — fast
        return {"ticker": ticker, "history": [], "source": "mock_test"}

    # Try dynamic fetch first
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if not hist.empty:
            history_list = []
            for idx, row in hist.iterrows():
                date_str = idx.strftime("%Y-%m-%d %H:%M:%S") if hasattr(idx, "strftime") else str(idx)
                history_list.append({
                    "date": date_str,
                    "close": float(row["Close"]),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "volume": int(row["Volume"])
                })
            return {"ticker": ticker, "history": history_list}
    except Exception as e:
        logger.info(f"Yfinance history fetch failed for {ticker}: {e}")
        
    # Fallback to database compact history
    data = local_db.load_stock_record(ticker)
    if data:
        try:
            compact = data.get("price_history_compact")
            if compact:
                # compact is a dict of date -> price
                history_list = []
                for d_str, price in sorted(compact.items()):
                    history_list.append({
                        "date": d_str,
                        "close": float(price),
                        "open": float(price),
                        "high": float(price),
                        "low": float(price),
                        "volume": 0
                    })
                return {"ticker": ticker, "history": history_list, "source": "local_database"}
        except Exception as e:
            logger.info(f"Database fallback history read failed for {ticker}: {e}")
            
    return {"error": f"No history found for {ticker}"}, 404


@app.route("/api/stock/<ticker>/recalculate", methods=["POST"])
def recalculate_stock(ticker):
    """Recalculate dynamic DCF model inside JSON database and Excel file on disk."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    data = local_db.load_stock_record(ticker)
    if not data:
        return {"error": f"Ticker {ticker} not found in database"}, 404
        
    try:
        req_data = request.get_json() or {}

        def pct_input(name, default, low, high):
            raw = _safe_float(req_data.get(name), default)
            raw = max(low, min(raw, high))
            return raw / 100.0

        wacc = pct_input("wacc", 9.0, 1.0, 25.0)
        growth_1_5 = pct_input("growth_1_5", 15.0, -50.0, 80.0)
        growth_6_10 = pct_input("growth_6_10", 10.0, -30.0, 50.0)
        terminal_growth = pct_input("terminal_growth", 2.5, -2.0, 6.0)
        if wacc <= terminal_growth + 0.01:
            terminal_growth = max(-0.02, wacc - 0.01)

        # Data is already loaded above
            
        metrics = data.get("key_metrics", {})
        dcf_data = data.get("dcf_data", {})
        
        fcf_base = _safe_float(dcf_data.get("fcf_base") or metrics.get("freeCashflow"), 0)
        total_cash = _safe_float(metrics.get("totalCash"), 0)
        total_debt = _safe_float(metrics.get("totalDebt"), 0)
        if fcf_base == 0:
            return {"error": "Cannot recalculate DCF without a non-zero free cash flow base."}, 422
        
        shares_out = metrics.get("sharesOutstanding")
        shares_out = _safe_float(shares_out, 0)
        if shares_out <= 1:
            mc = metrics.get("marketCap")
            cp = metrics.get("current_price") or metrics.get("currentPrice") or 1.0
            if mc and cp:
                shares_out = _safe_float(mc, 0) / _safe_float(cp, 1)
            else:
                shares_out = 1.0
            
        curr_price = _safe_float(metrics.get("current_price") or metrics.get("currentPrice"), 0)
        
        # Projections
        npv = 0
        current_fcf = fcf_base
        for i in range(1, 11):
            gr = growth_1_5 if i <= 5 else growth_6_10
            current_fcf *= (gr + 1.0)  # Correct multiplication syntax
            pv = current_fcf / ((1 + wacc) ** i)
            npv += pv
            
        spread = wacc - terminal_growth
        if spread <= 0:
            return {"error": "WACC must be greater than terminal growth."}, 422
        terminal_value = (current_fcf * (1 + terminal_growth)) / spread
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
        try:
            from ai_engine import _enforce_valuation_coherence
        except ImportError:
            from .ai_engine import _enforce_valuation_coherence
        data["analysis"] = _enforce_valuation_coherence(data["analysis"], data)
        
        # Save back to database
        local_db.save_stock_record(ticker, data)
            
        # Re-generate Excel file dynamically
        try:
            from excel_generator import generate_excel_model
        except ImportError:
            from .excel_generator import generate_excel_model
        ticker_dir = OUTPUT_ROOT / ticker
        generate_excel_model(ticker, data, ticker_dir, data["analysis"])
        
        logger.info(f"  [+] Recalculated DCF and refreshed Excel Model for {ticker}.")
        return data
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Recalculation failed: {str(e)}"}, 500

@app.route("/verdict/<ticker>")
@app.route("/dashboard/<ticker>")
def serve_dashboard(ticker):
    """Serve the single master dynamic client dashboard template."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return "Invalid ticker format", 400
    if _db_path(ticker).exists():
        return render_template("dashboard.html", ticker=ticker)
    # No record: send to hub which auto-analyzes via ?ticker= then redirects back.
    return redirect(f"/?ticker={ticker}")

@app.route("/guide")
def serve_guide():
    """Serve the complete A to Z Institutional Quantitative Reference Guide."""
    return render_template("guide.html")

@app.route("/excel/<ticker>")
def download_excel(ticker):
    """Download the dynamic Excel financial model of a ticker."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    # Prevent path traversal via resolve check
    path = (OUTPUT_ROOT / ticker / f"{ticker}_Financial_Model.xlsx").resolve()
    try:
        path.relative_to(OUTPUT_ROOT.resolve())
    except ValueError:
        return {"error": "Invalid path"}, 400
    if path.exists() and path.is_file():
        return send_file(path, as_attachment=True, download_name=f"{ticker}_Financial_Model.xlsx")
    return f"Excel model for {ticker} not found.", 404

@app.route("/json/<ticker>")
def download_json(ticker):
    """Download the raw JSON database record of a ticker."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    path = _db_path(ticker).resolve()
    try:
        path.relative_to(OUTPUT_ROOT.resolve())
    except ValueError:
        return {"error": "Invalid path"}, 400
    if path.exists() and path.is_file():
        return send_file(path, as_attachment=True, download_name=f"{ticker}_Raw_Data.json")
    return f"JSON record for {ticker} not found.", 404

@app.route("/api/notion/sync/<ticker>", methods=["POST"])
def sync_notion(ticker):
    """Trigger a Notion workspace sync for a ticker."""
    ticker = ticker.upper().strip()
    try:
        try:
            from notion_integrator import auto_generate_notion_page
        except ImportError:
            from app.notion_integrator import auto_generate_notion_page
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
        raw_news = yf.Ticker(ticker).news or []
        news = []
        for n in raw_news:
            c = (n or {}).get("content") or {}
            if not c:
                continue
            cu = c.get("clickThroughUrl") or {}
            pv = c.get("provider") or {}
            news.append({
                "title": c.get("title", "News"),
                "link": cu.get("url", "#"),
                "publisher": pv.get("displayName", "Wire"),
                "pubDate": c.get("pubDate", "")
            })
        return {"status": "success", "news": news[:15]}
    except Exception as e:
        return {"error": str(e)}, 500




# Auto-update state
import threading
_auto_update_lock = threading.Lock()
auto_update_state = {"last_run": None, "next_run": None, "running": False, "queue": [], "log": []}
live_quotes_cache = {"data": None, "timestamp": 0}

ticker_tape_cache = {"data": None, "timestamp": 0}

def get_ticker_tape():
    import time
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        return [
            {"label": "S&P 500", "val": "5,200.00", "pct": 0.5, "is_yield": False},
            {"label": "NASDAQ 100", "val": "18,000.00", "pct": 0.7, "is_yield": False},
            {"label": "DOW JONES", "val": "38,000.00", "pct": 0.3, "is_yield": False},
            {"label": "CBOE VIX", "val": "14.00", "pct": -1.2, "is_yield": False},
            {"label": "US 10-YR YIELD", "val": "4.100%", "pct": 0.02, "is_yield": True},
            {"label": "BTC/USD", "val": "68,000.00", "pct": 1.1, "is_yield": False},
        ]
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


@app.route("/api/ticker-tape")
def api_ticker_tape():
    return get_ticker_tape()


@app.route("/api/stock/<ticker>/live-quote")
def api_live_quote(ticker):
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        # Mock live quote in test mode — no yfinance network
        return {"ticker": ticker, "price": 150.0, "change": 1.2, "pct": 0.008, "source": "mock_test"}
    local = _load_stock_record(ticker) or {}
    metrics = local.get("key_metrics", {})
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="5d")
        if len(hist) >= 2:
            current = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            return {"ticker": ticker, "price": current, "change": current - prev, "pct": ((current - prev) / prev) if prev else 0, "source": "yfinance"}
    except Exception as e:
        logger.info(f"Live quote failed for {ticker}: {e}")
    price = _safe_float(metrics.get("current_price") or metrics.get("currentPrice"), 0)
    return {"ticker": ticker, "price": price, "change": 0, "pct": 0, "source": "local_database"}


@app.route("/api/stock/<ticker>/earnings-preview")
def api_earnings_preview(ticker):
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    out = {"ticker": ticker, "next_date": None, "eps_avg": None, "eps_low": None, "eps_high": None, "surprises": [],
           "rev_avg": None, "rev_low": None, "rev_high": None, "analysts": None, "quarters": []}
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar or {}
        dates = cal.get("Earnings Date") or []
        if dates:
            d = dates[0]
            out["next_date"] = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        out["eps_avg"] = _safe_float(cal.get("Earnings Average"), None)
        out["eps_low"] = _safe_float(cal.get("Earnings Low"), None)
        out["eps_high"] = _safe_float(cal.get("Earnings High"), None)
        out["rev_avg"] = _safe_float(cal.get("Revenue Average"), None)
        out["rev_low"] = _safe_float(cal.get("Revenue Low"), None)
        out["rev_high"] = _safe_float(cal.get("Revenue High"), None)
    except Exception as e:
        logger.info(f"Earnings preview (calendar) failed for {ticker}: {e}")
    try:
        import yfinance as yf
        ed = yf.Ticker(ticker).get_earnings_dates(limit=12)
        if ed is not None and not ed.empty:
            for idx, row in ed.iterrows():
                try:
                    rep = row.get("Reported EPS")
                    import math
                    if rep is None or (isinstance(rep, float) and math.isnan(rep)):
                        continue
                    ds = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                    out["surprises"].append({
                        "date": ds,
                        "estimate": _safe_float(row.get("EPS Estimate"), None),
                        "reported": _safe_float(rep, None),
                        "surprise_pct": _safe_float(row.get("Surprise(%)"), None)})
                except Exception:
                    continue
            out["surprises"] = out["surprises"][:8]
    except Exception as e:
        logger.info(f"Earnings preview (history) failed for {ticker}: {e}")
    try:
        rec = _load_stock_record(ticker) or {}
        m = rec.get("key_metrics", {})
        out["analysts"] = m.get("numberOfAnalystOpinions")
        qf = rec.get("q_financials") or {}
        rows, cols = qf.get("rows") or [], qf.get("columns") or []
        if rows and len(cols) > 1:
            labK = list(rows[0].keys())[0]
            rev = next((r for r in rows if str(r.get(labK) or "").lower() == "total revenue"), None)
            net = next((r for r in rows if str(r.get(labK) or "").lower() == "net income"), None)
            for c in cols[1:][-4:]:
                out["quarters"].append({
                    "date": c,
                    "revenue": _safe_float(rev.get(c), None) if rev else None,
                    "net_income": _safe_float(net.get(c), None) if net else None})
    except Exception as e:
        logger.info(f"Earnings preview (local) failed for {ticker}: {e}")
    return out

@app.route("/api/stock/<ticker>/ratings-trend")
def api_ratings_trend(ticker):
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    out = {"ticker": ticker, "periods": []}
    try:
        import yfinance as yf
        rec = yf.Ticker(ticker).get_recommendations()
        if rec is not None and not rec.empty:
            for _, row in rec.iterrows():
                def _ci(v):
                    try:
                        f = float(v)
                        import math
                        return int(f) if not math.isnan(f) else 0
                    except Exception:
                        return 0
                out["periods"].append({
                    "period": str(row.get("period", "")),
                    "strongBuy": _ci(row.get("strongBuy")),
                    "buy": _ci(row.get("buy")),
                    "hold": _ci(row.get("hold")),
                    "sell": _ci(row.get("sell")),
                    "strongSell": _ci(row.get("strongSell"))})
    except Exception as e:
        logger.info(f"Ratings trend failed for {ticker}: {e}")
    return out

ESTIMATES_CACHE_FILE = DB_DIR / "_estimates_cache.json"
ESTIMATES_CACHE_TTL_HOURS = 24
_estimates_lock = threading.Lock()
prewarm_state = {"running": False, "total": 0, "done": [], "failed": []}


def _fetch_live_estimates(ticker):
    out = {"ticker": ticker, "earnings": [], "revenue": [], "growth": []}

    def _rows(df, year_ago_col):
        rows = []
        try:
            if df is None or df.empty:
                return rows
            for idx, row in df.iterrows():
                rows.append({
                    "period": str(idx),
                    "avg": _safe_float(row.get("avg"), None),
                    "low": _safe_float(row.get("low"), None),
                    "high": _safe_float(row.get("high"), None),
                    "analysts": _safe_float(row.get("numberOfAnalysts"), None),
                    "growth": _safe_float(row.get("growth"), None),
                    "year_ago": _safe_float(row.get(year_ago_col), None)})
        except Exception:
            pass
        return rows

    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        try:
            out["earnings"] = _rows(tk.get_earnings_estimate(), "yearAgoEps")
        except Exception as e:
            logger.info(f"Estimates (earnings) failed for {ticker}: {e}")
        try:
            out["revenue"] = _rows(tk.get_revenue_estimate(), "yearAgoRevenue")
        except Exception as e:
            logger.info(f"Estimates (revenue) failed for {ticker}: {e}")
        try:
            g = tk.get_growth_estimates()
            if g is not None and not g.empty:
                for idx, row in g.iterrows():
                    out["growth"].append({
                        "period": str(idx),
                        "stock": _safe_float(row.get("stockTrend"), None),
                        "index": _safe_float(row.get("indexTrend"), None)})
        except Exception as e:
            logger.info(f"Estimates (growth) failed for {ticker}: {e}")
    except Exception as e:
        logger.info(f"Estimates failed for {ticker}: {e}")
    return out


def _read_estimates_cache():
    try:
        with open(ESTIMATES_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_estimates_cache(cache):
    try:
        ESTIMATES_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ESTIMATES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1)
    except Exception as e:
        logger.info(f"[Estimates] failed to persist cache: {e}")


@app.route("/api/stock/<ticker>/estimates")
def api_stock_estimates(ticker):
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    import time as _time
    try:
        entry = _read_estimates_cache().get(ticker) or {}
        if entry.get("fetched_at") and (_time.time() - float(entry["fetched_at"])) < ESTIMATES_CACHE_TTL_HOURS * 3600 and entry.get("data"):
            cached = dict(entry["data"])
            cached["cached"] = True
            return cached
    except Exception:
        pass
    out = _fetch_live_estimates(ticker)
    out["cached"] = False
    try:
        with _estimates_lock:
            cache = _read_estimates_cache()
            if out["earnings"] or out["revenue"]:
                cache[ticker] = {"fetched_at": _time.time(), "data": out}
                _write_estimates_cache(cache)
            elif (cache.get(ticker) or {}).get("data"):
                stale = dict(cache[ticker]["data"])
                stale["cached"] = True
                stale["stale"] = True
                return stale
    except Exception:
        pass
    return out


@app.route("/api/system/estimates/prewarm", methods=["GET", "POST"])
def api_estimates_prewarm():
    if request.method == "GET":
        try:
            cache = _read_estimates_cache()
            return {"running": prewarm_state["running"], "total": prewarm_state["total"],
                    "done": prewarm_state["done"], "failed": prewarm_state["failed"],
                    "cached_tickers": sorted(cache.keys()), "cached_count": len(cache)}
        except Exception as e:
            return {"error": str(e)}, 500
    if prewarm_state["running"]:
        return {"status": "already_running", "done": prewarm_state["done"]}

    def _bg():
        import time as _t
        prewarm_state["running"] = True
        try:
            rows = _catalog_rows()
            tickers = [r["ticker"] for r in rows]
            try:
                have = set(_read_estimates_cache().keys())
                tickers = [tk for tk in tickers if tk not in have] or [r["ticker"] for r in rows]
            except Exception:
                pass
            prewarm_state["total"] = len(tickers)
            prewarm_state["done"] = []
            prewarm_state["failed"] = []
            for tk in tickers:
                try:
                    out = _fetch_live_estimates(tk)
                    if out["earnings"] or out["revenue"]:
                        out["cached"] = False
                        with _estimates_lock:
                            cache = _read_estimates_cache()
                            cache[tk] = {"fetched_at": _t.time(), "data": out}
                            _write_estimates_cache(cache)
                        prewarm_state["done"].append(tk)
                    else:
                        prewarm_state["failed"].append(tk)
                except Exception as e:
                    prewarm_state["failed"].append(tk)
                    logger.info(f"[Estimates] prewarm {tk} failed: {e}")
                _t.sleep(3)
        finally:
            prewarm_state["running"] = False

    import threading as _th
    _th.Thread(target=_bg, daemon=True).start()
    return {"status": "started"}


def _fetch_quotes_concurrent(tickers, with_vol=False):
    """Concurrent per-ticker 2d history fetch (~1-2s for 25-50 tickers vs 5-9s batched). Never raises."""
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor
    live = {}

    def _one(tk):
        try:
            hist = yf.Ticker(tk).history(period="2d")
            if hist is None or hist.empty or "Close" not in hist:
                return None
            closes = hist["Close"].dropna()
            if len(closes) < 2:
                return None
            cur, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
            if not (math.isfinite(cur) and math.isfinite(prev)) or not prev:
                return None
            q = {"price": cur, "change": cur - prev, "pct": (cur - prev) / prev, "source": "yfinance"}
            if with_vol:
                try:
                    vols = hist["Volume"].dropna() if "Volume" in hist else []
                    q["vol"] = int(vols.iloc[-1]) if len(vols) else 0
                except Exception:
                    q["vol"] = 0
            return q
        except Exception:
            return None

    try:
        with ThreadPoolExecutor(max_workers=10) as ex:
            for tk, q in zip(tickers, ex.map(_one, tickers)):
                if q:
                    live[tk] = q
    except Exception as e:
        logger.info(f"concurrent quotes failed: {e}")
    return live


@app.route("/api/stocks/live-quotes")
def api_live_quotes():
    tickers = [t.strip().upper() for t in request.args.get("tickers", "").split(",") if t.strip()]
    if not tickers:
        tickers = [row["ticker"] for row in _catalog_rows()]
    tickers = [t for t in tickers[:50] if is_valid_ticker(t)]
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        quotes = []
        for ticker in tickers:
            row = next((r for r in _catalog_rows() if r["ticker"] == ticker), None)
            quotes.append({"ticker": ticker, "price": row.get("current_price", 150.0) if row else 150.0, "change": 1.2, "pct": 0.008, "source": "mock_test"})
        return {"quotes": quotes}
    # 30s cache to avoid hammering yfinance on every 30s frontend poll
    import time as _tq
    _cache_key = ",".join(tickers)
    if (live_quotes_cache.get("data") and live_quotes_cache.get("key") == _cache_key
            and _tq.time() - live_quotes_cache.get("timestamp", 0) < 15):
        return {"quotes": live_quotes_cache["data"]}
    # Concurrent per-ticker fetch (~1-2s), fallback to local
    quotes = []
    try:
        live = _fetch_quotes_concurrent(tickers)
        for ticker in tickers:
            if ticker in live:
                quotes.append({"ticker": ticker, **live[ticker]})
            else:
                row = next((r for r in _catalog_rows() if r["ticker"] == ticker), None)
                quotes.append({"ticker": ticker, "price": row.get("current_price", 0) if row else 0, "change": 0, "pct": 0, "source": "local_database"})
        live_quotes_cache["data"] = quotes
        live_quotes_cache["key"] = _cache_key
        live_quotes_cache["timestamp"] = _tq.time()
        return {"quotes": quotes}
    except Exception as e:
        logger.info(f"live-quotes error: {e}")
        for ticker in tickers:
            row = next((r for r in _catalog_rows() if r["ticker"] == ticker), None)
            quotes.append({"ticker": ticker, "price": row.get("current_price", 0) if row else 0, "change": 0, "pct": 0, "source": "local_database"})
        return {"quotes": quotes}


@app.route("/api/stock/<ticker>/dividends")
def api_stock_dividends(ticker):
    """Dividend history: yield/rate/payout + yearly totals + recent payouts."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    local = _load_stock_record(ticker) or {}
    m = local.get("key_metrics", {})
    base = {"ticker": ticker, "yield": m.get("dividendYield"), "rate": m.get("dividendRate"),
            "payout": m.get("payoutRatio"), "frequency": "none", "annual": [], "recent": [],
            "source": "local_no_history"}
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        base["source"] = "mock_test"
        return base
    try:
        import yfinance as yf
        from datetime import timedelta
        divs = yf.Ticker(ticker).dividends
        if divs is None or len(divs) == 0:
            return base
        yearly = divs.resample("YE").sum().tail(8)
        base["annual"] = [{"year": int(idx.year), "amount": round(float(v), 4)} for idx, v in yearly.items()]
        base["recent"] = [{"date": idx.strftime("%Y-%m-%d"), "amount": round(float(v), 4)}
                          for idx, v in divs.tail(8).items()]
        last = divs.index.max()
        cnt = int(sum(1 for d in divs.index if d >= last - timedelta(days=365)))
        base["frequency"] = "quarterly" if cnt >= 4 else ("semi-annual" if cnt == 2 else ("annual" if cnt == 1 else "irregular"))
        base["source"] = "yfinance"
        return base
    except Exception as e:
        logger.info(f"dividends failed for {ticker}: {e}")
        return base


@app.route("/api/peers/sector/<ticker>")
def api_sector_peers(ticker):
    """Sector P/E median + mates from the local catalog (always works, no LLM)."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    rows = _catalog_rows()
    me = next((r for r in rows if r["ticker"] == ticker), None)
    if not me:
        return {"error": f"Ticker {ticker} not found"}, 404
    sector = me.get("sector") or "N/A"
    mates = [r for r in rows if r.get("sector") == sector and r["ticker"] != ticker]
    vals = sorted(r["pe_ratio"] for r in mates if r.get("pe_ratio"))
    med = vals[len(vals) // 2] if vals else None
    return {"ticker": ticker, "sector": sector, "count": len(mates) + 1, "median_pe": med,
            "your_pe": me.get("pe_ratio"),
            "mates": [{"ticker": r["ticker"], "pe": r.get("pe_ratio")} for r in mates[:8]]}


@app.route("/api/stock/<ticker>/insiders")
def api_stock_insiders(ticker):
    """Live insider transactions (yfinance). Schema-proof: stringifies whatever columns come back."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        return {"ticker": ticker, "trades": [], "source": "mock_test"}
    try:
        import yfinance as yf
        import pandas as pd
        df = yf.Ticker(ticker).insider_transactions
        trades = []
        if df is not None and not df.empty:
            for idx, row in df.head(15).iterrows():
                d = dict(row)
                rec = {"date": str(d.get("Start Date") or d.get("Date") or idx)[:10]}
                for k, v in dict(row).items():
                    try:
                        rec[str(k)] = None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
                    except Exception:
                        rec[str(k)] = str(v)
                trades.append(rec)
        return {"ticker": ticker, "trades": trades, "source": "yfinance"}
    except Exception as e:
        logger.info(f"insiders failed for {ticker}: {e}")
        return {"ticker": ticker, "trades": [], "error": str(e), "source": "unavailable"}


@app.route("/api/stock/<ticker>/holders")
def api_stock_holders(ticker):
    """Top institutional + mutual-fund holders and major-holder snapshot (yfinance)."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        return {"ticker": ticker, "institutions": [], "funds": [], "major": {}, "source": "mock_test"}

    def _rows(df, n=10):
        import pandas as pd
        out = []
        if df is None or df.empty:
            return out
        for _, row in df.head(n).iterrows():
            rec = {}
            for k, v in dict(row).items():
                try:
                    rec[str(k)] = None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
                except Exception:
                    rec[str(k)] = str(v)
            out.append(rec)
        return out

    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        try:
            inst = _rows(tk.institutional_holders)
        except Exception:
            inst = []
        try:
            funds = _rows(tk.mutualfund_holders)
        except Exception:
            funds = []
        major = {}
        try:
            mh = tk.major_holders
            if mh is not None and not mh.empty:
                col = mh.columns[0]
                for idx in mh.index:
                    v = mh.loc[idx, col]
                    import pandas as pd
                    major[str(idx)] = None if pd.isna(v) else (v.item() if hasattr(v, "item") else str(v))
        except Exception:
            pass
        return {"ticker": ticker, "institutions": inst, "funds": funds, "major": major, "source": "yfinance"}
    except Exception as e:
        logger.info(f"holders failed for {ticker}: {e}")
        return {"ticker": ticker, "institutions": [], "funds": [], "major": {}, "error": str(e), "source": "unavailable"}


@app.route("/api/stock/<ticker>/earnings")
def api_stock_earnings(ticker):
    """Earnings calendar + EPS/revenue estimates + reported history (yfinance)."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        return {"ticker": ticker, "next": None, "estimates": [], "history": [], "source": "mock_test"}
    out = {"ticker": ticker, "next": None, "estimates": [], "history": [], "source": "yfinance"}
    try:
        import yfinance as yf
        import pandas as pd
        tk = yf.Ticker(ticker)
        try:
            cal = tk.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date") or cal.get("Earnings_Date")
                if isinstance(ed, (list, tuple)) and ed:
                    out["next"] = [str(d)[:10] for d in ed]
                out["calendar"] = {str(k): str(v)[:120] for k, v in list(cal.items())[:12]}
        except Exception as e:
            logger.info(f"earnings calendar failed for {ticker}: {e}")
        try:
            edt = tk.earnings_dates
            if edt is not None and not edt.empty:
                for idx, row in edt.head(8).iterrows():
                    d = dict(row)
                    out["history"].append({
                        "date": str(idx)[:10],
                        "estimate": (None if pd.isna(d.get("EPS Estimate")) else float(d.get("EPS Estimate"))),
                        "reported": (None if pd.isna(d.get("Reported EPS")) else float(d.get("Reported EPS"))),
                        "surprise": (None if pd.isna(d.get("Surprise(%)")) else float(d.get("Surprise(%)"))),
                    })
        except Exception as e:
            logger.info(f"earnings history failed for {ticker}: {e}")
        return out
    except Exception as e:
        logger.info(f"earnings failed for {ticker}: {e}")
        out["error"] = str(e)
        out["source"] = "unavailable"
        return out


@app.route("/api/stock/<ticker>/esg")
def api_stock_esg(ticker):
    """ESG / sustainability scores (yfinance)."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        return {"ticker": ticker, "scores": {}, "source": "mock_test"}
    try:
        import yfinance as yf
        import pandas as pd
        s = yf.Ticker(ticker).sustainability
        scores = {}
        if s is not None and not s.empty:
            col = s.columns[0]
            for key in ["totalEsg", "environmentScore", "socialScore", "governanceScore", "controversialWeapons",
                        "gambling", "tobacco", "adult", "militaryContract", "smallArms", "thermalCoal",
                        "palmOil", "coal", "esgPerformance"]:
                if key in s.index:
                    v = s.loc[key, col]
                    try:
                        scores[key] = None if pd.isna(v) else (float(v) if isinstance(v, (int, float)) else str(v))
                    except Exception:
                        scores[key] = str(v)
        return {"ticker": ticker, "scores": scores, "source": "yfinance"}
    except Exception as e:
        logger.info(f"esg failed for {ticker}: {e}")
        return {"ticker": ticker, "scores": {}, "error": str(e), "source": "unavailable"}


@app.route("/api/market/movers")
def api_market_movers():
    """Gainers / losers / most-active computed live across the local catalog (free)."""
    rows = _catalog_rows()
    tickers = [r["ticker"] for r in rows[:50] if is_valid_ticker(r["ticker"])]
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        demo = [{"ticker": t, "price": 100.0, "change": 1.0, "pct": 0.01, "vol": 1000, "source": "mock_test"} for t in tickers[:5]]
        return {"gainers": demo, "losers": demo, "actives": demo, "source": "mock_test", "universe": len(tickers)}
    quotes = []
    try:
        live = _fetch_quotes_concurrent(tickers, with_vol=True)
        for tk in tickers:
            if tk in live:
                quotes.append({"ticker": tk, **live[tk]})
    except Exception as e:
        logger.info(f"movers error: {e}")
    by_pct = sorted(quotes, key=lambda q: q["pct"])
    by_vol = sorted(quotes, key=lambda q: q["vol"], reverse=True)
    return {"gainers": list(reversed(by_pct))[:5], "losers": by_pct[:5], "actives": by_vol[:5],
            "source": "yfinance", "universe": len(tickers), "quoted": len(quotes)}


@app.route("/api/stock/<ticker>/profile")
def api_stock_profile(ticker):
    """Company profile: officers, website, employees (yfinance info, live)."""
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker"}, 400
    local = _load_stock_record(ticker) or {}
    m = local.get("key_metrics", {})
    base = {"ticker": ticker, "name": local.get("company_name", ticker),
            "website": m.get("website"), "employees": m.get("fullTimeEmployees"),
            "sector": m.get("sector"), "industry": m.get("industry"),
            "officers": [], "source": "local"}
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        base["source"] = "mock_test"
        return base
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        off = []
        for o in (info.get("companyOfficers") or [])[:6]:
            if isinstance(o, dict) and o.get("name"):
                off.append({"name": o.get("name"), "title": o.get("title", "")})
        base.update({"website": info.get("website") or base["website"],
                     "employees": info.get("fullTimeEmployees") or base["employees"],
                     "officers": off, "source": "yfinance"})
        return base
    except Exception as e:
        logger.info(f"profile failed for {ticker}: {e}")
        base["error"] = str(e)
        return base


@app.route("/macro")
def serve_macro():
    return render_template("macro.html")


@app.route("/api/macro/snapshot")
def api_macro_snapshot():
    """Combined macro snapshot (cached 1h in macro_fetcher). Adapts keys for page + tests."""
    try:
        try:
            import macro_fetcher
        except ImportError:
            from app import macro_fetcher
        force = request.args.get("force", "").strip().lower() in {"1", "true", "yes"}
        s = macro_fetcher.get_macro_snapshot(force=force)
        return {"yields": s.get("yields") or {}, "gauges": s.get("risk") or {},
                "regime": s.get("regime") or {}, "fed_stance": s.get("fed") or {},
                "generated_at": s.get("asof"), "cached": s.get("cached"),
                "source": s.get("source")}
    except Exception as e:
        logger.exception(f"/api/macro/snapshot failed: {e}")
        return {"error": str(e)}, 500


@app.route("/api/macro/yields")
def api_macro_yields():
    try:
        try:
            import macro_fetcher
        except ImportError:
            from app import macro_fetcher
        return {"yields": macro_fetcher.get_yield_curve()}
    except Exception as e:
        logger.exception(f"/api/macro/yields failed: {e}")
        return {"error": str(e)}, 500


@app.route("/api/macro/regime")
def api_macro_regime():
    try:
        try:
            import macro_fetcher
        except ImportError:
            from app import macro_fetcher
        return {"regime": macro_fetcher.get_regime()}
    except Exception as e:
        logger.exception(f"/api/macro/regime failed: {e}")
        return {"error": str(e)}, 500


@app.route("/api/intel/macro/<ticker>")
def api_macro_impact(ticker):
    ticker = ticker.upper().strip()
    if not is_valid_ticker(ticker):
        return {"error": "Invalid ticker format"}, 400
    data = local_db.load_stock_record(ticker)
    if not data:
        return {"error": f"Ticker {ticker} not found in database"}, 404
    try:
        from ai_engine import get_macro_impact
    except ImportError:
        from app.ai_engine import get_macro_impact
    impact = get_macro_impact(data) or {}
    # normalize for page + contract tests (dicts, never null)
    rr = impact.get("regime_read")
    impact["regime_read"] = {"text": str(rr)} if not isinstance(rr, dict) else rr
    rs = impact.get("rate_sensitivity")
    impact["rate_sensitivity"] = {"level": "MED", "why": str(rs)} if not isinstance(rs, dict) else rs
    impact["ticker"] = ticker
    return impact


@app.route("/compare")
def serve_compare():
    return render_template("compare.html")


@app.route("/api/compare")
def api_compare():
    tickers = [t.strip().upper() for t in request.args.get("tickers", "").split(",") if is_valid_ticker(t.strip().upper())]
    rows = [row for row in _catalog_rows() if row["ticker"] in set(tickers)]
    return {"stocks": rows}

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




@app.after_request
def _no_store_api(resp):
    # Live data must never be served stale from browser/proxy cache.
    try:
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
    except Exception:
        pass
    return resp


@app.errorhandler(404)
def page_not_found(e):
    # Return JSON for API routes, HTML for pages
    if request.path.startswith("/api/"):
        return {"error": "Not found", "path": request.path}, 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    logger.exception(f"Internal server error on {request.path}: {e}")
    if request.path.startswith("/api/"):
        return {"error": "Internal server error", "detail": str(e)}, 500
    return render_template('404.html'), 500

@app.errorhandler(429)
def rate_limited(e):
    if request.path.startswith("/api/"):
        return {"error": "Rate limited, retry later"}, 429
    return "Rate limited", 429

EARNINGS_SCHEDULE_FILE = DB_DIR / "_earnings_schedule.json"
EARNINGS_SCHEDULE_TTL_DAYS = 7
EARNINGS_POST_WINDOW_DAYS = 4
_EARNINGS_SCHED = None


def _read_earnings_schedule():
    global _EARNINGS_SCHED
    if _EARNINGS_SCHED is not None:
        return _EARNINGS_SCHED
    try:
        with open(EARNINGS_SCHEDULE_FILE, "r", encoding="utf-8") as f:
            _EARNINGS_SCHED = json.load(f) or {}
    except Exception:
        _EARNINGS_SCHED = {}
    return _EARNINGS_SCHED


def _write_earnings_schedule(sched):
    global _EARNINGS_SCHED
    _EARNINGS_SCHED = sched
    try:
        EARNINGS_SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EARNINGS_SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(sched, f, indent=1)
    except Exception as e:
        logger.info(f"[Earnings] failed to persist schedule: {e}")


def _parse_record_date(gen):
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(str(gen).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _fetch_next_earnings(ticker):
    import yfinance as yf
    try:
        cal = yf.Ticker(ticker).calendar or {}
        dates = cal.get("Earnings Date") or cal.get("Earnings_Date") or []
        if isinstance(dates, dict):
            dates = list(dates.keys())
        out = []
        for d in dates:
            try:
                import datetime as _dt
                if isinstance(d, str):
                    out.append(_dt.date.fromisoformat(d[:10]))
                elif hasattr(d, "date"):
                    out.append(d.date())
                else:
                    out.append(_dt.date.fromisoformat(str(d)[:10]))
            except Exception:
                continue
        out = sorted(set(out))
        return out[0] if out else None
    except Exception as e:
        logger.info(f"[Earnings] calendar fetch failed for {ticker}: {e}")
        return None


def _refresh_earnings_schedule(tickers):
    import time
    from datetime import datetime, timezone
    sched = _read_earnings_schedule()
    now = datetime.now(timezone.utc)
    changed = False
    for ticker in tickers:
        entry = sched.get(ticker) or {}
        checked = entry.get("checked_at") or ""
        try:
            cdt = _parse_record_date(checked) if checked else None
            age = (now - cdt).days if cdt else 999
        except Exception:
            age = 999
        if age < EARNINGS_SCHEDULE_TTL_DAYS and entry.get("next_earnings"):
            continue
        nxt = _fetch_next_earnings(ticker)
        sched[ticker] = {"next_earnings": nxt.isoformat() if nxt else None, "checked_at": now.isoformat()}
        changed = True
        time.sleep(2)
    if changed:
        _write_earnings_schedule(sched)
    return sched


def _earnings_due_list():
    out = []
    try:
        sched = _read_earnings_schedule()
        for row in _catalog_rows():
            rec = _load_stock_record(row["ticker"])
            if not rec:
                continue
            due, reason = _earnings_due(rec, sched)
            if due:
                out.append({"ticker": row["ticker"], "reason": reason,
                            "next_earnings": (sched.get(row["ticker"]) or {}).get("next_earnings")})
    except Exception as e:
        logger.info(f"[Earnings] due-list failed: {e}")
    return out


def _earnings_due(data, sched):
    from datetime import datetime, timezone
    try:
        entry = (sched or {}).get((data.get("ticker") or "").upper()) or {}
        nxt = entry.get("next_earnings")
        if not nxt:
            return False, ""
        eday = datetime.fromisoformat(nxt).date()
        today = datetime.now(timezone.utc).date()
        if today < eday or (today - eday).days > EARNINGS_POST_WINDOW_DAYS:
            return False, ""
        gen_dt = _parse_record_date(data.get("generated_at") or "")
        if gen_dt and gen_dt.date() >= eday:
            return False, ""
        return True, f"earnings {eday.isoformat()} passed"
    except Exception:
        return False, ""


def _should_auto_update_record(data):
    try:
        from datetime import datetime, timezone
        gen_dt = _parse_record_date(data.get("generated_at") or "")
        age_days = (datetime.now(timezone.utc) - gen_dt).days if gen_dt else 999
        if age_days >= 85:
            return True, f"age {age_days}d >=85d"
        due, reason = _earnings_due(data, _read_earnings_schedule())
        if due:
            return True, reason
        return False, "fresh"
    except Exception as e:
        return False, str(e)


def _auto_update_worker():
    import time, threading
    from pathlib import Path
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    global auto_update_state
    _first_check_done = False
    while True:
        try:
            # first check 60s after boot, then hourly
            time.sleep(60 if not _first_check_done else 3600)
            _first_check_done = True
            try:
                auto_update_state["next_run"] = (_dt.now(_tz.utc) + _td(seconds=3600)).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass
            if auto_update_state["running"]:
                continue
            if not _auto_update_lock.acquire(blocking=False):
                continue
            rows = _catalog_rows()
            _refresh_earnings_schedule([r["ticker"] for r in rows])
            due = []
            for row in rows:
                rec = _load_stock_record(row["ticker"])
                if not rec:
                    continue
                need, reason = _should_auto_update_record(rec)
                if need:
                    due.append((row["ticker"], reason))
            if not due:
                auto_update_state["log"].append(f"{time.strftime('%Y-%m-%d %H:%M')} — no tickers due for quarterly refresh")
                auto_update_state["log"] = auto_update_state["log"][-50:]
                continue
            auto_update_state["running"] = True
            auto_update_state["queue"] = [t for t,_ in due]
            auto_update_state["log"].append(f"{time.strftime('%Y-%m-%d %H:%M')} — quarterly auto-update starting {len(due)} tickers: {', '.join([t for t,_ in due[:5]])}")
            logger.info(f"[AutoUpdate] Quarterly refresh for {len(due)} tickers")
            from stock_analyzer import analyze
            for ticker, reason in due:
                try:
                    auto_update_state["log"].append(f"  -> {ticker} ({reason})")
                    analyze(ticker)
                    time.sleep(90)  # respect rate limits
                except Exception as e:
                    auto_update_state["log"].append(f"  ! {ticker} failed: {e}")
                    logger.info(f"[AutoUpdate] {ticker} failed: {e}")
                    time.sleep(30)
            auto_update_state["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            auto_update_state["running"] = False
            auto_update_state["queue"] = []
            try:
                _auto_update_lock.release()
            except Exception:
                pass
        except Exception as e:
            logger.info(f"[AutoUpdate] worker error: {e}")
            auto_update_state["running"] = False
            try:
                _auto_update_lock.release()
            except Exception:
                pass
            time.sleep(3600)

def _start_auto_update_thread():
    import threading
    t = threading.Thread(target=_auto_update_worker, daemon=True)
    t.start()
    logger.info("[AutoUpdate] background quarterly updater started (first check in 60s, then hourly)")

@app.route("/api/system/auto-update/status")
def api_auto_update_status():
    return {
        "last_run": auto_update_state["last_run"],
        "next_run": auto_update_state.get("next_run"),
        "running": auto_update_state["running"],
        "queue": auto_update_state["queue"],
        "log": auto_update_state["log"][-20:],
        "total_tracked": len(_catalog_rows()),
        "quarterly_threshold_days": 85,
        "earnings_post_window_days": EARNINGS_POST_WINDOW_DAYS,
        "schedule_ttl_days": EARNINGS_SCHEDULE_TTL_DAYS,
        "live_prices": "poll /api/stocks/live-quotes every 30s frontend; ticker-tape cached 5m",
        "earnings_schedule": _read_earnings_schedule(),
        "earnings_due": _earnings_due_list(),
    }


@app.route("/api/system/earnings-schedule")
def api_earnings_schedule():
    sched = _read_earnings_schedule()
    return {"schedule": sched, "due": _earnings_due_list(), "post_window_days": EARNINGS_POST_WINDOW_DAYS}

@app.route("/api/system/earnings-schedule/refresh", methods=["POST"])
def api_earnings_schedule_refresh():
    body = request.get_json(silent=True) or {}
    force = bool(body.get("force")) if isinstance(body, dict) else False
    try:
        rows = _catalog_rows()
        tickers = [r["ticker"] for r in rows]
        if force:
            sched = _read_earnings_schedule()
            for tk in tickers:
                (sched.get(tk) or {}).pop("next_earnings", None)
            _write_earnings_schedule(sched)
        sched = _refresh_earnings_schedule(tickers)
        return {"status": "refreshed", "count": len(sched), "due": _earnings_due_list()}
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/api/system/auto-update/trigger", methods=["POST"])
def api_auto_update_trigger():
    tickers = request.get_json(silent=True) or {}
    # if specific tickers provided, use them; else due tickers (age>=85d or just past earnings)
    req_tickers = tickers.get("tickers") if isinstance(tickers, dict) else None
    force = bool(tickers.get("force")) if isinstance(tickers, dict) else False
    def _bg():
        import time
        from stock_analyzer import analyze
        global auto_update_state
        if not _auto_update_lock.acquire(blocking=False):
            auto_update_state["log"].append("manual trigger skipped: another update already running")
            return
        try:
            if auto_update_state["running"]:
                auto_update_state["log"].append("manual trigger skipped: already running")
                return
            auto_update_state["running"] = True
            try:
                if isinstance(req_tickers, list) and req_tickers:
                    targets = [tk.upper().strip() for tk in req_tickers[:10] if isinstance(tk, str) and is_valid_ticker(tk.upper().strip())]
                else:
                    _refresh_earnings_schedule([r["ticker"] for r in _catalog_rows()])
                    targets = []
                    for row in _catalog_rows():
                        rec = _load_stock_record(row["ticker"])
                        if not rec:
                            continue
                        need, _reason = _should_auto_update_record(rec)
                        if need or force:
                            targets.append(row["ticker"])
                    if not targets:
                        auto_update_state["log"].append(f"{time.strftime('%Y-%m-%d %H:%M')} - manual check: nothing due (all records fresh, no post-earnings pending)")
                        auto_update_state["log"] = auto_update_state["log"][-50:]
                        return
                auto_update_state["queue"] = targets
                auto_update_state["log"].append(f"{time.strftime('%Y-%m-%d %H:%M')} - manual update starting {len(targets)} tickers: {', '.join(targets[:8])}")
                for tk in targets:
                    try:
                        auto_update_state["log"].append(f"  -> {tk}")
                        analyze(tk)
                        time.sleep(60)
                    except Exception as e:
                        auto_update_state["log"].append(f"  ! {tk} failed: {e}")
                        logger.info(f"manual auto-update {tk} failed: {e}")
            finally:
                auto_update_state["running"] = False
                auto_update_state["queue"] = []
                import time as _t
                auto_update_state["last_run"] = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
        finally:
            try:
                _auto_update_lock.release()
            except Exception:
                pass
    import threading
    threading.Thread(target=_bg, daemon=True).start()
    return {"status": "triggered", "running": True}

def run_server(port=5001):
    """Start the local web server."""
    import logging
    port = int(os.environ.get("STOCKER_PORT", port))
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info(f"\n=======================================================")
    logger.info(f"   StockerAI Standalone Classic Terminal — Live + Quarterly Auto-Update")
    logger.info(f"   Live prices: polling /api/stocks/live-quotes, auto-refresh every earnings quarter")
    logger.info(f"   Starting server on http://127.0.0.1:{port}")
    logger.info(f"=======================================================\n")
    _start_auto_update_thread()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

if __name__ == "__main__":
    run_server()
