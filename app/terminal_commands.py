import json
import os
import yfinance as yf
from datetime import datetime

OUTPUT_DIR = "output"
DATABASE_DIR = os.path.join(OUTPUT_DIR, "database")

def generate_ascii_chart(prices):
    if not prices or len(prices) == 0:
        return "No data available."
    min_p = min(prices)
    max_p = max(prices)
    range_p = max_p - min_p if max_p > min_p else 1
    chars = " ▁▂▃▄▅▆█"
    
    chart_str = ""
    for p in prices:
        idx = int(((p - min_p) / range_p) * 7)
        chart_str += chars[idx]
        
    return f"""<span class="bbg-text-white">Min:</span> ${min_p:.2f}  |  <span class="bbg-text-white">Max:</span> ${max_p:.2f}
<div style="font-family: 'JetBrains Mono', monospace; font-size: 1.2rem; letter-spacing: 2px; color: var(--emerald); margin-top: 8px; margin-bottom: 8px;">{chart_str}</div>"""

def handle_screen_command(query):
    query = query.upper()
    db_dir = DATABASE_DIR
    if not os.path.exists(db_dir):
        return {"html": "<span class=\"bbg-text-red\">No database found.</span>"}
        
    results = []
    import glob
    for fpath in glob.glob(os.path.join(db_dir, "*.json")):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        ticker = data.get("ticker", "")
        analysis = data.get("analysis", {})
        verdict = analysis.get("verdict", "").upper()
        metrics = data.get("key_metrics", {})
        sector = str(metrics.get("sector", "")).upper()
        
        # Build a searchable text blob
        blob = f"{ticker} {verdict} {sector}"
        
        # Simple match: all tokens in query must be in blob
        tokens = [t for t in query.split() if t != "SCREEN"]
        match = True
        for t in tokens:
            if t not in blob:
                match = False
                break
                
        if match:
            results.append(f'> <a href="javascript:void(0)" onclick="runTerminalCommand(\'{ticker} DES\')" class="terminal-link bbg-text-cyan">{ticker}</a> <span class="bbg-text-white">[{verdict}]</span> {sector[:20]}')
            
    if not results:
        return {"html": f"<span class=\"bbg-text-red\">0 MATCHES FOUND FOR '{query}'</span>"}
    return {"html": f"<div class=\"bbg-text-green\">SCREEN RESULTS ({len(results)} MATCHES):</div><br>" + "<br>".join(results)}

