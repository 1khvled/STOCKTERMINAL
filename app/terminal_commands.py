import html
import os
import re
from datetime import datetime

OUTPUT_DIR = "output"
DATABASE_DIR = os.path.join(OUTPUT_DIR, "database")

_TICKER_RE = re.compile(r"^[A-Z0-9.\-\^]{1,12}$")

def _is_valid_ticker(t):
    return isinstance(t, str) and bool(_TICKER_RE.match(t.strip().upper())) and ".." not in t and not t.strip().startswith((".", "-"))

def _esc(s):
    return html.escape(str(s), quote=True)

def generate_ascii_chart(prices):
    if not prices or len(prices) == 0:
        return "No data available."
    try:
        vals = [float(p) for p in prices if p is not None]
    except Exception:
        return "No data available."
    if not vals:
        return "No data available."
    min_p = min(vals)
    max_p = max(vals)
    range_p = max_p - min_p if max_p > min_p else 1
    chars = " ▁▂▃▄▅▆█"
    chart_str = ""
    for p in vals:
        idx = int(((p - min_p) / range_p) * 7)
        idx = max(0, min(7, idx))
        chart_str += chars[idx]
    return f"""<span class="bbg-text-white">Min:</span> ${min_p:.2f}  |  <span class="bbg-text-white">Max:</span> ${max_p:.2f}
<div style="font-family: 'JetBrains Mono', monospace; font-size: 1.2rem; letter-spacing: 2px; color: var(--emerald); margin-top: 8px; margin-bottom: 8px;">{_esc(chart_str)}</div>"""

def handle_screen_command(query):
    # query already uppercased by caller
    if len(query) > 120:
        query = query[:120]
    try:
        import local_db
        stocks = local_db.catalog_rows()
    except Exception:
        return {"html": "<span class=\"bbg-text-red\">No database records found.</span>"}
    if not stocks:
        return {"html": "<span class=\"bbg-text-red\">No database records found.</span>"}
    tokens = [t for t in query.split() if t != "SCREEN"]
    # sanitize tokens: alphanumeric only, max 12 chars
    tokens = [re.sub(r"[^A-Z0-9]", "", t)[:12] for t in tokens]
    tokens = [t for t in tokens if t]
    if not tokens:
        tokens = []
    results = []
    for stock in stocks:
        ticker = str(stock.get("ticker", "")).upper()
        verdict = str(stock.get("verdict", "")).upper()
        sector = str(stock.get("sector", "")).upper()
        blob = f"{ticker} {verdict} {sector}"
        match = all(t in blob for t in tokens) if tokens else True
        if match:
            safe_ticker = _esc(ticker)
            safe_verdict = _esc(verdict)
            safe_sector = _esc(sector[:20])
            results.append(f'> <a href="javascript:void(0)" onclick="runTerminalCommand(\'{safe_ticker} DES\')" class="terminal-link bbg-text-cyan">{safe_ticker}</a> <span class="bbg-text-white">[{safe_verdict}]</span> {safe_sector}')
            if len(results) >= 50:
                break
    if not results:
        return {"html": f"<span class=\"bbg-text-red\">0 MATCHES FOUND FOR '{_esc(query)}'</span>"}
    return {"html": f"<div class=\"bbg-text-green\">SCREEN RESULTS ({len(results)} MATCHES):</div><br>" + "<br>".join(results)}

