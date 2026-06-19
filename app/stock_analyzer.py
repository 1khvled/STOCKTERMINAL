"""
AI Stock Analyzer -- Main Entry Point
Type a ticker, get: Excel model + PDF report + Interactive HTML dashboard
Powered by Yahoo Finance data + Groq AI (free)
"""
import sys
import os
import time
import io
from pathlib import Path

# Fix Windows encoding issues
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from config import OUTPUT_DIR, validate_config
from data_fetcher import fetch_stock_data
from ai_engine import generate_analysis
from dashboard_generator import generate_dashboard, _df_to_json_ready
from excel_generator import generate_excel_model
from chart_generator import generate_all_charts
from pdf_generator import generate_pdf


BANNER = r"""
   _____ __             __       ___                __
  / ___// /_____  _____/ /__    /   |  ____  ____ _/ /_  ______  ___  _____
  \__ \/ __/ __ \/ ___/ //_/   / /| | / __ \/ __ `/ / / / /_  / / _ \/ ___/
 ___/ / /_/ /_/ / /__/ ,<     / ___ |/ / / / /_/ / / /_/ / / /_/  __/ /
/____/\__/\____/\___/_/|_|   /_/  |_/_/ /_/\__,_/_/\__, / /___/\___/_/
                                                   /____/
  +---------------------------------------------------------------+
  |  AI-Powered Stock Analysis  |  Yahoo Finance + Groq (Free AI) |
  |  Generates: Premium Dark-Themed Stock Terminal HTML Dashboard |
  |  SaaS Web Server Portal:   Run with '--server' command flag   |
  +---------------------------------------------------------------+
"""