def process_command(raw_command):
    """
    Parses and executes a terminal command.
    Returns a dict with 'html' or 'text' keys.
    """
    cmd = raw_command.strip().upper()
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

    if base_cmd == "PING":
        return {"html": f"<span class=\"bbg-text-green\">PONG. System timestamp: {datetime.utcnow().isoformat()}Z</span>"}

    if base_cmd == "SCREEN":
        return handle_screen_command(cmd)

    if base_cmd in ["NEWS", "IMPACT"] and len(parts) >= 2:
        ticker = parts[1]
        return {"html": f"<span class='bbg-text-green'>Opening AI News Impact Engine for {ticker}...</span><script>window.location.href='/news-impact?ticker={ticker}'</script>"}

    if base_cmd in ["SEC", "FILINGS"] and len(parts) >= 2:
        ticker = parts[1]
        return {"html": f"<span class='bbg-text-green'>Opening SEC Filing Intelligence for {ticker}...</span><script>window.location.href='/filings?ticker={ticker}'</script>"}

    if base_cmd in ["LAB", "SCENARIO", "SCENARIOS"] and len(parts) >= 2:
        ticker = parts[1]
        return {"html": f"<span class='bbg-text-green'>Opening Valuation Scenario Lab for {ticker}...</span><script>window.location.href='/scenario-lab?ticker={ticker}'</script>"}

    if base_cmd in ["IC", "COMMITTEE"] and len(parts) >= 2:
        ticker = parts[1]
        return {"html": f"<span class='bbg-text-green'>Opening AI Investment Committee for {ticker}...</span><script>window.location.href='/committee?ticker={ticker}'</script>"}

    if base_cmd in ["FLAGS", "RED", "RISK"] and len(parts) >= 2:
        ticker = parts[1]
        return {"html": f"<span class='bbg-text-green'>Opening AI Red Flag Detector for {ticker}...</span><script>window.location.href='/red-flags?ticker={ticker}'</script>"}

    if base_cmd in ["PORT", "PORTFOLIO"]:
        return {"html": "<span class='bbg-text-green'>Opening Portfolio Command Center...</span><script>window.location.href='/portfolio'</script>"}

    # Handle TICKER only, ACTION TICKER, or TICKER ACTION
    valid_actions = ["DES", "DCF", "COMP", "CHART", "ER", "NEWS", "SEC"]
    ticker = None
    action = None

    if len(parts) == 1 and base_cmd not in ["HELP", "PING", "CLEAR"]:
        ticker = parts[0]
        action = "DES"  # Default to snapshot
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
        # Check if we have the ticker analyzed locally
        json_path = os.path.join(DATABASE_DIR, f"{ticker}.json")
        if not os.path.exists(json_path):
            return {"html": f"<span class=\"bbg-text-red\">Error: Ticker {ticker} not found in local database. Run the pipeline first.</span>"}

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                stock_data = json.load(f)
        except Exception as e:
            return {"html": f"<span class=\"bbg-text-red\">Error reading data for {ticker}: {e}</span>"}
            
        metrics = stock_data.get("key_metrics", {})
        
        if action == "DES":
            analysis = stock_data.get('analysis', {})
            desc = (
                stock_data.get('ai_analysis', {}).get('executive_summary')
                or analysis.get('executive_summary')
                or analysis.get('summary')
                or 'No summary available.'
            )
            return {"html": f"""
<div class="bbg-text-cyan">=== {ticker} : {metrics.get('shortName', ticker)} ===</div>
<span class="bbg-text-white">Sector:</span> {metrics.get('sector', 'N/A')}
<span class="bbg-text-white">Price:</span> ${metrics.get('current_price', 'N/A')}
<span class="bbg-text-white">Market Cap:</span> {metrics.get('marketCap', 'N/A')}
<span class="bbg-text-white">P/E (TTM):</span> {metrics.get('trailingPE', 'N/A')}
<span class="bbg-text-white">EPS (Fwd):</span> {metrics.get('forwardEps', 'N/A')}

<div class="bbg-text-green" style="margin-top:8px;">EXECUTIVE SUMMARY:</div>
{desc}
"""}

        if action == "DCF":
            dcf = stock_data.get('dcf_data', {})
            if not dcf:
                return {"html": f"<span class=\"bbg-text-red\">No DCF data available for {ticker}.</span>"}
            
            implied = dcf.get('implied_price', 0)
            curr = metrics.get('current_price', 1)
            upside = ((implied - curr) / curr) * 100 if curr else 0
            
            color = "bbg-text-green" if upside > 0 else "bbg-text-red"
            
            return {"html": f"""
<div class="bbg-text-cyan">=== {ticker} : DCF VALUATION ===</div>
<span class="bbg-text-white">Valuation Basis:</span> {dcf.get('valuation_basis', 'N/A')}
<span class="bbg-text-white">Current Price:</span> ${curr}
<span class="bbg-text-white">Implied Value:</span> ${implied}
<span class="bbg-text-white">Upside/Downside:</span> <span class="{color}">{upside:+.2f}%</span>

<span class="bbg-text-white">WACC Used:</span> {dcf.get('wacc_used', 'N/A')}%
<span class="bbg-text-white">Terminal Growth:</span> {dcf.get('terminal_growth', 'N/A')}%
"""}

        if action == "COMP":
            cca = stock_data.get('cca_data', {})
            if not cca:
                return {"html": f"<span class=\"bbg-text-red\">No Comparable Analysis data available for {ticker}.</span>"}
            
            return {"html": f"""
<div class="bbg-text-cyan">=== {ticker} : COMPARABLE ANALYSIS ===</div>
<span class="bbg-text-white">Target P/E:</span> {cca.get('target_pe', 'N/A')}  |  <span class="bbg-text-white">Peer Median P/E:</span> {cca.get('peer_median_pe', 'N/A')}
<span class="bbg-text-white">Implied P/E Price:</span> ${cca.get('implied_pe_price', 'N/A')}

<span class="bbg-text-white">Target P/S:</span> {cca.get('target_ps', 'N/A')}  |  <span class="bbg-text-white">Peer Median P/S:</span> {cca.get('peer_median_ps', 'N/A')}
<span class="bbg-text-white">Implied P/S Price:</span> ${cca.get('implied_ps_price', 'N/A')}

<span class="bbg-text-white">Target P/B:</span> {cca.get('target_pb', 'N/A')}  |  <span class="bbg-text-white">Peer Median P/B:</span> {cca.get('peer_median_pb', 'N/A')}
<span class="bbg-text-white">Implied P/B Price:</span> ${cca.get('implied_pb_price', 'N/A')}
"""}

        if action == "CHART":
            try:
                hist = yf.Ticker(ticker).history(period="3mo")
                prices = hist['Close'].dropna().tolist()
                chart_html = generate_ascii_chart(prices)
                return {"html": f"<div class=\"bbg-text-cyan\">=== {ticker} : 3-MONTH PRICE CHART ===</div>\n{chart_html}"}
            except Exception as e:
                return {"html": f"<span class=\"bbg-text-red\">Failed to generate chart: {e}</span>"}

        if action == "ER":
            try:
                cal = yf.Ticker(ticker).calendar
                if not cal:
                    return {"html": f"<span class=\"bbg-text-red\">No earnings calendar data found for {ticker}.</span>"}
                
                er_dates = cal.get('Earnings Date', [])
                er_date_str = ", ".join([d.strftime('%Y-%m-%d') for d in er_dates]) if er_dates else "N/A"
                
                return {"html": f"""
<div class="bbg-text-cyan">=== {ticker} : EARNINGS CALENDAR ===</div>
<span class="bbg-text-white">Next Earnings Date(s):</span> <span class="bbg-text-green">{er_date_str}</span>
<span class="bbg-text-white">Earnings Estimate (Avg):</span> {cal.get('Earnings Average', 'N/A')}
<span class="bbg-text-white">Revenue Estimate (Avg):</span> {cal.get('Revenue Average', 'N/A')}
<span class="bbg-text-white">Ex-Dividend Date:</span> {cal.get('Ex-Dividend Date', 'N/A')}
"""}
            except Exception as e:
                return {"html": f"<span class=\"bbg-text-red\">Failed to fetch earnings calendar: {e}</span>"}

        return {"html": f"<span class=\"bbg-text-red\">Invalid action '{action}' for ticker '{ticker}'. Try DES, DCF, or COMP.</span>"}

    return {"html": f"<span class=\"bbg-text-red\">Unknown command: '{raw_command}'. Type HELP for options.</span>"}
