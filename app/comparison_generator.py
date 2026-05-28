import json
from pathlib import Path
from datetime import datetime

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Quant Terminal — Multi-Ticker Comparison</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #030407;
            --bg-sidebar: #0e0e11;
            --bg-panel: #121215;
            --bg-card: #18181b;
            --border-color: #27272a;
            --border-hover: #3f3f46;
            --text-primary: #fafafa;
            --text-secondary: #a1a1aa;
            --text-muted: #52525b;
            
            --accent: #2563eb;
            --cyan: #06b6d4;
            --purple: #8b5cf6;
            --green: #10b981;
            --green-glow: rgba(16, 185, 129, 0.08);
            --red: #ef4444;
            --red-glow: rgba(239, 68, 68, 0.08);
            --amber: #f59e0b;
            --amber-glow: rgba(245, 158, 11, 0.08);
            --ease: cubic-bezier(0.16, 1, 0.3, 1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-main);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            font-size: 15px;
            line-height: 1.5;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* Sidebar Styling */
        .sidebar {
            width: 240px;
            background-color: var(--bg-sidebar);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            z-index: 100;
        }

        .sidebar-brand {
            padding: 24px 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid var(--border-color);
        }

        .brand-monogram {
            background-color: var(--accent);
            color: #ffffff;
            font-weight: 700;
            font-size: 0.9rem;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
        }

        .brand-text {
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: var(--text-primary);
        }

        .sidebar-menu {
            list-style: none;
            padding: 20px 10px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            flex-grow: 1;
        }

        .menu-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 14px;
            border-radius: 4px;
            color: var(--text-secondary);
            text-decoration: none;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .menu-item:hover, .menu-item.active {
            background-color: var(--bg-panel);
            color: var(--text-primary);
            border-left: 3px solid var(--accent);
            padding-left: 11px;
        }

        .menu-item svg {
            width: 16px;
            height: 16px;
            color: inherit;
        }

        .sidebar-footer {
            padding: 20px;
            border-top: 1px solid var(--border-color);
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        /* Workspace Layout */
        .workspace {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            padding: 24px;
            background-color: var(--bg-main);
        }

        .workspace-header {
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .workspace-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 4px;
        }

        .workspace-subtitle {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        /* Panel Widgets */
        .panel {
            background-color: var(--bg-panel);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 20px;
            margin-bottom: 24px;
            transition: transform 0.3s var(--ease), border-color 0.3s var(--ease), box-shadow 0.3s var(--ease);
        }

        .panel:hover {
            transform: scale(1.005);
            border-color: var(--border-hover);
            box-shadow: 0 12px 40px rgba(0,0,0,0.25);
        }

        .panel-title {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 16px;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
        }

        /* Matrix Table styling */
        .table-container {
            width: 100%;
            overflow-x: auto;
            margin-bottom: 10px;
        }

        .matrix-table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.85rem;
        }

        .matrix-table th {
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 10px 14px;
            font-size: 0.8rem;
            text-transform: uppercase;
        }

        .matrix-table td {
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }

        .matrix-table tr:hover td {
            background-color: rgba(255, 255, 255, 0.02);
        }

        .val-cell {
            font-family: 'JetBrains Mono', monospace;
            text-align: right;
        }

        .ticker-badge {
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .verdict-badge {
            display: inline-block;
            font-weight: 700;
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 3px;
            text-transform: uppercase;
        }

        .moat-badge {
            display: inline-block;
            font-weight: 600;
            font-size: 0.75rem;
            padding: 2px 6px;
            border-radius: 3px;
            text-transform: uppercase;
        }

        /* Bar Chart Styles */
        .comparison-charts {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 10px;
        }

        .chart-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 16px;
            transition: transform 0.3s var(--ease), border-color 0.3s var(--ease), box-shadow 0.3s var(--ease);
        }

        .chart-card:hover {
            transform: scale(1.01);
            border-color: var(--border-hover);
            box-shadow: 0 12px 32px rgba(0,0,0,0.3);
        }

        .chart-card-title {
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 14px;
        }

        .bar-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .bar-row {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .bar-label {
            width: 60px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--text-primary);
            text-align: left;
        }

        .bar-wrapper {
            flex-grow: 1;
            height: 16px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 2px;
            overflow: hidden;
            position: relative;
        }

        .bar-fill {
            height: 100%;
            background-color: var(--accent);
            border-radius: 2px;
            transition: width 0.5s ease-out;
        }

        .bar-val {
            width: 70px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-align: right;
        }
    </style>
</head>
<body>

    <!-- Sidebar navigation -->
    <div class="sidebar">
        <div class="sidebar-brand">
            <span class="brand-monogram">QT</span>
            <span class="brand-text">QUANT TERMINAL</span>
        </div>
        <ul class="sidebar-menu">
            <a href="#" class="menu-item active">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"></path><path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"></path></svg>
                Comparison Matrix
            </a>
        </ul>
        <div class="sidebar-footer">
            <div>Quant Terminal Comparison</div>
            <div>Refreshed: {{REFRESH_DATE}}</div>
        </div>
    </div>

    <!-- Workspace -->
    <div class="workspace">
        <div class="workspace-header">
            <div>
                <h1 class="workspace-title">Multi-Ticker Portfolio Comparison</h1>
                <p class="workspace-subtitle">Side-by-side valuation, financial metrics, and AI recommendations</p>
            </div>
        </div>

        <!-- 1. Comparison Matrix Grid -->
        <div class="panel">
            <div class="panel-title">Comparative Analysis Matrix</div>
            <div class="table-container">
                <table class="matrix-table">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th>Company Name</th>
                            <th>Sector</th>
                            <th>Verdict</th>
                            <th style="text-align:right">Price</th>
                            <th style="text-align:right">P/E</th>
                            <th style="text-align:right">Fwd P/E</th>
                            <th style="text-align:right">PEG Ratio</th>
                            <th style="text-align:right">ROE</th>
                            <th style="text-align:right">Net Margin</th>
                            <th style="text-align:right">Rev Growth</th>
                            <th style="text-align:right">Moat</th>
                            <th style="text-align:right">Altman Z</th>
                            <th style="text-align:right">Piotroski F</th>
                            <th style="text-align:right">DCF Fair Val</th>
                            <th style="text-align:right">Margin of Safety</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{MATRIX_ROWS}}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 2. Visual Multiples Comparison Charts -->
        <div class="panel">
            <div class="panel-title">Visual Multiples Comparison</div>
            <div class="comparison-charts">
                
                <!-- Chart 1: Trailing P/E Comparison -->
                <div class="chart-card">
                    <div class="chart-card-title">Trailing P/E Ratio</div>
                    <div class="bar-group">
                        {{PE_CHART_ROWS}}
                    </div>
                </div>

                <!-- Chart 2: Net Income Margins Comparison -->
                <div class="chart-card">
                    <div class="chart-card-title">Net Margin (%)</div>
                    <div class="bar-group">
                        {{MARGIN_CHART_ROWS}}
                    </div>
                </div>

                <!-- Chart 3: Margin of Safety Comparison -->
                <div class="chart-card">
                    <div class="chart-card-title">DCF Margin of Safety</div>
                    <div class="bar-group">
                        {{MOS_CHART_ROWS}}
                    </div>
                </div>

            </div>
        </div>

    </div>