def serialize_stock_data(stock_data, analysis):
    """Convert pandas DataFrames and other non-JSON objects into serializable types."""
    import pandas as pd
    
    def handle_val(val):
        if isinstance(val, pd.DataFrame):
            # Convert DataFrame to a nested dict orientation (records or index-split)
            res = {}
            for col in val.columns:
                col_name = col.strftime('%Y-%m-%d') if hasattr(col, 'strftime') else str(col)
                res[col_name] = {}
                for idx in val.index:
                    idx_name = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
                    v = val.loc[idx, col]
                    res[col_name][idx_name] = None if pd.isna(v) else float(v) if isinstance(v, (int, float, complex)) else str(v)
            return res
        elif isinstance(val, pd.Series):
            return {
                (idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)): (None if pd.isna(v) else float(v) if isinstance(v, (int, float, complex)) else str(v))
                for idx, v in val.items()
            }
        elif isinstance(val, dict):
            return {k: handle_val(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [handle_val(v) for v in val]
        elif hasattr(val, 'to_dict'):
            try:
                return val.to_dict()
            except Exception:
                pass
        return val

    # Extract compact weekly close price history for charting
    history_1y = stock_data.get("history_1y")
    price_history = None
    if history_1y is not None and not history_1y.empty and "Close" in history_1y.columns:
        try:
            weekly_close = history_1y["Close"].resample('W').last().dropna()
            price_history = {
                date.strftime('%Y-%m-%d'): float(price)
                for date, price in weekly_close.items()
            }
        except Exception as e:
            print(f"  [!] Failed to resample weekly close history: {e}")

    serialized = {
        "ticker": stock_data.get("ticker", ""),
        "company_name": stock_data.get("company_name", ""),
        "key_metrics": handle_val(stock_data.get("key_metrics", {})),
        "dcf_data": handle_val(stock_data.get("dcf_data", {})),
        "financial_scores": handle_val(stock_data.get("financial_scores", {})),
        "notion_data": handle_val(stock_data.get("notion_data", {})),
        "advanced_models": handle_val(stock_data.get("advanced_models", {})),
        "price_history_compact": price_history,
        "q_financials": _df_to_json_ready(stock_data.get("quarterly_financials")),
        "q_balance_sheet": _df_to_json_ready(stock_data.get("quarterly_balance_sheet")),
        "q_cashflow": _df_to_json_ready(stock_data.get("quarterly_cashflow")),
        "analysis": analysis,
        "generated_at": pd.Timestamp.now().isoformat()
    }
    return serialized


def print_terminal_quant_briefing(stock_data, analysis):
    """Print an institutional-grade, retro-futuristic Bloomberg-style quantitative briefing to stdout."""
    m = stock_data.get("key_metrics", {})
    dcf = stock_data.get("dcf_data") or {}
    scores = stock_data.get("financial_scores", {})
    dp = scores.get("dupont") or {}
    val_assess = analysis.get("valuation_assessment") or {}
    
    # Inline clean helpers
    def _fmt_n(v, is_currency=True):
        if v is None: return "N/A"
        prefix = "$" if is_currency else ""
        try:
            val = float(v)
            if abs(val) >= 1e12: return f"{prefix}{val/1e12:.2f}T"
            if abs(val) >= 1e9: return f"{prefix}{val/1e9:.2f}B"
            if abs(val) >= 1e6: return f"{prefix}{val/1e6:.2f}M"
            return f"{prefix}{val:,.2f}"
        except (ValueError, TypeError):
            return str(v)
            
    def _fmt_p(v, is_already_scaled=False):
        if v is None: return "N/A"
        try:
            val = float(v)
            if not is_already_scaled and abs(val) < 1.0 and val != 0:
                val = val * 100.0
            return f"{val:+.2f}%" if val != 0 else "0.00%"
        except (ValueError, TypeError):
            return str(v)
            
    def _fmt_x(v):
        if v is None: return "N/A"
        try:
            return f"{float(v):.2f}x"
        except (ValueError, TypeError):
            return str(v)

    # Ingest data fields
    rev = m.get("totalRevenue")
    
    rev_g_val = m.get("revenueGrowth_pct")
    rev_g_scaled = True
    if rev_g_val is None:
        rev_g_val = m.get("revenueGrowth")
        rev_g_scaled = False

    ebitda = m.get("ebitda")
    
    gross_val = m.get("grossMargins_pct")
    gross_scaled = True
    if gross_val is None:
        gross_val = m.get("grossMargins")
        gross_scaled = False

    op_val = m.get("operatingMargins_pct")
    op_scaled = True
    if op_val is None:
        op_val = m.get("operatingMargins")
        op_scaled = False

    net_val = m.get("profitMargins_pct")
    net_scaled = True
    if net_val is None:
        net_val = m.get("profitMargins")
        net_scaled = False
    
    cash = m.get("totalCash")
    debt = m.get("totalDebt")
    net_debt = None
    if debt is not None and cash is not None:
        net_debt = debt - cash
    de_val = m.get("debtToEquity")
    curr_r = m.get("currentRatio")
    quick_r = m.get("quickRatio")
    
    z_score = scores.get("altman_z")
    z_label = scores.get("altman_z_label") or "N/A"
    f_score = scores.get("piotroski_f")
    
    dp_margin = dp.get("net_margin")
    dp_turn = dp.get("asset_turnover")
    dp_lev = dp.get("equity_multiplier")
    dp_roe = dp.get("roe_computed")
    
    spot = m.get("current_price") or 0.0
    dcf_val = dcf.get("implied_price") or val_assess.get("fair_value_mid") or 0.0
    analyst_target = m.get("targetMeanPrice")
    reg_val = (stock_data.get("advanced_models") or {}).get("historical_regression", {}).get("fair_price")
    grade = val_assess.get("valuation_grade") or "N/A"
    
    upside = 0.0
    if spot > 0:
        upside = ((dcf_val - spot) / spot) * 100.0

    print("\n" + "═" * 63)
    print(" 📊 STOCKERAI PORTFOLIO BRIEFING - QUANTITATIVE VITAL STATS")
    print("" + "═" * 63)
    
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│                 INCOME STATEMENT HIGHLIGHTS                 │")
    print("├──────────────────────────────┬──────────────────────────────┤")
    print(f"│ Total Revenue: {f'{_fmt_n(rev)}':<13} │ YoY Rev Growth: {f'{_fmt_p(rev_g_val, rev_g_scaled)}':<12} │")
    print(f"│ EBITDA:        {f'{_fmt_n(ebitda)}':<13} │ Gross Margin:   {f'{_fmt_p(gross_val, gross_scaled)}':<12} │")
    print(f"│ Operating Margin: {f'{_fmt_p(op_val, op_scaled)}':<9} │ Net Profit Margin: {f'{_fmt_p(net_val, net_scaled)}':<9} │")
    print("└──────────────────────────────┴──────────────────────────────┘")
    
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│              BALANCE SHEET & CAPITAL STRUCTURE              │")
    print("├──────────────────────────────┬──────────────────────────────┤")
    print(f"│ Total Cash:    {f'{_fmt_n(cash)}':<13} │ Total Debt:     {f'{_fmt_n(debt)}':<12} │")
    print(f"│ Net Debt:      {f'{_fmt_n(net_debt)}':<13} │ Debt/Equity:    {f'{_fmt_p(de_val, True)}':<12} │")
    print(f"│ Current Ratio: {f'{_fmt_x(curr_r)}':<13} │ Quick Ratio:    {f'{_fmt_x(quick_r)}':<12} │")
    print("└──────────────────────────────┴──────────────────────────────┘")
    
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│              ACCOUNTING SCORES & DECOMPOSITION              │")
    print("├──────────────────────────────┬──────────────────────────────┤")
    z_str = f"{z_score:.2f} ({z_label})" if isinstance(z_score, (int, float)) else "N/A"
    f_str = f"{f_score}/9" if f_score is not None else "N/A"
    print(f"│ Altman Z-Score: {f'{z_str}':<12} │ Piotroski F-Score: {f'{f_str}':<10} │")
    print(f"│ DuPont Margin:  {f'{_fmt_p(dp_margin, True)}':<12} │ DuPont Asset Turn: {f'{_fmt_x(dp_turn)}':<10} │")
    print(f"│ DuPont Leverage: {f'{_fmt_x(dp_lev)}':<11} │ Computed DuPont ROE: {f'{_fmt_p(dp_roe, True)}':<9} │")
    print("└──────────────────────────────┴──────────────────────────────┘")
    
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│                      VALUATION ANCHORS                      │")
    print("├──────────────────────────────┬──────────────────────────────┤")
    print(f"│ Spot Stock Price: {_fmt_n(spot):<10} │ DCF Fair Value: {_fmt_n(dcf_val):<12} │")
    print(f"│ Analyst Target:   {_fmt_n(analyst_target):<10} │ Regression Trend: {_fmt_n(reg_val):<10} │")
    print(f"│ Valuation Grade:  {grade:<10} │ DCF Implied Upside: {f'{upside:+.2f}%':<9} │")
    print("└──────────────────────────────┴──────────────────────────────┘\n")


def analyze(ticker_symbol):
    """Run the full analysis pipeline for a ticker."""
    ticker = ticker_symbol.strip().upper()
    if not ticker:
        print("❌ No ticker provided.")
        return None

    # Create output directory
    ticker_dir = OUTPUT_DIR / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    stock_data = {}
    analysis = {}
    html_success = False
    pdf_success = False
    excel_success = False
    elapsed = 0

    try:
        # Step 1: Fetch data
        print(f"\n[1/5] 📡 Fetching data from Yahoo Finance...")
        try:
            stock_data = fetch_stock_data(ticker, raw_output_dir=ticker_dir / "raw")
        except Exception as e:
            print(f"❌ Failed to fetch data for '{ticker}': {e}")
            print("   Make sure the ticker symbol is valid (e.g., AAPL, TSLA, MSFT)")
            return None

        if not stock_data or stock_data.get("history_1y") is None or stock_data["history_1y"].empty:
            print(f"❌ No price data found for '{ticker}'. Is this a valid ticker?")
            return None

        # Step 1b: Fetch Notion data if integration is configured
        try:
            from notion_integrator import fetch_notion_data
            notion_data = fetch_notion_data(ticker)
            if notion_data:
                stock_data["notion_data"] = notion_data
                print(f"  ✅ Linked to Notion company hub page: '{notion_data['company_title']}'")
            else:
                stock_data["notion_data"] = None
        except Exception as ne:
            print(f"  ⚠️ Warning: Failed to query Notion integration: {ne}")
            stock_data["notion_data"] = None

        # Step 2: AI Analysis
        print(f"\n[2/5] 🤖 Generating AI analysis via Groq...")
        analysis = generate_analysis(stock_data)
        stock_data["analysis"] = analysis
        print(f"  ✅ AI Verdict: {analysis.get('verdict', 'N/A')} (Confidence: {analysis.get('verdict_confidence', 'N/A')}%)")

        # Step 2b: Print terminal quantitative briefing
        try:
            print_terminal_quant_briefing(stock_data, analysis)
        except Exception as qe:
            print(f"  ⚠️ Warning: Failed to render terminal quant briefing: {qe}")

        # Step 3: PDF Report (Skipped for efficiency)
        print(f"\n[3/5] 📈 Skipping Matplotlib charts & PDF report generation (optimized)...")
        pdf_success = False

        # Step 4: HTML dashboard (main deliverable)
        print(f"\n[4/5] 🌐 Generating full interactive dashboard...")
        html_path = ticker_dir / f"{ticker}_dashboard.html"
        html_success = False
        try:
            generate_dashboard(stock_data, analysis, html_path)
            print(f"  ✅ Saved: {html_path}")
            html_success = True
        except PermissionError:
            print(f"  ❌ Permission Denied: Could not write HTML. Please close '{html_path.name}' if it is open in a browser and try again.")
        except Exception as e:
            print(f"  ❌ Failed to generate HTML Dashboard: {e}")

        # Step 5: Excel Model (Re-enabled with dynamic formulas)
        print(f"\n[5/5] 📊 Generating dynamic Excel Financial Model...")
        excel_success = False
        try:
            generate_excel_model(ticker, stock_data, ticker_dir, analysis)
            excel_success = True
            print(f"  ✅ Saved: {ticker_dir / f'{ticker}_Financial_Model.xlsx'}")
        except PermissionError:
            print(f"  ❌ Permission Denied: Could not write Excel file. Please close it if it is open in Excel.")
        except Exception as e:
            print(f"  ❌ Failed to generate Excel Model: {e}")

    except Exception as e:
        print(f"\n❌ Unhandled error during analysis pipeline for {ticker}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        elapsed = time.time() - start_time
        # Step 6: Database Serialization (Local JSON Database)
        if stock_data:
            print(f"\n[6/6] 🗄️ Saving consolidated records to local database...")
            db_dir = OUTPUT_DIR / "database"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / f"{ticker}.json"
            
            import json
            try:
                serialized = serialize_stock_data(stock_data, analysis)
                with open(db_path, "w", encoding="utf-8") as f:
                    json.dump(serialized, f, indent=2, ensure_ascii=False)
                print(f"  ✅ Saved database record: {db_path}")
            except Exception as e:
                print(f"  ❌ Failed to save database record: {e}")

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    ✅ ANALYSIS COMPLETE                      ║
╠══════════════════════════════════════════════════════════════╣
║  Ticker:     {ticker:<47}║
║  Company:    {stock_data.get('company_name', 'N/A')[:47]:<47}║
║  Verdict:    {analysis.get('verdict','N/A'):<47}║
║  Time:       {elapsed:.1f}s{' ' * (45 - len(f'{elapsed:.1f}s'))}║
╠══════════════════════════════════════════════════════════════╣
║  🌐 HTML:    {"SAVED" if html_success else "SKIPPED/LOCKED":<47}║
║  📄 PDF:     {"SAVED" if pdf_success else "SKIPPED/DIVERTED":<47}║
║  📊 EXCEL:   {"SAVED" if excel_success else "SKIPPED/DIVERTED":<47}║
╚══════════════════════════════════════════════════════════════╝
""")

    return ticker_dir, stock_data, analysis


def main():
    print(BANNER)

    # If --server argument is provided, launch the web server and exit
    if len(sys.argv) > 1 and any(arg.lower() in ["--server", "-server", "server"] for arg in sys.argv[1:]):
        try:
            from server import run_server
            run_server()
        except KeyboardInterrupt:
            print("\n👋 Server stopped.")
        except Exception as e:
            print(f"❌ Error starting server: {e}")
        return

    # Validate config
    if not validate_config():
        sys.exit(1)

    # If CLI arguments are provided, analyze them and exit
    if len(sys.argv) > 1:
        ticker_input = ",".join(sys.argv[1:])
        tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]
        analyzed_list = []
        for t in tickers:
            try:
                res = analyze(t)
                if res and isinstance(res, tuple):
                    analyzed_list.append({"data": res[1], "analysis": res[2]})
            except KeyboardInterrupt:
                print("\n\n⚠️ Analysis interrupted.")
                break
            except Exception as e:
                print(f"\n❌ Error analyzing {t}: {e}")
                import traceback
                traceback.print_exc()
        
        if len(analyzed_list) > 1:
            try:
                from comparison_generator import generate_comparison_dashboard
                comp_path = OUTPUT_DIR / "comparison_dashboard.html"
                generate_comparison_dashboard(analyzed_list, comp_path)
                print(f"\n✨ MULTI-TICKER COMPARISON DASHBOARD GENERATED!")
                print(f"  ✅ Saved: {comp_path}\n")
            except Exception as e:
                print(f"\n❌ Failed to generate comparison dashboard: {e}")
        return

    # Interactive loop
    while True:
        print("─" * 60)
        ticker = input("\n🔍 Enter ticker symbol (or 'quit' to exit): ").strip()

        if ticker.lower() in ["quit", "exit", "q"]:
            print("\n👋 Goodbye! Happy investing.\n")
            break

        if not ticker:
            continue

        # Support multiple tickers separated by comma
        tickers = [t.strip() for t in ticker.split(",") if t.strip()]
        analyzed_list = []

        for t in tickers:
            try:
                res = analyze(t)
                if res and isinstance(res, tuple):
                    analyzed_list.append({"data": res[1], "analysis": res[2]})
            except KeyboardInterrupt:
                print("\n\n⚠️ Analysis interrupted.")
                break
            except Exception as e:
                print(f"\n❌ Error analyzing {t}: {e}")
                import traceback
                traceback.print_exc()

        if len(analyzed_list) > 1:
            try:
                from comparison_generator import generate_comparison_dashboard
                comp_path = OUTPUT_DIR / "comparison_dashboard.html"
                generate_comparison_dashboard(analyzed_list, comp_path)
                print(f"\n✨ MULTI-TICKER COMPARISON DASHBOARD GENERATED!")
                print(f"  ✅ Saved: {comp_path}\n")
            except Exception as e:
                print(f"\n❌ Failed to generate comparison dashboard: {e}")


if __name__ == "__main__":
    main()