def process_command(raw_command):
    """Parses and executes a terminal command. Returns dict with 'html' or 'text'."""
    if not isinstance(raw_command, str):
        return {"html": "<span class=\"bbg-text-red\">Invalid command.</span>"}
    cmd_raw = raw_command.strip()
    if len(cmd_raw) > 64:
        return {"html": "<span class=\"bbg-text-red\">Command too long (max 64).</span>"}
    if not cmd_raw:
        return {"text": ""}
    cmd = cmd_raw.upper()
    parts = cmd.split()
    if not parts:
        return {"text": ""}
    base_cmd = parts[0]

    if base_cmd == "HELP":
        return {"html": """
<div class="bbg-text-cyan">AVAILABLE COMMANDS:</div>
  <a href="javascript:void(0)" onclick="runTerminalCommand('HELP')" class="bbg-text-white terminal-link">HELP</a>                 - Show this help menu
  <a href="javascript:void(0)" onclick="runTerminalCommand('CLEAR')" class="bbg-text-white terminal-link">CLEAR</a>                - Clear the terminal screen
  <span class="bbg-text-white">[TICKER]</span>             - Quick Company Snapshot (e.g., <a href="javascript:void(0)" onclick="runTerminalCommand('AAPL')" class="terminal-link" style="color:var(--bbg-cyan);">AAPL</a>)
  <span class="bbg-text-white">DES [TICKER]</span>         - Company Description (e.g., <a href="javascript:void(0)" onclick="runTerminalCommand('DES AAPL')" class="terminal-link" style="color:var(--bbg-cyan);">DES AAPL</a>)
  <span class="bbg-text-white">DCF [TICKER]</span>         - Discounted Cash Flow (e.g., <a href="javascript:void(0)" onclick="runTerminalCommand('DCF MSFT')" class="terminal-link" style="color:var(--bbg-cyan);">DCF MSFT</a>)
  <span class="bbg-text-white">COMP [TICKER]</span>        - Comparable Analysis (e.g., <a href="javascript:void(0)" onclick="runTerminalCommand('COMP TSLA')" class="terminal-link" style="color:var(--bbg-cyan);">COMP TSLA</a>)
  <span class="bbg-text-white">CHART [TICKER]</span>       - Text-based Price Chart (e.g., <a href="javascript:void(0)" onclick="runTerminalCommand('CHART NVDA')" class="terminal-link" style="color:var(--bbg-cyan);">CHART NVDA</a>)
  <span class="bbg-text-white">ER [TICKER]</span>          - Earnings Calendar (e.g., <a href="javascript:void(0)" onclick="runTerminalCommand('ER CRM')" class="terminal-link" style="color:var(--bbg-cyan);">ER CRM</a>)
  <span class="bbg-text-white">SCREEN [QUERY]</span>       - Search local DB (e.g., <a href="javascript:void(0)" onclick="runTerminalCommand('SCREEN BUY TECH')" class="terminal-link" style="color:var(--bbg-cyan);">SCREEN BUY TECH</a>)
  <span class="bbg-text-white">NEWS [TICKER]</span>        - AI News Impact Engine
  <span class="bbg-text-white">SEC [TICKER]</span>         - SEC Filing Intelligence
  <span class="bbg-text-white">LAB [TICKER]</span>         - Valuation Scenario Lab
  <span class="bbg-text-white">IC [TICKER]</span>          - AI Investment Committee
  <span class="bbg-text-white">FLAGS [TICKER]</span>       - AI Red Flag Detector
  <span class="bbg-text-white">PORT</span>                 - Portfolio Command Center
  <a href="javascript:void(0)" onclick="runTerminalCommand('PING')" class="bbg-text-white terminal-link">PING</a>                 - Check system latency
"""}

    if base_cmd == "CLEAR":
        return {"html": "", "clear": True}

    if base_cmd == "PING":
        return {"html": f"<span class=\"bbg-text-green\">PONG. System timestamp: {_esc(datetime.utcnow().isoformat())}Z</span>"}

    if base_cmd == "SCREEN":
        return handle_screen_command(cmd)

    # Redirect commands — validate ticker before redirect
    if base_cmd in ["NEWS", "IMPACT"] and len(parts) >= 2:
        ticker = parts[1].strip().upper()
        if not _is_valid_ticker(ticker):
            return {"html": f"<span class=\"bbg-text-red\">Invalid ticker '{_esc(ticker)}'.</span>"}
        return {"html": f"<span class='bbg-text-green'>Opening AI News Impact Engine for {_esc(ticker)}...</span>", "redirect": f"/news-impact?ticker={_esc(ticker)}"}

    if base_cmd in ["SEC", "FILINGS"] and len(parts) >= 2:
        ticker = parts[1].strip().upper()
        if not _is_valid_ticker(ticker):
            return {"html": f"<span class=\"bbg-text-red\">Invalid ticker '{_esc(ticker)}'.</span>"}
        return {"html": f"<span class='bbg-text-green'>Opening SEC Filing Intelligence for {_esc(ticker)}...</span>", "redirect": f"/filings?ticker={_esc(ticker)}"}

    if base_cmd in ["LAB", "SCENARIO", "SCENARIOS"] and len(parts) >= 2:
        ticker = parts[1].strip().upper()
        if not _is_valid_ticker(ticker):
            return {"html": f"<span class=\"bbg-text-red\">Invalid ticker '{_esc(ticker)}'.</span>"}
        return {"html": f"<span class='bbg-text-green'>Opening Valuation Scenario Lab for {_esc(ticker)}...</span>", "redirect": f"/scenario-lab?ticker={_esc(ticker)}"}

    if base_cmd in ["IC", "COMMITTEE"] and len(parts) >= 2:
        ticker = parts[1].strip().upper()
        if not _is_valid_ticker(ticker):
            return {"html": f"<span class=\"bbg-text-red\">Invalid ticker '{_esc(ticker)}'.</span>"}
        return {"html": f"<span class='bbg-text-green'>Opening AI Investment Committee for {_esc(ticker)}...</span>", "redirect": f"/committee?ticker={_esc(ticker)}"}

    if base_cmd in ["FLAGS", "RED", "RISK"] and len(parts) >= 2:
        ticker = parts[1].strip().upper()
        if not _is_valid_ticker(ticker):
            return {"html": f"<span class=\"bbg-text-red\">Invalid ticker '{_esc(ticker)}'.</span>"}
        return {"html": f"<span class='bbg-text-green'>Opening AI Red Flag Detector for {_esc(ticker)}...</span>", "redirect": f"/red-flags?ticker={_esc(ticker)}"}

    if base_cmd in ["PORT", "PORTFOLIO"]:
        return {"html": "<span class='bbg-text-green'>Opening Portfolio Command Center...</span>", "redirect": "/portfolio"}

    # TICKER / ACTION handling
    valid_actions = ["DES", "DCF", "COMP", "CHART", "ER", "NEWS", "SEC"]
    ticker = None
    action = None

    if len(parts) == 1 and base_cmd not in ["HELP", "PING", "CLEAR"]:
        ticker = parts[0]
        action = "DES"
    elif len(parts) >= 2:
        if parts[0] in valid_actions:
            action = parts[0]
            ticker = parts[1]
        elif parts[1] in valid_actions:
            ticker = parts[0]
            action = parts[1]
        else:
            ticker = parts[0]
            action = "DES"

    if ticker and action:
        ticker = ticker.strip().upper()
        if not _is_valid_ticker(ticker):
            return {"html": f"<span class=\"bbg-text-red\">Invalid ticker '{_esc(ticker)}'.</span>"}
        try:
            import local_db
            stock_data = local_db.load_stock_record(ticker)
        except Exception:
            stock_data = None
        if not stock_data:
            return {"html": f"<span class=\"bbg-text-red\">Error: Ticker {_esc(ticker)} not found in database. Run the pipeline first.</span>"}
        metrics = stock_data.get("key_metrics", {}) or {}

        if action == "DES":
            analysis = stock_data.get('analysis', {}) or {}
            desc = (
                stock_data.get('ai_analysis', {}).get('executive_summary')
                or analysis.get('executive_summary')
                or analysis.get('summary')
                or 'No summary available.'
            )
            desc = _esc(str(desc)[:800])
            return {"html": f"""
<div class="bbg-text-cyan">=== {_esc(ticker)} : {_esc(metrics.get('shortName', ticker))} ===</div>
<span class="bbg-text-white">Sector:</span> {_esc(metrics.get('sector', 'N/A'))}
<span class="bbg-text-white">Price:</span> ${_esc(metrics.get('current_price', 'N/A'))}
<span class="bbg-text-white">Market Cap:</span> {_esc(metrics.get('marketCap', 'N/A'))}
<span class="bbg-text-white">P/E (TTM):</span> {_esc(metrics.get('trailingPE', 'N/A'))}
<span class="bbg-text-white">EPS (Fwd):</span> {_esc(metrics.get('forwardEps', 'N/A'))}

<div class="bbg-text-green" style="margin-top:8px;">EXECUTIVE SUMMARY:</div>
{desc}
"""}

        if action == "DCF":
            dcf = stock_data.get('dcf_data', {}) or {}
            if not dcf:
                return {"html": f"<span class=\"bbg-text-red\">No DCF data available for {_esc(ticker)}.</span>"}
            try:
                implied = float(dcf.get('implied_price', 0) or 0)
                curr = float(metrics.get('current_price', 0) or 1)
            except Exception:
                implied, curr = 0, 1
            upside = ((implied - curr) / curr) * 100 if curr else 0
            color = "bbg-text-green" if upside > 0 else "bbg-text-red"
            return {"html": f"""
<div class="bbg-text-cyan">=== {_esc(ticker)} : DCF VALUATION ===</div>
<span class="bbg-text-white">Valuation Basis:</span> {_esc(dcf.get('valuation_basis', 'N/A'))}
<span class="bbg-text-white">Current Price:</span> ${curr:.2f}
<span class="bbg-text-white">Implied Value:</span> ${implied:.2f}
<span class="bbg-text-white">Upside/Downside:</span> <span class="{color}">{upside:+.2f}%</span>

<span class="bbg-text-white">WACC Used:</span> {_esc(dcf.get('wacc_used', 'N/A'))}%
<span class="bbg-text-white">Terminal Growth:</span> {_esc(dcf.get('terminal_growth', 'N/A'))}%
"""}

        if action == "COMP":
            cca = stock_data.get('cca_data', {}) or {}
            if not cca:
                return {"html": f"<span class=\"bbg-text-red\">No Comparable Analysis data available for {_esc(ticker)}.</span>"}
            return {"html": f"""
<div class="bbg-text-cyan">=== {_esc(ticker)} : COMPARABLE ANALYSIS ===</div>
<span class="bbg-text-white">Target P/E:</span> {_esc(cca.get('target_pe', 'N/A'))}  |  <span class="bbg-text-white">Peer Median P/E:</span> {_esc(cca.get('peer_median_pe', 'N/A'))}
<span class="bbg-text-white">Implied P/E Price:</span> ${_esc(cca.get('implied_pe_price', 'N/A'))}

<span class="bbg-text-white">Target P/S:</span> {_esc(cca.get('target_ps', 'N/A'))}  |  <span class="bbg-text-white">Peer Median P/S:</span> {_esc(cca.get('peer_median_ps', 'N/A'))}
<span class="bbg-text-white">Implied P/S Price:</span> ${_esc(cca.get('implied_ps_price', 'N/A'))}

<span class="bbg-text-white">Target P/B:</span> {_esc(cca.get('target_pb', 'N/A'))}  |  <span class="bbg-text-white">Peer Median P/B:</span> {_esc(cca.get('peer_median_pb', 'N/A'))}
<span class="bbg-text-white">Implied P/B Price:</span> ${_esc(cca.get('implied_pb_price', 'N/A'))}
"""}

        if action == "CHART":
            if os.environ.get("STOCKER_TEST_MODE") == "1":
                return {"html": f"<div class=\"bbg-text-cyan\">=== {_esc(ticker)} : 3-MONTH PRICE CHART ===</div>\n{generate_ascii_chart([100, 102, 101, 105, 103])}<br><span class=\"bbg-text-muted\">(mock in test mode)</span>"}
            try:
                import yfinance as yf
                hist = yf.Ticker(ticker).history(period="3mo")
                prices = hist['Close'].dropna().tolist() if not hist.empty else []
                chart_html = generate_ascii_chart(prices)
                return {"html": f"<div class=\"bbg-text-cyan\">=== {_esc(ticker)} : 3-MONTH PRICE CHART ===</div>\n{chart_html}"}
            except Exception as e:
                return {"html": f"<span class=\"bbg-text-red\">Failed to generate chart: {_esc(str(e))}</span>"}

        if action == "ER":
            try:
                import yfinance as yf
                cal = yf.Ticker(ticker).calendar
                if cal is None or (isinstance(cal, dict) and not cal):
                    return {"html": f"<span class=\"bbg-text-red\">No earnings calendar data found for {_esc(ticker)}.</span>"}
                # yfinance calendar is often dict
                if isinstance(cal, dict):
                    er_dates = cal.get('Earnings Date') or cal.get('Earnings Dates') or []
                    if not isinstance(er_dates, (list, tuple)):
                        er_dates = [er_dates] if er_dates else []
                    er_date_str = ", ".join([d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else _esc(str(d)) for d in er_dates]) if er_dates else "N/A"
                    return {"html": f"""
<div class="bbg-text-cyan">=== {_esc(ticker)} : EARNINGS CALENDAR ===</div>
<span class="bbg-text-white">Next Earnings Date(s):</span> <span class="bbg-text-green\">{_esc(er_date_str)}</span>
<span class="bbg-text-white">Earnings Estimate (Avg):</span> {_esc(cal.get('Earnings Average', 'N/A'))}
<span class="bbg-text-white">Revenue Estimate (Avg):</span> {_esc(cal.get('Revenue Average', 'N/A'))}
<span class="bbg-text-white">Ex-Dividend Date:</span> {_esc(cal.get('Ex-Dividend Date', 'N/A'))}
"""}
                return {"html": f"<span class=\"bbg-text-red\">No earnings calendar data found for {_esc(ticker)}.</span>"}
            except Exception as e:
                return {"html": f"<span class=\"bbg-text-red\">Failed to fetch earnings calendar: {_esc(str(e))}</span>"}

        return {"html": f"<span class=\"bbg-text-red\">Invalid action '{_esc(action)}' for ticker '{_esc(ticker)}'. Try DES, DCF, or COMP.</span>"}

    return {"html": f"<span class=\"bbg-text-red\">Unknown command: '{_esc(raw_command)}'. Type HELP for options.</span>"}