</body>
</html>
"""

def generate_comparison_dashboard(stocks_list, output_path):
    """
    Compiles a side-by-side comparison dashboard.
    stocks_list: list of dicts: [ { "data": stock_data, "analysis": analysis_dict }, ... ]
    """
    matrix_rows = ""
    pe_rows = ""
    margin_rows = ""
    mos_rows = ""

    # Find max values for normalization in visual bar charts
    max_pe = 1.0
    max_margin = 1.0
    max_mos = 1.0
    
    parsed_stocks = []
    
    for s in stocks_list:
        sd = s["data"]
        an = s["analysis"]
        m = sd.get("key_metrics", {})
        ticker = sd["ticker"]
        name = sd["company_name"]
        
        # Pull multiples
        pe = m.get("trailingPE")
        fwd_pe = m.get("forwardPE")
        peg = m.get("pegRatio")
        roe = m.get("returnOnEquity")
        margins = m.get("profitMargins")
        rev_growth = m.get("revenueGrowth")
        
        # Coherent Fair Value
        val_assess = an.get("valuation_assessment", {})
        fair_value_mid = val_assess.get("fair_value_mid")
        dcf = sd.get("dcf_data")
        raw_dcf = dcf.get("implied_price") if dcf else None
        
        price = m.get("current_price", 0)
        
        mos = None
        if fair_value_mid and price:
            mos = ((fair_value_mid - price) / fair_value_mid) * 100
            
        parsed_stocks.append({
            "ticker": ticker,
            "name": name,
            "sector": m.get("sector", "N/A"),
            "verdict": an.get("verdict", "N/A"),
            "confidence": an.get("verdict_confidence", "N/A"),
            "price": price,
            "pe": pe,
            "fwd_pe": fwd_pe,
            "peg": peg,
            "roe": roe,
            "margins": margins,
            "rev_growth": rev_growth,
            "moat": an.get("moat_rating", "N/A") or m.get("overallRisk", "N/A"),
            "dcf": raw_dcf,
            "mos": mos,
            "altman_z_label": sd.get("financial_scores", {}).get("altman_z_label", "N/A"),
            "altman_z_color": sd.get("financial_scores", {}).get("altman_z_color", "var(--text-secondary)"),
            "piotroski_f_label": sd.get("financial_scores", {}).get("piotroski_f_label", "N/A"),
            "piotroski_f_color": sd.get("financial_scores", {}).get("piotroski_f_color", "var(--text-secondary)")
        })
        
        # Track max values for charting
        if pe and isinstance(pe, (int, float)): max_pe = max(max_pe, pe)
        if margins and isinstance(margins, (int, float)): max_margin = max(max_margin, margins * 100)
        if mos and isinstance(mos, (int, float)): max_mos = max(max_mos, abs(mos))

    # Build HTML elements
    for s in parsed_stocks:
        # 1. Verdict Color
        v = s["verdict"].upper()
        v_color = "var(--green)" if "BUY" in v else "var(--red)" if "SELL" in v else "var(--amber)"
        v_bg = "var(--green-glow)" if "BUY" in v else "var(--red-glow)" if "SELL" in v else "var(--amber-glow)"
        
        # 2. Moat badge color
        moat = str(s["moat"]).upper()
        moat_color = "var(--green)" if "WIDE" in moat else "var(--cyan)" if "NARROW" in moat else "var(--text-secondary)"
        moat_bg = "var(--green-glow)" if "WIDE" in moat else "rgba(6, 182, 212, 0.08)" if "NARROW" in moat else "rgba(255,255,255,0.05)"
        
        # 3. String values formatting
        pe_str = f"{s['pe']:.1f}" if isinstance(s['pe'], (int, float)) else "N/A"
        fwd_pe_str = f"{s['fwd_pe']:.1f}" if isinstance(s['fwd_pe'], (int, float)) else "N/A"
        peg_str = f"{s['peg']:.2f}" if isinstance(s['peg'], (int, float)) else "N/A"
        roe_str = f"{s['roe']*100:.1f}%" if isinstance(s['roe'], (int, float)) else "N/A"
        margins_str = f"{s['margins']*100:.1f}%" if isinstance(s['margins'], (int, float)) else "N/A"
        rev_growth_str = f"{s['rev_growth']*100:.1f}%" if isinstance(s['rev_growth'], (int, float)) else "N/A"
        dcf_str = f"${s['dcf']:.2f}" if isinstance(s['dcf'], (int, float)) else "N/A"
        
        mos_str = "N/A"
        mos_color = "var(--text-primary)"
        if isinstance(s['mos'], (int, float)):
            mos_str = f"{s['mos']:+.1f}%"
            mos_color = "var(--green)" if s['mos'] > 0 else "var(--red)"
            
        matrix_rows += f"""
        <tr>
            <td><a href="{s['ticker']}/{s['ticker']}_dashboard.html" class="ticker-badge" style="text-decoration:none;">{s['ticker']}</a></td>
            <td>{s['name']}</td>
            <td>{s['sector']}</td>
            <td><span class="verdict-badge" style="color:{v_color}; background-color:{v_bg}; border:1px solid {v_color}30;">{s['verdict']} ({s['confidence']}%)</span></td>
            <td class="val-cell">${s['price']:.2f}</td>
            <td class="val-cell">{pe_str}</td>
            <td class="val-cell">{fwd_pe_str}</td>
            <td class="val-cell">{peg_str}</td>
            <td class="val-cell">{roe_str}</td>
            <td class="val-cell">{margins_str}</td>
            <td class="val-cell">{rev_growth_str}</td>
            <td style="text-align:right;"><span class="moat-badge" style="color:{moat_color}; background-color:{moat_bg}; border:1px solid {moat_color}30;">{s['moat']}</span></td>
            <td class="val-cell" style="color:{s['altman_z_color']}; font-weight:700;">{s['altman_z_label']}</td>
            <td class="val-cell" style="color:{s['piotroski_f_color']}; font-weight:700;">{s['piotroski_f_label']}</td>
            <td class="val-cell">{dcf_str}</td>
            <td class="val-cell" style="color:{mos_color}; font-weight:700;">{mos_str}</td>
        </tr>
        """
        
        # 4. Chart 1: P/E
        pe_val = s['pe'] if isinstance(s['pe'], (int, float)) else 0
        pe_width = min(100, (pe_val / max_pe) * 100) if max_pe > 0 else 0
        pe_rows += f"""
        <div class="bar-row">
            <div class="bar-label">{s['ticker']}</div>
            <div class="bar-wrapper">
                <div class="bar-fill" style="width: {pe_width}%; background-color: var(--accent);"></div>
            </div>
            <div class="bar-val">{pe_str}</div>
        </div>
        """
        
        # 5. Chart 2: Profit Margins
        margin_val = s['margins'] * 100 if isinstance(s['margins'], (int, float)) else 0
        margin_width = min(100, (margin_val / max_margin) * 100) if max_margin > 0 else 0
        margin_rows += f"""
        <div class="bar-row">
            <div class="bar-label">{s['ticker']}</div>
            <div class="bar-wrapper">
                <div class="bar-fill" style="width: {margin_width}%; background-color: var(--cyan);"></div>
            </div>
            <div class="bar-val">{margins_str}</div>
        </div>
        """
        
        # 6. Chart 3: Margin of Safety
        mos_val = s['mos'] if isinstance(s['mos'], (int, float)) else 0
        mos_width = min(100, (abs(mos_val) / max_mos) * 100) if max_mos > 0 else 0
        fill_color = "var(--green)" if mos_val > 0 else "var(--red)"
        mos_rows += f"""
        <div class="bar-row">
            <div class="bar-label">{s['ticker']}</div>
            <div class="bar-wrapper">
                <div class="bar-fill" style="width: {mos_width}%; background-color: {fill_color};"></div>
            </div>
            <div class="bar-val" style="color: {fill_color};">{mos_str}</div>
        </div>
        """

    # Replace values
    html = HTML_TEMPLATE
    html = html.replace("{{REFRESH_DATE}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace("{{MATRIX_ROWS}}", matrix_rows)
    html = html.replace("{{PE_CHART_ROWS}}", pe_rows)
    html = html.replace("{{MARGIN_CHART_ROWS}}", margin_rows)
    html = html.replace("{{MOS_CHART_ROWS}}", mos_rows)
    
    # Save file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
