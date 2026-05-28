"""
Dashboard Generator -- High-End, Interactive All-In-One Stock Terminal HTML
Incorporates all quarterly financial statements, expectations, consensus estimates, and expert AI thesis.
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

def _safe_json(o):
    if hasattr(o, "strftime"):
        return o.strftime("%Y-%m-%d")
    if isinstance(o, (set, range)):
        return list(o)
    if hasattr(o, "to_dict"):
        return o.to_dict()
    return str(o)

def _safe_float(val):
    if pd.isna(val) or val is None:
        return None
    try:
        return float(val)
    except:
        return str(val)

def _df_to_json_ready(df):
    if df is None or df.empty:
        return {"columns": [], "rows": []}
    
    df_reset = df.reset_index()
    first_col_name = "Metric"
    df_reset.rename(columns={df_reset.columns[0]: first_col_name}, inplace=True)
    
    cols = []
    date_cols = []
    for col in df_reset.columns:
        if hasattr(col, "strftime"):
            date_str = col.strftime("%Y-%m-%d")
            cols.append(date_str)
            date_cols.append(date_str)
        else:
            cols.append(str(col))
    
    df_reset.columns = cols
    
    if len(date_cols) > 1:
        non_date_cols = [c for c in cols if c not in date_cols]
        reversed_date_cols = list(reversed(date_cols))
        ordered_cols = non_date_cols + reversed_date_cols
        df_reset = df_reset[ordered_cols]
    
    rows = []
    for _, row in df_reset.iterrows():
        r = {}
        for col in df_reset.columns:
            r[col] = _safe_float(row[col])
        rows.append(r)
        
    return {
        "columns": list(df_reset.columns),
        "rows": rows
    }

def _df_to_records_safe(df):
    if df is None or df.empty:
        return []
    df_reset = df.reset_index()
    df_reset.rename(columns={df_reset.columns[0]: "Date"}, inplace=True)
    for col in df_reset.columns:
        if pd.api.types.is_datetime64_any_dtype(df_reset[col]):
            df_reset[col] = df_reset[col].dt.strftime("%Y-%m-%d")
        else:
            df_reset[col] = df_reset[col].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else x)
            
    records = []
    for _, row in df_reset.iterrows():
        rec = {}
        for col in df_reset.columns:
            val = row[col]
            if pd.isna(val) or val is None:
                rec[col] = None
            else:
                try:
                    rec[col] = float(val)
                except:
                    rec[col] = str(val)
        records.append(rec)
    return records

def _prep_chart_data(history):
    if history.empty:
        return {
            "labels": [], "close": [], "volume": [], 
            "sma50": [], "sma200": [], "ema20": [], 
            "bb_upper": [], "bb_lower": [], "rsi": [], 
            "macd": [], "macd_signal": [], "macd_hist": []
        }
    h = history.tail(252)
    labels = [d.strftime("%Y-%m-%d") for d in h.index]
    def col(n):
        return [round(float(v), 2) if pd.notna(v) else None for v in h[n]] if n in h.columns else []
    return {
        "labels": labels,
        "close": col("Close"),
        "volume": col("Volume"),
        "sma50": col("SMA_50"),
        "sma200": col("SMA_200"),
        "ema20": col("EMA_20"),
        "bb_upper": col("BB_Upper"),
        "bb_lower": col("BB_Lower"),
        "rsi": col("RSI"),
        "macd": col("MACD"),
        "macd_signal": col("MACD_Signal"),
        "macd_hist": col("MACD_Hist")
    }

def generate_dashboard(stock_data, analysis, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    sd = stock_data
    m = sd["key_metrics"]
    t = sd["ticker"]
    name = sd["company_name"]
    source_meta = sd.get("source_metadata", {})
    
    q_financials = _df_to_json_ready(sd.get("quarterly_financials"))
    q_balance_sheet = _df_to_json_ready(sd.get("quarterly_balance_sheet"))
    q_cashflow = _df_to_json_ready(sd.get("quarterly_cashflow"))
    
    earnings_hist = _df_to_records_safe(sd.get("earnings_history"))
    earnings_dates = _df_to_records_safe(sd.get("earnings_dates"))
    chart_data = _prep_chart_data(sd["history_1y"])
    
    v = analysis.get("verdict", "HOLD")
    conf = analysis.get("verdict_confidence", 50)
    vc = "#10b981" if v in ["BUY", "STRONG BUY"] else "#f43f5e" if v in ["SELL", "STRONG SELL"] else "#f59e0b"
    vbg = "rgba(16, 185, 129, 0.1)" if v in ["BUY", "STRONG BUY"] else "rgba(244, 63, 94, 0.1)" if v in ["SELL", "STRONG SELL"] else "rgba(245, 158, 11, 0.1)"
    
    moat = analysis.get("fundamental_analysis", {}).get("moat_rating", "N/A")
    mgmt = analysis.get("fundamental_analysis", {}).get("management_score", "N/A")
    sent_score = analysis.get("sentiment_analysis", {}).get("sentiment_score", "N/A")
    sent_label = analysis.get("sentiment_label", "NEUTRAL")
    val_grade = analysis.get("valuation_assessment", {}).get("valuation_grade", "N/A")
    
    source_citations = {
        "fundamentals": "Yahoo Finance/yfinance statements; SEC EDGAR companyfacts and 10-K/10-Q filings where available.",
        "dcf": f"Local Python DCF using {sd.get('dcf_data', {}).get('valuation_basis', 'FCF DCF')} from Yahoo/SEC-derived fundamentals.",
        "analyst_targets": "Yahoo Finance/yfinance analyst target and recommendation fields.",
        "earnings": "Yahoo Finance/yfinance earnings dates and history.",
        "news_sentiment": "Alpha Vantage NEWS_SENTIMENT API plus Groq interpretation.",
        "ai": "Groq-generated interpretation grounded in the embedded facts payload."
    }

    facts_payload = {
        "ticker": t,
        "company_name": name,
        "metrics": m,
        "metric_confidence": m.get("_confidence", {}),
        "q_financials": q_financials,
        "q_balance_sheet": q_balance_sheet,
        "q_cashflow": q_cashflow,
        "earnings_history": earnings_hist,
        "earnings_dates": earnings_dates,
        "chart_data": chart_data,
        "financial_scores": sd.get("financial_scores", {}),
        "peers_data": sd.get("peers_data", []),
        "advanced_models": sd.get("advanced_models", {}),
        "sec_data": sd.get("sec_data", {}),
        "source_metadata": source_meta,
        "source_citations": source_citations
    }

    interpretation_payload = {
        "analysis": analysis,
        "provider": source_meta.get("providers", {}).get("ai_analysis", "Groq OpenAI-compatible chat completions")
    }

    raw_data_payload = {
        "ticker": t,
        "company_name": name,
        "metrics": m,
        "metric_confidence": m.get("_confidence", {}),
        "q_financials": q_financials,
        "q_balance_sheet": q_balance_sheet,
        "q_cashflow": q_cashflow,
        "earnings_history": earnings_hist,
        "earnings_dates": earnings_dates,
        "chart_data": chart_data,
        "analysis": analysis,
        "financial_scores": sd.get("financial_scores", {}),
        "peers_data": sd.get("peers_data", []),
        "advanced_models": sd.get("advanced_models", {}),
        "dcf_data": sd.get("dcf_data", {}),
        "sec_data": sd.get("sec_data", {}),
        "notion_data": sd.get("notion_data"),
        "source_metadata": source_meta,
        "source_citations": source_citations,
        "facts": facts_payload,
        "interpretation": interpretation_payload
    }
    
    # Static HTML Template (no f-string format errors)
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TICKER}} // AI Equity Research Terminal</title>
    <!-- Core Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #08090b; /* Deep matte black */
            --bg-sidebar: #0d0e12; /* Volcanic panel matte */
            --bg-panel: #0d0e12;
            --bg-card: #0d0e12;
            --border-color: #1c1e24; /* Steel grey border */
            --border-hover: #2a2d36; /* Subtle border hover highlight */
            --text-primary: #f3f4f6; /* Off-white text */
            --text-secondary: #9ca3af; /* Steel grey descriptive text */
            --text-muted: #4b5563; /* Slate grey */
            
            --accent: #3f61ec; /* Muted corporate blue */
            --accent-gradient: #3f61ec;
            --accent-glow: rgba(63, 97, 236, 0.04);
            --accent-glow-bright: rgba(63, 97, 236, 0.1);
            
            --green: #10b981;
            --green-glow: rgba(16, 185, 129, 0.02);
            --red: #ef4444;
            --red-glow: rgba(239, 68, 68, 0.02);
            --amber: #f59e0b;
            --amber-glow: rgba(245, 158, 11, 0.02);
            --cyan: #06b6d4;
            --yellow: #f59e0b;
        }

        html {
            /* Fluid base font: scales smoothly from 11.5px at 1024px to 15px at 1920px */
            font-size: clamp(11.5px, 0.55vw + 9.5px, 15px);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', sans-serif;
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.08) transparent;
        }

        /* Scrollbar styles */
        ::-webkit-scrollbar {
            width: 5px;
            height: 5px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 9999px;
            transition: all 0.3s ease;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(59, 130, 246, 0.5);
            box-shadow: 0 0 8px rgba(59, 130, 246, 0.5);
        }

        body {
            background-color: var(--bg-main);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            display: flex;
            background-attachment: fixed;
        }

        /* Left Navigation Terminal Sidebar */
        .sidebar {
            width: clamp(200px, 14vw, 260px);
            background: rgba(5, 7, 15, 0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            flex-direction: column;
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            z-index: 100;
            flex-shrink: 0;
        }

        .brand {
            padding: 28px 24px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-logo {
            width: 28px;
            height: 28px;
            background: var(--accent-gradient);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            color: white;
            font-size: 0.85rem;
            font-family: 'JetBrains Mono', monospace;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
        }

        .brand-text {
            font-weight: 800;
            font-size: 0.9rem;
            letter-spacing: 1.5px;
            color: var(--text-primary);
            text-transform: uppercase;
            background: linear-gradient(135deg, #ffffff 0%, #a1a1aa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .sidebar-menu {
            padding: 20px 12px;
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 6px;
            flex: 1;
        }

        .menu-item {
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 12px 16px;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 500;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            border-left: 3px solid transparent;
        }

        .menu-item:hover {
            color: var(--text-primary);
            background-color: rgba(255, 255, 255, 0.03);
            transform: translateX(4px);
        }

        .menu-item.active {
            color: var(--text-primary);
            background: linear-gradient(90deg, rgba(59, 130, 246, 0.15) 0%, rgba(99, 102, 241, 0.03) 100%);
            border-left: 3px solid var(--accent);
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.05);
        }

        .menu-item svg {
            width: 16px;
            height: 16px;
            stroke-width: 1.5;
            transition: none;
        }

        .sidebar-footer {
            padding: 24px 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.72rem;
            color: var(--text-muted);
            line-height: 1.6;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        /* Main Workspace Content Area */
        .workspace {
            margin-left: clamp(200px, 14vw, 260px);
            flex: 1;
            padding: clamp(1rem, 1.5vw, 2rem) clamp(1rem, 2vw, 2.5rem);
            min-height: 100vh;
            max-width: 100vw;
            display: flex;
            flex-direction: column;
            gap: clamp(1rem, 1.5vw, 2rem);
            transition: all 0.15s ease;
            overflow-x: hidden;
        }

        /* Real-time Ticker Banner */
        .ticker-header {
            background: rgba(10, 15, 30, 0.55);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            padding: 20px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }

        .ticker-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--accent-gradient);
        }

        .ticker-left {
            display: flex;
            align-items: center;
            gap: 18px;
        }

        .symbol-badge {
            font-size: 2rem;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.8px;
        }

        .info-tag-group {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .company-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.2px;
        }

        .sector-industry {
            font-size: 0.78rem;
            color: var(--text-secondary);
            font-weight: 500;
            letter-spacing: 0.3px;
        }

        .ticker-center {
            display: flex;
            align-items: center;
            gap: 32px;
        }

        .quote-block {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }

        .quote-label {
            font-size: 0.65rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 3px;
            font-weight: 600;
        }

        .quote-value {
            font-size: 1.5rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }

        .quote-change {
            font-size: 0.82rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
            margin-top: 2px;
            font-family: 'JetBrains Mono', monospace;
        }

        .btn-primary, .btn-secondary {
            padding: 8px 20px;
            font-size: 0.85rem;
            font-weight: 600;
            border-radius: 8px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.25s cubic-bezier(0.19, 1, 0.22, 1);
            height: 40px;
            gap: 8px;
            letter-spacing: 0.3px;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
        }

        .btn-primary {
            background: linear-gradient(135deg, rgba(63, 97, 236, 0.9), rgba(41, 72, 201, 0.95));
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.15);
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(63, 97, 236, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.2);
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        }

        .btn-primary:hover {
            box-shadow: 0 8px 25px rgba(63, 97, 236, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
            background: linear-gradient(135deg, rgba(73, 107, 246, 0.95), rgba(51, 82, 211, 1));
        }

        .btn-primary:active {
            transform: translateY(1px);
            box-shadow: 0 2px 8px rgba(63, 97, 236, 0.3), inset 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .btn-secondary {
            background-color: rgba(255, 255, 255, 0.04);
            color: var(--text-primary) !important;
            border: 1px solid rgba(255, 255, 255, 0.08);
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }

        .btn-secondary:hover {
            border-color: rgba(255, 255, 255, 0.2);
            background-color: rgba(255, 255, 255, 0.08);
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
            color: #fff !important;
        }

        .btn-secondary:active {
            transform: translateY(1px);
            background-color: rgba(255, 255, 255, 0.02);
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        @keyframes verdict-pulse {
            0% {
                box-shadow: 0 0 6px {{VERDICT_COLOR}}25, inset 0 0 4px {{VERDICT_COLOR}}15;
            }
            50% {
                box-shadow: 0 0 16px {{VERDICT_COLOR}}50, inset 0 0 10px {{VERDICT_COLOR}}25;
            }
            100% {
                box-shadow: 0 0 6px {{VERDICT_COLOR}}25, inset 0 0 4px {{VERDICT_COLOR}}15;
            }
        }

        .verdict-banner {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 18px;
            border-radius: 20px;
            background-color: {{VERDICT_BG}};
            border: 1px solid {{VERDICT_COLOR}}60;
            height: 38px;
            animation: verdict-pulse 3s infinite ease-in-out;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .verdict-banner:hover {
            border-color: {{VERDICT_COLOR}};
            transform: scale(1.03);
            box-shadow: 0 0 24px {{VERDICT_COLOR}}70, inset 0 0 12px {{VERDICT_COLOR}}40;
        }

        .verdict-tag {
            font-size: 1rem;
            font-weight: 800;
            color: {{VERDICT_COLOR}};
            letter-spacing: 0.8px;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
        }

        .verdict-conf {
            text-align: right;
            display: flex;
            flex-direction: column;
            line-height: 1.1;
        }

        .verdict-conf span:first-child {
            font-size: 0.6rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.8;
        }

        .verdict-conf span:last-child {
            font-size: 0.85rem;
            font-weight: 700;
            color: {{VERDICT_COLOR}};
            font-family: 'JetBrains Mono', monospace;
        }

        /* Performance Bar */
        .perf-bar {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }

        .perf-badge {
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.72rem;
            font-weight: 600;
            border: 1px solid var(--border-color);
            background-color: rgba(255, 255, 255, 0.02);
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }

        /* Bento Grid Layouts */
        .bento-grid-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: clamp(12px, 1.2vw, 20px);
        }

        .score-bento {
            background: var(--bg-card);
            backdrop-filter: blur(16px) saturate(120%);
            -webkit-backdrop-filter: blur(16px) saturate(120%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            min-height: 130px;
            height: auto;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .score-bento::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--accent-gradient);
            opacity: 0.6;
        }

        .score-bento:hover {
            transform: translateY(-3px);
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5), 0 0 25px rgba(59, 130, 246, 0.15);
            border-color: rgba(59, 130, 246, 0.4);
            background: rgba(20, 28, 54, 0.6);
        }

        .score-title {
            font-size: 0.7rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1.2px;
            font-weight: 600;
            opacity: 0.8;
        }

        .score-big {
            font-size: 1.3rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .score-desc {
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-weight: 500;
        }

        /* Main Tabs Panel Content */
        .tab-panel {
            display: none;
            flex-direction: column;
            gap: 28px;
            animation: fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .tab-panel.active {
            display: flex;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Bento Panel Layout */
        .panel-grid-2 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(400px, 100%), 1fr));
            gap: clamp(14px, 1.5vw, 24px);
        }

        .panel-grid-3 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
            gap: clamp(14px, 1.5vw, 24px);
        }

        .panel-left-heavy {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: clamp(14px, 1.5vw, 24px);
        }

        .panel-right-heavy {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: clamp(14px, 1.5vw, 24px);
        }

        /* Main Widget Card Styling */
        .widget {
            backdrop-filter: blur(16px) saturate(120%);
            -webkit-backdrop-filter: blur(16px) saturate(120%);
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: clamp(14px, 1.5vw, 24px);
            display: flex;
            flex-direction: column;
            gap: clamp(12px, 1.2vw, 18px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            min-width: 0;
        }

        .widget:hover {
            transform: translateY(-2px);
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6), 0 0 20px rgba(59, 130, 246, 0.08);
            border-color: rgba(59, 130, 246, 0.35);
        }

        .widget-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 12px;
        }

        .widget-title {
            font-size: 1rem;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.2px;
        }

        /* Scenario Preset Buttons styling */
        .btn-scenario {
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
            position: relative;
            overflow: hidden;
            border-radius: 6px;
        }
        .btn-scenario:hover {
            transform: translateY(-1px);
        }
        .btn-scenario:active {
            transform: translateY(1px);
        }
        .btn-scenario[data-scenario="bear"] {
            background: rgba(244, 63, 94, 0.05) !important;
            color: var(--red) !important;
            border: 1px solid rgba(244, 63, 94, 0.15) !important;
        }
        .btn-scenario[data-scenario="bear"]:hover, .btn-scenario[data-scenario="bear"].active {
            background: rgba(244, 63, 94, 0.15) !important;
            border-color: var(--red) !important;
            box-shadow: 0 0 15px rgba(244, 63, 94, 0.25) !important;
        }
        .btn-scenario[data-scenario="base"] {
            background: rgba(59, 130, 246, 0.05) !important;
            color: var(--cyan) !important;
            border: 1px solid rgba(59, 130, 246, 0.15) !important;
        }
        .btn-scenario[data-scenario="base"]:hover, .btn-scenario[data-scenario="base"].active {
            background: rgba(59, 130, 246, 0.15) !important;
            border-color: var(--cyan) !important;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.25) !important;
        }
        .btn-scenario[data-scenario="bull"] {
            background: rgba(16, 185, 129, 0.05) !important;
            color: var(--green) !important;
            border: 1px solid rgba(16, 185, 129, 0.15) !important;
        }
        .btn-scenario[data-scenario="bull"]:hover, .btn-scenario[data-scenario="bull"].active {
            background: rgba(16, 185, 129, 0.15) !important;
            border-color: var(--green) !important;
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.25) !important;
        }

        .widget-badge {
            font-size: 0.65rem;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 700;
            letter-spacing: 0.8px;
            text-transform: uppercase;
        }

        /* Metric Grid inside overview */
        .metrics-bento-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(min(160px, 100%), 1fr));
            gap: clamp(10px, 1vw, 14px);
        }

        .metric-mini {
            background-color: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .metric-mini:hover {
            border-color: rgba(59, 130, 246, 0.35);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
            background-color: rgba(255, 255, 255, 0.03);
        }

        .metric-mini-label {
            font-size: 0.65rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            opacity: 0.8;
        }

        .metric-mini-val {
            font-size: 1.15rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
        }

        .metric-mini-sub {
            font-size: 0.72rem;
            color: var(--text-secondary);
            opacity: 0.7;
        }

        /* High-End interactive financials table */
        .financial-statement-selector {
            display: flex;
            gap: 6px;
        }

        .btn-toggle {
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .btn-toggle:hover {
            color: var(--text-primary);
            border-color: var(--border-hover);
            background-color: rgba(255, 255, 255, 0.05);
        }

        .btn-toggle.active {
            background: var(--accent-gradient);
            color: #ffffff;
            border: none;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
        }

        .table-container {
            width: 100%;
            overflow-x: auto;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            background-color: rgba(10, 15, 30, 0.3);
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        }

        .statement-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            text-align: left;
        }

        .statement-table th {
            background-color: rgba(6, 8, 19, 0.6);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 12px 16px;
            border-bottom: 1.5px solid rgba(255, 255, 255, 0.06);
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.8px;
        }

        .statement-table td {
            padding: 12px 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text-secondary);
            transition: all 0.15s ease;
        }

        .statement-table tr:hover td {
            color: var(--text-primary);
            background-color: rgba(59, 130, 246, 0.05);
        }

        .statement-table tr.header-row td {
            background-color: rgba(59, 130, 246, 0.08);
            color: var(--text-primary);
            font-weight: 700;
            border-bottom: 1.5px solid rgba(59, 130, 246, 0.2);
        }

        .statement-table td.metric-name {
            font-weight: 600;
            color: var(--text-primary);
            max-width: 250px;
        }

        .statement-table td.val-cell {
            font-family: 'JetBrains Mono', monospace;
            text-align: right;
        }

        /* Custom styled range sliders for DCF simulation */
        input[type="range"].dcf-slider {
            -webkit-appearance: none;
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 4px;
            outline: none;
            transition: all 0.15s ease;
            margin: 12px 0;
        }

        input[type="range"].dcf-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--accent);
            cursor: pointer;
            box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
            transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
            border: 2px solid #ffffff;
        }

        input[type="range"].dcf-slider::-webkit-slider-thumb:hover {
            transform: scale(1.25);
            background: #ffffff;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.8), 0 0 0 4px rgba(59, 130, 246, 0.25);
            border-color: var(--accent);
        }

        /* Expectations Chart and Dates */
        .earnings-grid {
            display: grid;
            grid-template-columns: 3fr 2fr;
            gap: 24px;
        }

        .earnings-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-height: 350px;
            overflow-y: auto;
            padding-right: 4px;
        }

        .earnings-row {
            background-color: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.82rem;
            transition: all 0.2s ease;
        }

        .earnings-row:hover {
            border-color: rgba(59, 130, 246, 0.35);
            background-color: rgba(255, 255, 255, 0.03);
            transform: translateY(-1px);
        }

        .earnings-date-tag {
            font-weight: 700;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
        }

        .earnings-estimates {
            display: flex;
            flex-direction: column;
            gap: 2px;
            align-items: flex-end;
        }

        .earnings-actual-tag {
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        /* Gold-Standard AI Note block styling */
        .ai-section-box {
            background-color: rgba(255, 255, 255, 0.01);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            line-height: 1.7;
            font-size: 0.88rem;
            color: var(--text-secondary);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .ai-section-box:hover {
            border-color: rgba(59, 130, 246, 0.3);
            transform: translateY(-1px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            background-color: rgba(255, 255, 255, 0.02);
        }

        .ai-section-box h3 {
            color: var(--text-primary);
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 8px;
            letter-spacing: -0.2px;
        }

        .ai-section-box p {
            margin-bottom: 12px;
        }

        /* Tailwinds & Headwinds block */
        .wind-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .wind-box {
            background-color: rgba(255, 255, 255, 0.01);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 18px 22px;
        }

        .wind-box h4 {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 700;
        }

        .wind-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .wind-item {
            font-size: 0.85rem;
            line-height: 1.6;
            padding-left: 20px;
            position: relative;
            color: var(--text-secondary);
        }

        .wind-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 7px;
            width: 7px;
            height: 7px;
            border-radius: 50%;
        }

        .tailwind::before {
            background-color: var(--green);
            box-shadow: 0 0 8px var(--green);
        }

        .headwind::before {
            background-color: var(--red);
            box-shadow: 0 0 8px var(--red);
        }

        /* Custom Intrinsic Value Gauge */
        .gauge-container {
            background-color: rgba(255, 255, 255, 0.01);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .gauge-track {
            height: 8px;
            background-color: rgba(255, 255, 255, 0.08);
            border-radius: 4px;
            position: relative;
            overflow: visible;
        }

        .gauge-marker {
            position: absolute;
            top: -5px;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background-color: var(--accent);
            border: 3px solid #ffffff;
            transform: translateX(-50%);
            transition: left 0.5s ease-out;
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.7);
        }

        .gauge-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
            opacity: 0.8;
        }

        /* Risks severity markers */
        .risk-row-card {
            background-color: rgba(255, 255, 255, 0.015);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            position: relative;
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .risk-row-card:hover {
            transform: translateY(-1px);
            background-color: rgba(255, 255, 255, 0.03);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .risk-row-card::before {
            content: '';
            position: absolute;
            top: 0;
            bottom: 0;
            left: 0;
            width: 4px;
            border-radius: 8px 0 0 8px;
        }

        .risk-row-card.severity-high::before { background-color: var(--red); box-shadow: 0 0 8px var(--red); }
        .risk-row-card.severity-medium::before { background-color: var(--amber); box-shadow: 0 0 8px var(--amber); }
        .risk-row-card.severity-low::before { background-color: var(--green); box-shadow: 0 0 8px var(--green); }

        .risk-row-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .risk-row-title {
            font-weight: 700;
            font-size: 0.88rem;
            color: var(--text-primary);
        }

        .risk-badge {
            font-size: 0.65rem;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .risk-badge.high { background-color: rgba(239,68,68,0.1); color: var(--red); border: 1px solid rgba(239,68,68,0.15); }
        .risk-badge.medium { background-color: rgba(245,158,11,0.1); color: var(--amber); border: 1px solid rgba(245,158,11,0.15); }
        .risk-badge.low { background-color: rgba(16,185,129,0.1); color: var(--green); border: 1px solid rgba(16,185,129,0.15); }

        .risk-row-impact {
            font-size: 0.82rem;
            color: var(--text-secondary);
            line-height: 1.5;
        }

        .moat-badge {
            font-size: 1.2rem;
            font-weight: 800;
            letter-spacing: 0.5px;
            padding: 4px 14px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            background: rgba(16, 185, 129, 0.1);
            color: var(--green);
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        .bento-gauge-value {
            position: absolute;
            bottom: 12px;
            font-size: 1.1rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        .dcf-interactive-card {
            border: 1px solid var(--border-color) !important;
            background-color: rgba(255, 255, 255, 0.005) !important;
        }

        .interactive-row {
            cursor: pointer;
            transition: background-color 0.15s ease;
        }
        .interactive-row:hover td {
            background-color: rgba(59, 130, 246, 0.08) !important;
        }

        /* PDF Export / Print styles */
        body.printing-pdf {
            background-color: #09090b !important;
            color: #fafafa !important;
        }
        body.printing-pdf .sidebar,
        body.printing-pdf .ticker-header button,
        body.printing-pdf .ticker-header a,
        body.printing-pdf .financial-statement-selector {
            display: none !important;
        }
        body.printing-pdf .workspace {
            margin-left: 0 !important;
            padding: 10px !important;
            width: 100% !important;
            max-width: 100% !important;
        }
        body.printing-pdf .tab-panel {
            display: flex !important;
            opacity: 1 !important;
            transform: none !important;
            page-break-after: always !important;
            break-after: page !important;
        }
        body.printing-pdf .widget,
        body.printing-pdf .score-bento,
        body.printing-pdf .ticker-header,
        body.printing-pdf .panel-grid-2,
        body.printing-pdf .panel-grid-3,
        body.printing-pdf .panel-left-heavy {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
        }

        /* Notion Research Hub styling */
        .notion-sub-nav {
            display: inline-flex;
            background: #050608;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 4px;
            gap: 4px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        .notion-sub-btn {
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-secondary);
            padding: 6px 14px;
            border-radius: 3px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.12s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .notion-sub-btn:hover {
            color: var(--text-primary);
            background: rgba(255, 255, 255, 0.03);
        }
        .notion-sub-btn.active {
            background: rgba(255, 255, 255, 0.04);
            border-color: var(--border-hover);
            color: var(--text-primary);
            box-shadow: none;
        }
        .notion-p {
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.75;
            margin-bottom: 16px;
            letter-spacing: 0.1px;
        }
        .notion-h1 {
            font-size: 1.45rem;
            font-weight: 800;
            margin-top: 32px;
            margin-bottom: 16px;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            padding-bottom: 10px;
            letter-spacing: -0.3px;
        }
        .notion-h2 {
            font-size: 1.2rem;
            font-weight: 750;
            color: var(--text-primary);
            margin-top: 24px;
            margin-bottom: 12px;
            border-left: 3px solid var(--accent);
            padding-left: 12px;
            letter-spacing: -0.2px;
        }
        .notion-h3 {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--cyan);
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .notion-ul, .notion-ol {
            margin-left: 4px;
            margin-bottom: 18px;
            list-style: none;
        }
        .notion-ul li {
            position: relative;
            padding-left: 22px;
            margin-bottom: 10px;
            line-height: 1.65;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        .notion-ul li::before {
            content: "•";
            color: var(--accent);
            font-size: 1.1rem;
            position: absolute;
            left: 0;
            top: -1px;
            font-weight: bold;
            text-shadow: none;
        }
        .notion-ol {
            counter-reset: notion-counter;
        }
        .notion-ol li {
            position: relative;
            padding-left: 26px;
            margin-bottom: 10px;
            line-height: 1.65;
            font-size: 0.9rem;
            color: var(--text-secondary);
            counter-increment: notion-counter;
        }
        .notion-ol li::before {
            content: counter(notion-counter) ".";
            color: var(--cyan);
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            position: absolute;
            left: 0;
            top: 0;
        }
        .notion-quote {
            background: rgba(59, 130, 246, 0.02);
            border-left: 4px solid var(--accent);
            border-radius: 0 4px 4px 0;
            padding: 16px 20px;
            margin: 24px 0;
            font-style: normal;
            color: var(--text-primary);
            font-size: 0.92rem;
            line-height: 1.7;
            border-top: 1px solid var(--border-color);
            border-right: 1px solid var(--border-color);
            border-bottom: 1px solid var(--border-color);
        }
        .notion-spacer {
            height: 14px;
        }
        .notion-indented {
            margin-left: 20px;
            border-left: 1px solid var(--border-color);
            padding-left: 16px;
            margin-top: 8px;
            margin-bottom: 8px;
        }
        .notion-img-container {
            margin: 20px 0;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            overflow: hidden;
            background: #090a0f;
            max-width: 100%;
        }
        .notion-img {
            max-width: 100%;
            display: block;
            height: auto;
        }
        .notion-img-caption {
            padding: 8px 12px;
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
            background: rgba(0, 0, 0, 0.15);
            border-top: 1px solid var(--border-color);
        }
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(6px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .notion-sec {
            animation: fadeInUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        @media (max-width: 1440px) {
            .panel-left-heavy,
            .panel-right-heavy {
                grid-template-columns: 1fr;
            }
            .earnings-grid {
                grid-template-columns: 1fr;
            }
            .wind-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 1280px) {
            .sidebar {
                position: relative;
                width: 100%;
                height: auto;
                border-right: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            }
            .sidebar-menu {
                flex-direction: row;
                flex-wrap: wrap;
                padding: 12px 24px;
            }
            .sidebar-footer {
                display: none;
            }
            .workspace {
                margin-left: 0;
                padding: 1rem 1rem;
            }
            .bento-grid-cards {
                grid-template-columns: repeat(2, 1fr);
            }
            .ticker-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 16px;
            }
            .ticker-center {
                width: 100%;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 16px;
            }
        }
        @media (max-width: 768px) {
            .bento-grid-cards {
                grid-template-columns: 1fr;
            }
            .sidebar-menu {
                flex-direction: column;
                gap: 4px;
            }
            .ticker-center {
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }
        }
    </style>
</head>
<body>

    <!-- Left Navigation Terminal Sidebar -->
    <div class="sidebar">
        <div class="brand">
            <div class="brand-logo">QT</div>
            <div class="brand-text">Quant Terminal</div>
        </div>
        <ul class="sidebar-menu">
            <li class="menu-item active" onclick="switchTab('overview')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>
                Overview
            </li>
            <li class="menu-item" onclick="switchTab('premium')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>
                Premium Data & DCF
            </li>
            <li class="menu-item" onclick="switchTab('quantitative')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
                Quantitative Models
            </li>
            <li class="menu-item" onclick="switchTab('financials')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                Quarterly Financials
            </li>
            <li class="menu-item" onclick="switchTab('expectations')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path><circle cx="12" cy="12" r="10" stroke="none" fill="none"></circle><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                Guidance & Expectations
            </li>
            <li class="menu-item" onclick="switchTab('thesis')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                AI Research Note
            </li>
            <li class="menu-item" onclick="switchTab('macro')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                Macro & Sentiment
            </li>
            <li class="menu-item" onclick="switchTab('risks')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                Risk Matrix
            </li>
            <li class="menu-item" id="menu-item-notion" onclick="switchTab('notion_hub')" style="display: none;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                Notion Research Hub
            </li>
        </ul>
        <div class="sidebar-footer">
            <div>Data refreshed: {{REFRESH_DATE}}</div>
            <div>Latest price date: {{LATEST_PRICE_DATE}}</div>
            <div>Sources: Yahoo Finance, Alpha Vantage, Groq</div>
            <div style="margin-top: 6px; color: var(--text-muted)">&copy; Quant Terminal v3.0</div>
        </div>
    </div>

    <!-- Main Workspace Content Area -->
    <div class="workspace">

        <!-- Real-time Ticker Banner -->
        <div class="ticker-header">
            <div class="ticker-left">
                <div class="symbol-badge">{{TICKER}}</div>
                <div class="info-tag-group">
                    <div class="company-title">{{COMPANY_NAME}}</div>
                    <div class="sector-industry">{{SECTOR}} &bull; {{INDUSTRY}}</div>
                </div>
            </div>
            
            <div class="ticker-center">
                <div class="quote-block">
                    <div class="quote-label">Last Traded</div>
                    <div class="quote-value">${{CURRENT_PRICE}}</div>
                    <div class="quote-change" style="color: {{PRICE_CHANGE_COLOR}}">
                        {{PRICE_CHANGE_1D}}% today
                    </div>
                </div>
                <div class="quote-block">
                    <div class="quote-label">Consensus Target</div>
                    <div class="quote-value" style="color: var(--cyan)">${{MEAN_TARGET}}</div>
                    <div class="quote-change" style="color: var(--text-muted)">
                        {{ANALYST_COUNT}} Analyst consensus
                    </div>
                    <div style="font-size:0.68rem; color:var(--text-muted); margin-top:6px;">Source: {{CITE_ANALYST_TARGETS}}</div>
                </div>
            </div>

            <div style="display:flex; align-items:center; gap:10px;">
                <button onclick="window.location.href='/?ticker={{TICKER}}'" class="btn-secondary" style="border-color: var(--accent); color: var(--accent); box-shadow: 0 4px 12px rgba(63, 97, 236, 0.15);">Recompile AI</button>
                <a href="/json/{{TICKER}}" download class="btn-secondary">Export JSON</a>
                <a href="{{TICKER}}_Financial_Model.xlsx" download class="btn-secondary">Export Excel</a>
                <button onclick="downloadPDF()" class="btn-secondary">Export PDF</button>
                <button onclick="syncToNotion('{{TICKER}}')" class="btn-primary" id="notionSyncBtn">Sync to Notion</button>
                <div class="verdict-banner">
                    <div class="verdict-tag">{{VERDICT}}</div>
                    <div class="verdict-conf">
                        <span>Confidence</span>
                        <span>{{VERDICT_CONFIDENCE}}%</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Live Ticker News panel -->
        <div class="card" style="margin-bottom: 24px;">
            <div class="section-label" style="display:flex; justify-content:space-between; align-items:center;">
                <span>Live Breaking News: {{TICKER}}</span>
                <span style="font-size: 0.75rem; color: var(--emerald); animation: pulse 2s infinite; font-weight:700;">● LIVE STREAM</span>
            </div>
            <div id="ticker-news-feed" style="margin-top: 15px; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; max-height: 400px; overflow-y: auto; padding-right: 10px;">
                <div style="color:var(--text-secondary); font-size:0.9rem; text-align:center; grid-column: 1/-1; margin-top: 20px;">Establishing secure connection to ticker news feed...</div>
            </div>
        </div>

        <!-- Bento Row Score Cards -->
        <div class="bento-grid-cards">
            <div class="score-bento">
                <div class="score-title">Economic Moat</div>
                <div style="height:70px; width:100%; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <div id="moat-badge" class="moat-badge">{{MOAT}}</div>
                </div>
                <div class="score-desc">Competitive Power</div>
            </div>
            <div class="score-bento">
                <div class="score-title">Management Quality</div>
                <div style="position:relative; height:70px; width:100%; display:flex; justify-content:center; align-items:flex-end;">
                    <canvas id="gauge-mgmt"></canvas>
                    <div class="bento-gauge-value" style="color:var(--accent)">{{MGMT}}/10</div>
                </div>
                <div class="score-desc">Capital Allocation</div>
            </div>
            <div class="score-bento">
                <div class="score-title">News/Analyst Mood</div>
                <div style="position:relative; height:70px; width:100%; display:flex; justify-content:center; align-items:flex-end;">
                    <canvas id="gauge-sent"></canvas>
                    <div class="bento-gauge-value" style="color:var(--cyan)">{{SENT_LABEL}}</div>
                </div>
                <div class="score-desc">Consensus Sentiment</div>
            </div>
            <div class="score-bento">
                <div class="score-title">Valuation Assessment</div>
                <div style="position:relative; height:70px; width:100%; display:flex; justify-content:center; align-items:flex-end;">
                    <canvas id="gauge-val"></canvas>
                    <div class="bento-gauge-value" style="color:var(--amber)">{{VAL_GRADE}}</div>
                </div>
                <div class="score-desc">Grade vs Fair Value</div>
            </div>
        </div>

        <!-- ================= OVERVIEW TAB PANEL ================= -->
        <div id="overview" class="tab-panel active">
            <div class="panel-left-heavy">
                
                <!-- Performance Sidebar & Chart -->
                <div class="widget">
                    <div class="widget-header" style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="widget-title">Interactive Price Action</div>
                        <div style="display:flex; gap:6px;">
                            <button class="btn-toggle active" id="btn-chart-light" onclick="setChartType('light')" style="background:var(--bg-card); border:1px solid var(--border-color); color:var(--text-primary); font-size:0.75rem; padding:4px 10px; cursor:pointer; font-weight:600; font-family:inherit; border-radius:3px; transition:all 0.15s ease;">Lightweight</button>
                            <button class="btn-toggle" id="btn-chart-tv" onclick="setChartType('tv')" style="background:transparent; border:1px solid transparent; color:var(--text-muted); font-size:0.75rem; padding:4px 10px; cursor:pointer; font-weight:600; font-family:inherit; border-radius:3px; transition:all 0.15s ease;">TradingView Advanced</button>
                        </div>
                    </div>
                    
                    <!-- Indicator Overlays Bar -->
                    <div id="indicator-overlays-bar" style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
                        <button class="indicator-btn active" id="toggle-sma50" onclick="toggleIndicator('sma50')" style="background: rgba(255, 145, 0, 0.15); border: 1px solid #ff9100; color: #ff9100; font-size: 0.7rem; padding: 3px 8px; cursor: pointer; border-radius: 4px; font-weight: 600; transition: all 0.15s;">SMA 50</button>
                        <button class="indicator-btn active" id="toggle-sma200" onclick="toggleIndicator('sma200')" style="background: rgba(124, 77, 255, 0.15); border: 1px solid #7c4dff; color: #7c4dff; font-size: 0.7rem; padding: 3px 8px; cursor: pointer; border-radius: 4px; font-weight: 600; transition: all 0.15s;">SMA 200</button>
                        <button class="indicator-btn" id="toggle-ema20" onclick="toggleIndicator('ema20')" style="background: transparent; border: 1px solid var(--border-color); color: var(--text-secondary); font-size: 0.7rem; padding: 3px 8px; cursor: pointer; border-radius: 4px; font-weight: 600; transition: all 0.15s;">EMA 20</button>
                        <button class="indicator-btn" id="toggle-bb" onclick="toggleIndicator('bb')" style="background: transparent; border: 1px solid var(--border-color); color: var(--text-secondary); font-size: 0.7rem; padding: 3px 8px; cursor: pointer; border-radius: 4px; font-weight: 600; transition: all 0.15s;">Bollinger Bands</button>
                    </div>
                    
                    <div id="chart-area-container" style="height: clamp(280px, 25vw, 420px); margin-bottom: 20px; position:relative; width:100%;">
                        <div id="tv-chart" style="width: 100%; height: 100%;"></div>
                        <div id="tv-advanced-wrapper" style="width: 100%; height: 100%; display: none; position: absolute; top: 0; left: 0; z-index:10;">
                            <iframe id="tradingview_advanced_iframe" src="" style="width: 100%; height: 100%; border: none;" allowtransparency="true" allowfullscreen></iframe>
                        </div>
                    </div>

                    <!-- Technical Studies Panel -->
                    <div style="margin-top: 15px; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; background-color: rgba(255, 255, 255, 0.01); margin-bottom: 20px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="toggleTechnicalStudies()">
                            <span style="font-size: 0.8rem; font-weight: 700; color: var(--text-primary); text-transform: uppercase;">Technical Study Indicators (RSI & MACD)</span>
                            <span id="studies-chevron" style="font-size: 0.9rem; color: var(--text-secondary); transition: transform 0.2s;">&#9662;</span>
                        </div>
                        <div id="technical-studies-body" style="display: none; flex-direction: column; gap: 20px; margin-top: 12px;">
                            <div style="height: 120px; width: 100%;">
                                <div style="font-size: 0.7rem; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">Relative Strength Index (RSI 14)</div>
                                <div style="height: 90px; width: 100%;">
                                    <canvas id="rsi-chart"></canvas>
                                </div>
                            </div>
                            <div style="height: 120px; width: 100%;">
                                <div style="font-size: 0.7rem; color: var(--text-secondary); margin-bottom: 4px; font-weight: 600;">MACD (12, 26, 9)</div>
                                <div style="height: 90px; width: 100%;">
                                    <canvas id="macd-chart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: flex; flex-direction: column; gap: 14px;">
                        <div class="perf-bar" id="perf-bar-root"></div>
                        <div style="border-top: 1px solid var(--border-color); padding-top: 14px;">
                            <div class="quote-label" style="margin-bottom: 8px;">Investment Thesis Preview</div>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6; font-style: italic;">
                                "{{INVESTMENT_THESIS}}"
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Upcoming Catalysts Widget -->
                <div class="widget">
                    <div class="widget-header">
                        <div class="widget-title" style="color:var(--cyan)">Upcoming Catalysts</div>
                        <div class="widget-badge" style="background-color:rgba(6,182,212,0.1); color:var(--cyan)">MARKET EVENTS</div>
                    </div>
                    <div style="display:flex; flex-direction:column; gap:12px; max-height:480px; overflow-y:auto; padding-right:4px;" id="catalysts-root">
                        <!-- Loaded from JS -->
                    </div>
                </div>
            </div>

            <!-- Grid of Key Metrics Bento -->
            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title">Financial & Valuation Terminal Stats</div>
                    <div class="widget-badge" style="background-color: var(--border-color); color: var(--text-secondary);">RAW yfinance METRICS</div>
                </div>
                <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:10px;">Sources: {{CITE_FUNDAMENTALS}}</div>
                <div class="metrics-bento-grid" id="metrics-root"></div>
            </div>
        </div>

        <!-- ================= PREMIUM DATA & DCF TAB PANEL ================= -->
        <div id="premium" class="tab-panel">
            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title">Discounted Cash Flow (DCF) Engine</div>
                    <div class="widget-badge" style="background-color:rgba(16,185,129,0.1); color:var(--green)">QUANTITATIVE FAIR VALUE</div>
                </div>
                <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:10px;">Source: {{CITE_DCF}}</div>
                {{DCF_WIDGET_HTML}}
            </div>
            
            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title" style="color:var(--accent)">Peer Group Multiples Comparison</div>
                    <div class="widget-badge" style="background-color:rgba(99,102,241,0.1); color:var(--accent)">AI DISCOVERED</div>
                </div>
                <div class="table-container">
                    {{PEERS_WIDGET_HTML}}
                </div>
            </div>
            
            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title" style="color:var(--amber)">Recent Insider Transactions</div>
                    <div class="widget-badge" style="background-color:rgba(245,158,11,0.1); color:var(--amber)">SEC FILINGS</div>
                </div>
                <div class="table-container">
                    {{INSIDERS_WIDGET_HTML}}
                </div>
            </div>
        </div>

        <!-- ================= FINANCIALS TAB PANEL (QUARTERLY) ================= -->
        <div id="financials" class="tab-panel">
            <!-- DuPont & Health Audit Container -->
            <div id="financials-audit-container" class="panel-grid-2" style="margin-bottom: 24px; display: none;">
                <!-- DuPont Decomposition Widget -->
                <div id="dupont-widget-container" class="widget" style="margin-bottom: 0; display: none; border-color: rgba(139, 92, 246, 0.2);">
                    <div class="widget-header">
                        <div class="widget-title" style="color: var(--purple)">DuPont Analysis ROE Decomposition</div>
                        <div class="widget-badge" style="background-color: rgba(139, 92, 246, 0.1); color: var(--purple)">QUANTITATIVE ACCOUNTING</div>
                    </div>
                    <div id="dupont-widget-body" class="panel-grid-3" style="margin-top: 10px;">
                        <!-- Populated dynamically via JS -->
                    </div>
                </div>
                
                <!-- Financial Health & Risk Audit Widget -->
                <div id="health-audit-widget-container" class="widget" style="margin-bottom: 0; display: none; border-color: rgba(6, 182, 212, 0.2);">
                    <div class="widget-header">
                        <div class="widget-title" style="color: var(--cyan)">Financial Health & Risk Audit</div>
                        <div class="widget-badge" style="background-color: rgba(6, 182, 212, 0.1); color: var(--cyan)">RISK METRICS</div>
                    </div>
                    <div id="health-audit-widget-body" class="panel-grid-3" style="margin-top: 10px;">
                        <!-- Populated dynamically via JS -->
                    </div>
                </div>
            </div>

            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title">Quarter-over-Quarter Detailed Statements</div>
                    <div class="financial-statement-selector">
                        <button class="btn-toggle active" onclick="loadStatement('income', this)">Income Statement</button>
                        <button class="btn-toggle" onclick="loadStatement('balance', this)">Balance Sheet</button>
                        <button class="btn-toggle" onclick="loadStatement('cashflow', this)">Cash Flow</button>
                    </div>
                </div>

                <!-- Click-to-Chart Container -->
                <div id="financial-row-chart-container" style="display:none; margin-bottom: 20px; background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 15px; height: 260px; position: relative;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: var(--text-secondary);" id="financial-chart-title">Quarterly Trend</span>
                        <button style="background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 1.2rem; line-height: 1;" onclick="closeFinancialChart()">&times;</button>
                    </div>
                    <div style="height: calc(100% - 30px); width: 100%;">
                        <canvas id="financial-row-chart"></canvas>
                    </div>
                </div>

                <div class="table-container">
                    <table class="statement-table" id="statement-table-root">
                        <!-- Dynamically generated in JS -->
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= QUANTITATIVE MODELS TAB PANEL ================= -->
        <div id="quantitative" class="tab-panel">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                <!-- DDM Card -->
                <div class="widget">
                    <div class="widget-header">
                        <div class="widget-title" style="color: var(--cyan)">Dividend Discount Model (DDM)</div>
                        <div class="widget-badge" style="background-color: rgba(6,182,212,0.1); color: var(--cyan)">VALUATION</div>
                    </div>
                    <div id="ddm-root" style="padding: 15px;">
                        <!-- JS Loaded -->
                    </div>
                </div>

                <!-- Comparable Company Analysis -->
                <div class="widget">
                    <div class="widget-header">
                        <div class="widget-title" style="color: var(--green)">Comparable Company Analysis (CCA)</div>
                        <div class="widget-badge" style="background-color: rgba(34,197,94,0.1); color: var(--green)">MULTIPLES</div>
                    </div>
                    <div id="cca-root" style="padding: 15px;">
                        <!-- JS Loaded -->
                    </div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 15px;">
                <!-- Monte Carlo Simulation -->
                <div class="widget">
                    <div class="widget-header">
                        <div class="widget-title" style="color: var(--yellow)">Monte Carlo DCF Simulation</div>
                        <div class="widget-badge" style="background-color: rgba(234,179,8,0.1); color: var(--yellow)">1,000 TRIALS</div>
                    </div>
                    <div id="monte-carlo-root" style="padding: 15px;">
                        <!-- JS Loaded -->
                    </div>
                </div>

                <!-- Historical Log Growth Channel -->
                <div class="widget">
                    <div class="widget-header">
                        <div class="widget-title" style="color: var(--red)">Historical Growth Regression Channel</div>
                        <div class="widget-badge" style="background-color: rgba(239,68,68,0.1); color: var(--red)">5-YEAR CHANNEL</div>
                    </div>
                    <div id="regression-root" style="padding: 15px;">
                        <!-- JS Loaded -->
                    </div>
                </div>
            </div>
        </div>

        <!-- ================= EXPECTATIONS TAB PANEL ================= -->
        <div id="expectations" class="tab-panel">
            <div class="earnings-grid">
                <!-- Earnings Dates Calendar -->

                <!-- Earnings Dates Calendar -->
                <div class="widget">
                    <div class="widget-header">
                        <div class="widget-title">Earnings dates Calendar & Estimates</div>
                    </div>
                    <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:10px;">Source: {{CITE_EARNINGS}}</div>
                    <div class="earnings-list" id="earnings-dates-root">
                        <!-- Loaded dynamically -->
                    </div>
                </div>
            </div>

            <!-- Consensus Guidance assessment -->
            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title" style="color: var(--cyan)">Guidance & Market Expectations Assessment</div>
                    <div class="widget-badge" style="background-color: rgba(6,182,212,0.1); color: var(--cyan)">AI ANALYZED</div>
                </div>
                <div class="ai-section-box">
                    <p style="font-size: 0.95rem; line-height: 1.8; color: var(--text-primary);">
                        {{GUIDANCE_EXPECTATIONS}}
                    </p>
                </div>
            </div>
        </div>

        <!-- ================= AI RESEARCH NOTE TAB PANEL ================= -->
        <div id="thesis" class="tab-panel">
            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title" style="color: var(--accent)">Institutional Grade Equity Note</div>
                    <div class="widget-badge" style="background-color: var(--accent-glow); color: var(--accent)">GOLDMAN SACHS STYLE NOTE</div>
                </div>
                
                <div class="ai-section-box">
                    <h3>Executive Summary</h3>
                    <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:8px;">Interpretation source: {{CITE_AI}}</div>
                    <p>{{EXECUTIVE_SUMMARY}}</p>
                </div>

                <div class="panel-grid-2">
                    <div class="ai-section-box">
                        <h3>Revenue Quality</h3>
                        <p>{{REVENUE_QUALITY}}</p>
                    </div>
                    <div class="ai-section-box">
                        <h3>Profitability & Margin Expansion</h3>
                        <p>{{PROFITABILITY}}</p>
                    </div>
                </div>

                <div class="ai-section-box">
                    <h3>Competitive Moat Analysis</h3>
                    <p>{{COMPETITIVE_MOAT}}</p>
                </div>

                <div class="panel-grid-2">
                    <div class="ai-section-box">
                        <h3>Earnings Power & Stability</h3>
                        <p>{{EARNINGS_POWER}}</p>
                    </div>
                    <div class="ai-section-box">
                        <h3>Balance Sheet Health</h3>
                        <p>{{BALANCE_SHEET_HEALTH}}</p>
                    </div>
                </div>

                <div class="panel-grid-2" style="margin-top: 16px;">
                    <div class="ai-section-box">
                        <h3>Capital Allocation Discipline</h3>
                        <p>{{CAPITAL_ALLOCATION}}</p>
                    </div>
                    <div class="ai-section-box">
                        <h3>Unit Economics Breakdown</h3>
                        <p>{{UNIT_ECONOMICS}}</p>
                    </div>
                </div>
            </div>

            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title">Source & Data Audit</div>
                    <div class="widget-badge">PROVENANCE</div>
                </div>
                {{SOURCE_AUDIT_HTML}}
            </div>
        </div>

        <!-- ================= MACRO & SENTIMENT TAB PANEL ================= -->
        <div id="macro" class="tab-panel">
            <div class="widget">
                <div class="widget-header">
                    <div class="widget-title" style="color: var(--cyan)">Geopolitical, Macro & Sentiment Analysis</div>
                    <div class="widget-badge" style="background-color: rgba(6,182,212,0.1); color: var(--cyan)">25% DECISION WEIGHT</div>
                </div>
                
                <div class="ai-section-box">
                    <h3>Macro Environment Impact</h3>
                    <p>{{MACRO_ENVIRONMENT}}</p>
                </div>

                <div class="ai-section-box">
                    <h3>Sector Outlook & Regulation</h3>
                    <p>{{SECTOR_OUTLOOK}}</p>
                </div>

                <div class="panel-grid-2" style="margin-bottom: 16px;">
                    <div class="ai-section-box">
                        <h3>Regulatory & Antitrust Threats</h3>
                        <p>{{REGULATORY_ANTITRUST}}</p>
                    </div>
                    <div class="ai-section-box">
                        <h3>Geopolitical Vulnerability</h3>
                        <p>{{GEOPOLITICAL_RISK}}</p>
                    </div>
                </div>

                <!-- Winds side-by-side -->
                <div class="wind-grid">
                    <div class="wind-box">
                        <h4 style="color: var(--green)"><span style="font-size: 1.1rem;">▲</span> Strategic Tailwinds</h4>
                        <ul class="wind-list" id="tailwinds-root">
                            <!-- Loaded from JS -->
                        </ul>
                    </div>
                    <div class="wind-box">
                        <h4 style="color: var(--red)"><span style="font-size: 1.1rem;">▼</span> Strategic Headwinds</h4>
                        <ul class="wind-list" id="headwinds-root">
                            <!-- Loaded from JS -->
                        </ul>
                    </div>
                </div>

                <!-- Sentiment breakdowns -->
                <div class="widget-header" style="margin-top: 20px;">
                    <div class="widget-title" style="color: #a855f7">Wall Street Sentiment consensus</div>
                </div>
                <div class="panel-grid-3">
                    <div class="ai-section-box">
                        <h3>Wall Street Target Sentiment</h3>
                        <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:8px;">Source: {{CITE_ANALYST_TARGETS}}</div>
                        <p>{{ANALYST_SENTIMENT}}</p>
                    </div>
                    <div class="ai-section-box">
                        <h3>Institutional flow Trends</h3>
                        <p>{{INSTITUTIONAL_POSITIONING}}</p>
                    </div>
                    <div class="ai-section-box">
                        <h3>News Mood & Retail Buzz</h3>
                        <div style="font-size:0.72rem; color:var(--text-muted); margin-bottom:8px;">Source: {{CITE_NEWS_SENTIMENT}}</div>
                        <p>{{NEWS_SENTIMENT}}</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- ================= RISKS TAB PANEL ================= -->
        <div id="risks" class="tab-panel">
            <div class="panel-left-heavy">
                <!-- Risk list -->
                <div class="widget">
                    <div class="widget-header">
                        <div class="widget-title" style="color: var(--red)">Risk Factors & Threat Assessment</div>
                        <div class="widget-badge" style="background-color: var(--red-glow); color: var(--red)">14% WEIGHT</div>
                    </div>
                    
                    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.02); padding:20px; border-radius:12px; border:1px solid var(--border-color);">
                        <div>
                            <div style="font-size:0.8rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:1px;">Overall Risk vs Reward Ratio</div>
                            <div style="font-size:1.8rem; font-weight:800; color:var(--text-primary); margin-top:4px;" id="risk-reward-label">{{RISK_REWARD_RATIO}}</div>
                        </div>
                        <div style="width: 120px; height: 60px; position:relative;">
                            <canvas id="gauge-risk-reward"></canvas>
                        </div>
                    </div>
                    
                    <div style="display: flex; flex-direction: column; gap: 14px;" id="risks-list-root">
                        <!-- Loaded from JS -->
                    </div>
                </div>

                <!-- Worst Case & Position size -->
                <div class="workspace-col" style="display: flex; flex-direction: column; gap: 20px;">
                    <!-- Intrinsic Value -->
                    <div class="widget">
                        <div class="widget-header">
                            <div class="widget-title">Intrinsic Value & Margin of Safety</div>
                        </div>
                        <div class="gauge-container">
                            <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6;">
                                {{INTRINSIC_VALUE_ESTIMATE}}
                            </div>
                            <div class="gauge-track">
                                <div class="gauge-marker" id="gauge-marker-point"></div>
                            </div>
                            <div class="gauge-labels">
                                <span>Bear: ${{BEAR_CASE_TARGET}}</span>
                                <span style="color: var(--green); font-weight: 700">Fair: ${{FAIR_VALUE_MID}}</span>
                                <span>Bull: ${{BULL_CASE_TARGET}}</span>
                            </div>
                        </div>
                        <div style="font-size: 0.82rem; color: var(--text-muted);">
                            <strong>Margin of Safety Note:</strong> {{MARGIN_OF_SAFETY}}
                        </div>
                    </div>

                    <div class="widget" style="border-color: rgba(244,63,94,0.3)">
                        <div class="widget-header">
                            <div class="widget-title" style="color: var(--red)">Worst Case Bear Scenario</div>
                        </div>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.7;">
                            {{WORST_CASE_SCENARIO}}
                        </p>
                    </div>

                    <div class="widget">
                        <div class="widget-header">
                            <div class="widget-title" style="color: var(--cyan)">Position Sizing Allocation</div>
                        </div>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.7;">
                            {{POSITION_SIZING}}
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- ================= NOTION RESEARCH HUB PANEL ================= -->
        <div id="notion_hub" class="tab-panel">
            <div class="widget" style="padding: 24px;">
                <div class="widget-header" style="margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="background: var(--accent-glow); border: 1px solid var(--accent); border-radius: 6px; padding: 6px 10px; display: flex; align-items: center; justify-content: center;">
                            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                        </div>
                        <div>
                            <div class="widget-title" style="font-size: 1.2rem; font-weight: 700; color: var(--text-primary);" id="notion-hub-title">Notion Company Hub</div>
                            <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">Sync status: Linked to personal qualitative workspace</div>
                        </div>
                    </div>
                    <div class="widget-badge" style="background-color: var(--accent-glow); color: var(--accent); border: 1px solid var(--accent)30; font-weight: 600; font-size: 0.75rem;">LIVE NOTION INTEGRATION</div>
                </div>
                
                <!-- Notion subnavigation tabs -->
                <div class="notion-sub-nav" id="notion-sub-nav-root">
                    <!-- Dynamic tabs loaded from JS -->
                </div>
                
                <!-- Subpage content containers -->
                <div id="notion-content-area" style="margin-top: 15px; min-height: 250px;">
                    <!-- Dynamic subpage sections will be loaded here from JS -->
                </div>
            </div>
        </div>

    </div>

    <!-- Payload injection -->
    <script>
        async function syncToNotion(ticker) {
            const btn = document.getElementById('notionSyncBtn');
            const originalText = btn.innerText;
            btn.innerText = "Syncing...";
            btn.style.opacity = "0.7";
            btn.disabled = true;
            try {
                const res = await fetch(`/api/notion/sync/${ticker}`, { method: 'POST' });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    btn.innerText = "Synced ✓";
                    btn.style.background = "var(--green)";
                } else {
                    alert("Notion Sync Failed: " + (data.error || "Unknown error"));
                    btn.innerText = originalText;
                }
            } catch (e) {
                alert("Network error: " + e.message);
                btn.innerText = originalText;
            }
            setTimeout(() => {
                if (btn.innerText === "Synced ✓") {
                    btn.innerText = originalText;
                    btn.style.background = "";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                }
            }, 3000);
        }

        let STOCK_DATA = {{RAW_PAYLOAD}};

        // ─── Live Ticker News Polling ───
        async function fetchTickerNews() {
            try {
                const res = await fetch(`/api/news/stock/{{TICKER}}`);
                const data = await res.json();
                if (data.status === 'success' && data.news.length > 0) {
                    const container = document.getElementById('ticker-news-feed');
                    container.innerHTML = '';
                    data.news.forEach(item => {
                        const date = new Date(item.pubDate);
                        const timeStr = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                        const html = `
                            <a href="${item.link}" target="_blank" style="text-decoration:none;">
                                <div class="card" style="padding: 12px; background: rgba(255,255,255,0.02); transition: all 0.2s ease;">
                                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                                        <span style="font-size:0.65rem; color:var(--text-secondary); text-transform:uppercase; font-family:'JetBrains Mono', monospace;">${item.publisher || 'Wire'}</span>
                                        <span style="font-size:0.65rem; color:var(--emerald); font-family:'JetBrains Mono', monospace;">${timeStr}</span>
                                    </div>
                                    <div style="font-size:0.85rem; font-weight:600; color:var(--text-primary); line-height:1.4;">
                                        ${item.title}
                                    </div>
                                </div>
                            </a>
                        `;
                        container.innerHTML += html;
                    });
                }
            } catch (e) {
                console.error("News fetch failed", e);
            }
        }
        
        fetchTickerNews();
        setInterval(fetchTickerNews, 60000); // refresh every minute
    </script>
    
    <script>
        // Reverse DCF Solver (Binary Search method)
        function solveReverseDCF(targetPrice, fcfBase, wacc, tg, cash, debt, shares) {
            if (!targetPrice || targetPrice <= 0 || !fcfBase || fcfBase <= 0 || !shares) return null;
            let low = -0.90;
            let high = 2.00;
            let tolerance = 0.01;
            let maxIterations = 100;
            function calculatePrice(g) {
                if (wacc <= tg) return 0;
                let pv_fcf = 0;
                let current_fcf = fcfBase;
                for (let i = 1; i <= 10; i++) {
                    current_fcf *= (1 + g);
                    pv_fcf += current_fcf / Math.pow(1 + wacc, i);
                }
                const terminal_value = (current_fcf * (1 + tg)) / (wacc - tg);
                const pv_tv = terminal_value / Math.pow(1 + wacc, 10);
                const enterprise_value = pv_fcf + pv_tv;
                const equity_value = enterprise_value + cash - debt;
                let implied = equity_value / shares;
                if (implied < 0) return 0;
                return implied;
            }
            for (let iter = 0; iter < maxIterations; iter++) {
                let mid = (low + high) / 2;
                let midPrice = calculatePrice(mid);
                if (Math.abs(midPrice - targetPrice) < tolerance) return mid;
                if (midPrice < targetPrice) {
                    low = mid;
                } else {
                    high = mid;
                }
            }
            return (low + high) / 2;
        }

        // Main Tab Switcher
        function switchTab(tabId) {
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
            
            const panel = document.getElementById(tabId);
            if (panel) panel.classList.add('active');
            
            // Find active menu item
            const items = document.querySelectorAll('.menu-item');
            items.forEach(item => {
                if (item.getAttribute('onclick').includes(tabId)) {
                    item.classList.add('active');
                }
            });
            
            // Recalculate layout or redraw charts if needed
            window.dispatchEvent(new Event('resize'));
        }

        // Formatter utilities
        function fmt(v, isPct=false) {
            if (v === null || v === undefined || v === 'N/A') return 'N/A';
            if (typeof v === 'string') return v;
            
            if (isPct) {
                return (v * 100).toFixed(2) + '%';
            }
            
            let sign = v < 0 ? '-' : '';
            let absVal = Math.abs(v);
            
            if (absVal >= 1e12) return sign + '$' + (absVal / 1e12).toFixed(2) + 'T';
            if (absVal >= 1e9) return sign + '$' + (absVal / 1e9).toFixed(2) + 'B';
            if (absVal >= 1e6) return sign + '$' + (absVal / 1e6).toFixed(2) + 'M';
            
            return sign + '$' + absVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }

        function fmtNum(v) {
            if (v === null || v === undefined) return 'N/A';
            return v.toLocaleString(undefined, {maximumFractionDigits: 2});
        }

        function pctVal(rawKey, pctKey=null, decimals=2) {
            const pct = m[pctKey || `${rawKey}_pct`];
            if (pct !== null && pct !== undefined && !isNaN(pct)) return Number(pct).toFixed(decimals) + '%';
            const raw = m[rawKey];
            if (raw === null || raw === undefined || raw === 'N/A' || isNaN(raw)) return 'N/A';
            return (Number(raw) * 100).toFixed(decimals) + '%';
        }

        // Render Overview performance tags
        const pRoot = document.getElementById('perf-bar-root');
        const m = STOCK_DATA.metrics;
        const perfs = [
            {k: 'return_1w', l: '1W'},
            {k: 'return_1m', l: '1M'},
            {k: 'return_3m', l: '3M'},
            {k: 'return_6m', l: '6M'},
            {k: 'return_1y', l: '1Y'}
        ];
        perfs.forEach(p => {
            if (m[p.k] !== undefined && m[p.k] !== null) {
                const val = m[p.k];
                const c = val >= 0 ? 'var(--green)' : 'var(--red)';
                const bg = val >= 0 ? 'var(--green-glow)' : 'var(--red-glow)';
                pRoot.innerHTML += `<span class="perf-badge" style="color: ${c}; background-color: ${bg}; border-color: ${c}30">${p.l}: ${val >= 0 ? '+' : ''}${val.toFixed(2)}%</span>`;
            }
        });

        // Render Bento Mini Metric Cards
        const mRoot = document.getElementById('metrics-root');
        const cards = [
            {label: 'Trailing P/E', val: m.trailingPE, sub: `Forward: ${m.forwardPE || 'N/A'}`},
            {label: 'EV / EBITDA', val: m.enterpriseToEbitda, sub: `PEG Ratio: ${m.pegRatio || 'N/A'}`},
            {label: 'Enterprise / Revenue', val: m.enterpriseToRevenue, sub: `Market Cap: ${fmt(m.marketCap)}`},
            {label: 'Total Cash', val: fmt(m.totalCash), sub: `Per share: $${m.totalCashPerShare || 'N/A'}`},
            {label: 'Total Debt', val: fmt(m.totalDebt), sub: `D/E ratio: ${m.debtToEquity || 'N/A'}`},
            {label: 'Gross Profit Margins', val: pctVal('grossMargins'), sub: `Net: ${pctVal('profitMargins')}`},
            {label: 'Return on Equity (ROE)', val: pctVal('returnOnEquity'), sub: `ROA: ${pctVal('returnOnAssets')}`},
            {label: 'Operating Cash Flow', val: fmt(m.operatingCashflow), sub: `Free CF: ${fmt(m.freeCashflow)}`},
            {label: 'Dividend Yield', val: pctVal('dividendYield'), sub: `Payout: ${pctVal('payoutRatio')}`},
            {label: 'Beta volatility', val: m.beta, sub: `Ann. Vol: ${m.volatility_annual ? m.volatility_annual.toFixed(1) + '%' : 'N/A'}`},
            {label: 'Held by Institutions', val: pctVal('heldPercentInstitutions', null, 1), sub: `Insiders: ${pctVal('heldPercentInsiders', null, 1)}`},
            {label: 'Short % of Float', val: pctVal('shortPercentOfFloat'), sub: `Short Ratio: ${m.shortRatio || 'N/A'}`},
            {label: 'Operating Margin', val: pctVal('operatingMargins'), sub: 'Most recent quarter; prior quarters ranged about 22%-54%, not normalized'},
            {label: 'Altman Z-Score', val: (STOCK_DATA.financial_scores && STOCK_DATA.financial_scores.altman_z_label) || 'N/A', sub: 'Solvency Check', color: (STOCK_DATA.financial_scores && STOCK_DATA.financial_scores.altman_z_color) || ''},
            {label: 'Piotroski F-Score', val: (STOCK_DATA.financial_scores && STOCK_DATA.financial_scores.piotroski_f_label) || 'N/A', sub: 'Accounting Health', color: (STOCK_DATA.financial_scores && STOCK_DATA.financial_scores.piotroski_f_color) || ''},
        ];
        cards.forEach(c => {
            const valStyle = c.color ? `style="color: ${c.color}; font-weight: 700;"` : '';
            mRoot.innerHTML += `
                <div class="metric-mini">
                    <div class="metric-mini-label">${c.label}</div>
                    <div class="metric-mini-val" ${valStyle}>${c.val || 'N/A'}</div>
                    <div class="metric-mini-sub">${c.sub}</div>
                </div>
            `;
        });

        // Render winds
        const twList = document.getElementById('tailwinds-root');
        const hwList = document.getElementById('headwinds-root');
        const tw = STOCK_DATA.analysis.macro_analysis.tailwinds || [];
        const hw = STOCK_DATA.analysis.macro_analysis.headwinds || [];
        tw.forEach(x => twList.innerHTML += `<li class="wind-item tailwind">${x}</li>`);
        hw.forEach(x => hwList.innerHTML += `<li class="wind-item headwind">${x}</li>`);

        // Render Intrinsic value Gauge position
        const currPrice = STOCK_DATA.metrics.current_price;
        const low = STOCK_DATA.analysis.bear_case_target || currPrice * 0.7;
        const high = STOCK_DATA.analysis.bull_case_target || currPrice * 1.3;
        
        let pct = ((currPrice - low) / (high - low)) * 100;
        if (pct < 0) pct = 0;
        if (pct > 100) pct = 100;
        document.getElementById('gauge-marker-point').style.left = pct + '%';

        // Render risks factors list
        const risksRoot = document.getElementById('risks-list-root');
        const riskFactors = STOCK_DATA.analysis.risk_assessment.risk_factors || [];
        riskFactors.forEach(rf => {
            const sev = (rf.severity || 'medium').toLowerCase();
            risksRoot.innerHTML += `
                <div class="risk-row-card severity-${sev}">
                    <div class="risk-row-header">
                        <span class="risk-row-title">${rf.risk}</span>
                        <span class="risk-badge ${sev}">${rf.severity}</span>
                    </div>
                    <div class="risk-row-impact">${rf.impact}</div>
                </div>
            `;
        });

        // Render Quarterly Statements dynamically
        function loadStatement(type, btn) {
            document.querySelectorAll('.financial-statement-selector button').forEach(b => b.classList.remove('active'));
            if (btn) {
                btn.classList.add('active');
            } else {
                const buttons = document.querySelectorAll('.financial-statement-selector button');
                if (type === 'income' && buttons[0]) buttons[0].classList.add('active');
                if (type === 'balance' && buttons[1]) buttons[1].classList.add('active');
                if (type === 'cashflow' && buttons[2]) buttons[2].classList.add('active');
            }
            
            let data;
            if (type === 'income') data = STOCK_DATA.q_financials;
            else if (type === 'balance') data = STOCK_DATA.q_balance_sheet;
            else data = STOCK_DATA.q_cashflow;
            
            const root = document.getElementById('statement-table-root');
            root.innerHTML = '';
            
            if (!data.columns || !data.columns.length) {
                root.innerHTML = '<tr><td style="padding: 20px; text-align: center;">No quarterly statement data loaded.</td></tr>';
                return;
            }
            
            let headerHtml = '<tr>';
            data.columns.forEach(c => {
                let displayName = c;
                if (c !== 'Metric') {
                    const d = new Date(c);
                    if (!isNaN(d)) {
                        const q = Math.floor(d.getMonth() / 3) + 1;
                        displayName = `Q${q} '${d.getFullYear().toString().slice(-2)}`;
                    }
                }
                headerHtml += `<th>${displayName}</th>`;
            });
            headerHtml += '</tr>';
            root.innerHTML += headerHtml;
            
            data.rows.forEach(row => {
                const isHeaderItem = ['Total Revenue', 'Net Income', 'Gross Profit', 'Operating Income', 
                                      'Total Assets', 'Total Liabilities', 'Total Liabilities And Equity',
                                      'Cash Flow From Operating Activities', 'Net Income From Continuing Operations'].includes(row.Metric);
                
                let rowHtml = `<tr class="${isHeaderItem ? 'header-row' : ''} interactive-row" onclick="chartFinancialRow('${row.Metric.replace(/'/g, "\\'")}', '${type}')">`;
                data.columns.forEach(col => {
                    const val = row[col];
                    if (col === 'Metric') {
                        rowHtml += `<td class="metric-name">${val}</td>`;
                    } else {
                        let printVal = '-';
                        let cellStyle = '';
                        if (val !== null && val !== undefined) {
                            let sign = val < 0 ? '-' : '';
                            let abs = Math.abs(val);
                            if (abs >= 1e9) printVal = sign + (abs / 1e9).toFixed(2) + 'B';
                            else if (abs >= 1e6) printVal = sign + (abs / 1e6).toFixed(2) + 'M';
                            else printVal = sign + abs.toLocaleString();
                            
                            if (val < 0) {
                                cellStyle = ' style="color: var(--red); font-weight: 500;"';
                            } else if (val > 0 && ['Net Income', 'Operating Income', 'Gross Profit', 'Total Revenue', 'Cash Flow From Operating Activities'].includes(row.Metric)) {
                                cellStyle = ' style="color: var(--green); font-weight: 600;"';
                            }
                        }
                        rowHtml += `<td class="val-cell"${cellStyle}>${printVal}</td>`;
                    }
                });
                rowHtml += '</tr>';
                root.innerHTML += rowHtml;
            });
        }
        
        let financialChartInstance = null;
        function chartFinancialRow(metricName, type) {
            let data;
            if (type === 'income') data = STOCK_DATA.q_financials;
            else if (type === 'balance') data = STOCK_DATA.q_balance_sheet;
            else data = STOCK_DATA.q_cashflow;
            
            if (!data) return;
            const row = data.rows.find(r => r.Metric === metricName);
            if (!row) return;
            
            const dateCols = data.columns.filter(c => c !== 'Metric');
            const sortedCols = [...dateCols].sort((a, b) => new Date(a) - new Date(b));
            
            const labels = sortedCols.map(c => {
                const d = new Date(c);
                if (isNaN(d)) return c;
                const q = Math.floor(d.getMonth() / 3) + 1;
                return `Q${q} '${d.getFullYear().toString().slice(-2)}`;
            });
            
            const values = sortedCols.map(c => row[c]);
            
            document.getElementById('financial-row-chart-container').style.display = 'block';
            document.getElementById('financial-chart-title').innerText = `${metricName} — Quarterly Progression`;
            
            const ctx = document.getElementById('financial-row-chart').getContext('2d');
            if (financialChartInstance) {
                financialChartInstance.destroy();
            }
            
            financialChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: metricName,
                        data: values,
                        backgroundColor: 'rgba(37, 99, 235, 0.4)',
                        borderColor: '#2563eb',
                        borderWidth: 1.5,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let v = context.parsed.y;
                                    let sign = v < 0 ? '-' : '';
                                    let abs = Math.abs(v);
                                    if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(2) + 'B';
                                    if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(2) + 'M';
                                    return sign + '$' + abs.toLocaleString();
                                }
                            }
                        }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: '#9ca3af' } },
                        y: { 
                            grid: { color: 'rgba(255, 255, 255, 0.05)' }, 
                            ticks: { 
                                color: '#9ca3af',
                                callback: function(value) {
                                    let sign = value < 0 ? '-' : '';
                                    let abs = Math.abs(value);
                                    if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(1) + 'B';
                                    if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(1) + 'M';
                                    return sign + '$' + abs.toLocaleString();
                                }
                            } 
                        }
                    }
                }
            });
        }
        
        function closeFinancialChart() {
            document.getElementById('financial-row-chart-container').style.display = 'none';
            if (financialChartInstance) {
                financialChartInstance.destroy();
                financialChartInstance = null;
            }
        }

        // Render DuPont Analysis if available
        const dupontRoot = document.getElementById('dupont-widget-body');
        const dupontContainer = document.getElementById('dupont-widget-container');
        const auditRoot = document.getElementById('health-audit-widget-body');
        const auditContainer = document.getElementById('health-audit-widget-container');
        const financialsAuditParent = document.getElementById('financials-audit-container');

        const dp = STOCK_DATA.financial_scores && STOCK_DATA.financial_scores.dupont;
        const scores = STOCK_DATA.financial_scores;

        let hasAnyAudit = false;

        if (dp && dupontRoot) {
            dupontContainer.style.display = 'block';
            hasAnyAudit = true;
            dupontRoot.innerHTML = `
                <div class="ai-section-box" style="text-align: center; border-color: rgba(139, 92, 246, 0.2);">
                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Net Profit Margin</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: var(--cyan); margin: 8px 0; font-family: 'JetBrains Mono', monospace;">${dp.net_margin.toFixed(2)}%</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">Net Income / Total Revenue</div>
                </div>
                <div class="ai-section-box" style="text-align: center; border-color: rgba(139, 92, 246, 0.2);">
                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Asset Turnover</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: var(--amber); margin: 8px 0; font-family: 'JetBrains Mono', monospace;">${dp.asset_turnover.toFixed(2)}x</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">Total Revenue / Total Assets</div>
                </div>
                <div class="ai-section-box" style="text-align: center; border-color: rgba(139, 92, 246, 0.2);">
                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Equity Multiplier</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: var(--red); margin: 8px 0; font-family: 'JetBrains Mono', monospace;">${dp.equity_multiplier.toFixed(2)}x</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">Total Assets / Stockholders Equity</div>
                </div>
                <div style="grid-column: span 3; text-align: center; margin-top: 10px; font-size: 0.95rem; color: var(--text-primary); border-top: 1px dashed var(--border-color); padding-top: 12px;">
                    Decomposed Return on Equity (ROE): 
                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--green); font-size: 1.1rem;">
                        ${dp.net_margin.toFixed(2)}% &times; ${dp.asset_turnover.toFixed(2)} &times; ${dp.equity_multiplier.toFixed(2)} = ${dp.roe_computed.toFixed(2)}%
                    </span>
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 5px;">
                        *Note: ${dp.note || `DuPont uses full-year annual financial statement figures. Spot or TTM reported ROE (${STOCK_DATA.metrics.returnOnEquity ? (STOCK_DATA.metrics.returnOnEquity * 100).toFixed(2) + '%' : 'N/A'}) may differ due to recent quarterly variations.`}
                    </div>
                </div>
            `;
        } else {
            if (dupontContainer) dupontContainer.style.display = 'none';
        }

        if (scores && (scores.altman_z !== null || scores.piotroski_f !== null || scores.beneish_m !== null) && auditRoot) {
            if (auditContainer) auditContainer.style.display = 'block';
            hasAnyAudit = true;

            const az_val = scores.altman_z !== null ? scores.altman_z.toFixed(2) : 'N/A';
            const az_lbl = scores.altman_z_label || 'N/A';
            const az_clr = scores.altman_z_color || 'var(--text-muted)';

            const pf_val = scores.piotroski_f !== null ? scores.piotroski_f : 'N/A';
            const pf_lbl = scores.piotroski_f_label || 'N/A';
            const pf_clr = scores.piotroski_f_color || 'var(--text-muted)';

            const bm_val = scores.beneish_m !== null ? scores.beneish_m.toFixed(2) : 'N/A';
            const bm_lbl = scores.beneish_m_label || 'N/A';
            const bm_clr = scores.beneish_m_color || 'var(--text-muted)';

            let execSummary = "";
            if (scores.altman_z !== null) {
                if (scores.altman_z < 1.81) execSummary += `⚠️ <b>Altman Z:</b> Distress zone (${az_val}) indicates elevated insolvency/credit risk. `;
                else if (scores.altman_z < 2.99) execSummary += `<b>Altman Z:</b> Grey zone (${az_val}) indicates moderate solvency risk. `;
                else execSummary += `✅ <b>Altman Z:</b> Safe zone (${az_val}) indicates strong balance sheet solvency. `;
            }
            if (scores.piotroski_f !== null) {
                if (scores.piotroski_f < 4) execSummary += `⚠️ <b>Piotroski F:</b> Low score (${pf_val}/9) flags weak operational momentum. `;
                else if (scores.piotroski_f >= 8) execSummary += `✅ <b>Piotroski F:</b> High score (${pf_val}/9) signals exceptional business health. `;
                else execSummary += `<b>Piotroski F:</b> Score of ${pf_val}/9 reflects stable operational quality. `;
            }
            if (scores.beneish_m !== null) {
                if (scores.beneish_m > -1.78) execSummary += `⚠️ <b>Beneish M:</b> Score of ${bm_val} flags potential earnings manipulation risk. `;
                else execSummary += `✅ <b>Beneish M:</b> Score of ${bm_val} indicates a low likelihood of accounting manipulation. `;
            }

            auditRoot.innerHTML = `
                <div class="ai-section-box" style="text-align: center; border-color: ${az_clr}40;">
                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Altman Z-Score</div>
                    <div style="font-size: 1.6rem; font-weight: 700; color: ${az_clr}; margin: 8px 0; font-family: 'JetBrains Mono', monospace;">${az_val}</div>
                    <div style="font-size: 0.75rem; font-weight: 500; color: ${az_clr};">${az_lbl.split(' ')[0]}</div>
                </div>
                <div class="ai-section-box" style="text-align: center; border-color: ${pf_clr}40;">
                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Piotroski F-Score</div>
                    <div style="font-size: 1.6rem; font-weight: 700; color: ${pf_clr}; margin: 8px 0; font-family: 'JetBrains Mono', monospace;">${pf_val}/9</div>
                    <div style="font-size: 0.75rem; font-weight: 500; color: ${pf_clr};">${pf_lbl.split('/')[0] >= 8 ? 'Strong' : pf_lbl.split('/')[0] >= 4 ? 'Stable' : 'Weak'}</div>
                </div>
                <div class="ai-section-box" style="text-align: center; border-color: ${bm_clr}40;">
                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Beneish M-Score</div>
                    <div style="font-size: 1.6rem; font-weight: 700; color: ${bm_clr}; margin: 8px 0; font-family: 'JetBrains Mono', monospace;">${bm_val}</div>
                    <div style="font-size: 0.75rem; font-weight: 500; color: ${bm_clr};">${bm_lbl.startsWith('High') ? 'High Risk' : 'Low Risk'}</div>
                </div>
                <div style="grid-column: span 3; text-align: left; margin-top: 10px; font-size: 0.85rem; color: var(--text-secondary); border-top: 1px dashed var(--border-color); padding-top: 12px; line-height: 1.4;">
                    ${execSummary}
                </div>
            `;
        } else {
            if (auditContainer) auditContainer.style.display = 'none';
        }

        if (hasAnyAudit && financialsAuditParent) {
            financialsAuditParent.style.display = 'grid';
        }
        
        loadStatement('income');

        // Render earnings calendar dates
        const datesRoot = document.getElementById('earnings-dates-root');
        const ed = STOCK_DATA.earnings_dates || [];
        if (!ed.length) {
            datesRoot.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; padding: 20px; text-align: center;">No upcoming earnings dates found.</div>';
        } else {
            ed.slice(0, 5).forEach(row => {
                let estVal = row['EPS Estimate'] !== null ? '$' + row['EPS Estimate'].toFixed(2) : 'N/A';
                datesRoot.innerHTML += `
                    <div class="earnings-row">
                        <div class="earnings-date-tag">${row.Date}</div>
                        <div class="earnings-estimates">
                            <span style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">EPS Estimate</span>
                            <span style="font-weight: 700; color: var(--cyan)">${estVal}</span>
                        </div>
                    </div>
                `;
            });
        }
        // Helper to draw half-doughnut gauge with needle
        function drawGauge(canvasId, value, min, max, colors) {
            const ctx = document.getElementById(canvasId);
            if (!ctx) return;
            let pct = (value - min) / (max - min);
            if (pct > 1) pct = 1;
            if (pct < 0) pct = 0;
            
            const needlePercent = pct * 100;
            
            // Draw static zones (33.3% each)
            const arcData = [33.3, 33.4, 33.3];
            const bgColors = colors;
            
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: arcData,
                        backgroundColor: bgColors.map(c => c + '30'), // Semi-transparent arcs
                        borderColor: bgColors,
                        borderWidth: 1.5,
                        circumference: 180,
                        rotation: 270
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '85%',
                    plugins: { tooltip: { enabled: false }, legend: { display: false } },
                    animation: { animateRotate: true, animateScale: false }
                },
                plugins: [{
                    id: 'gaugeNeedle',
                    afterDatasetsDraw(chart) {
                        const { ctx } = chart;
                        ctx.save();
                        const meta = chart.getDatasetMeta(0);
                        if (!meta || !meta.data || !meta.data[0]) return;
                        
                        const x = meta.data[0].x;
                        const y = meta.data[0].y;
                        const outerRadius = meta.data[0].outerRadius;
                        
                        const angle = Math.PI + (needlePercent / 100) * Math.PI;
                        
                        ctx.translate(x, y);
                        ctx.rotate(angle);
                        
                        // Needle path
                        ctx.beginPath();
                        ctx.moveTo(0, -3);
                        ctx.lineTo(outerRadius - 6, 0);
                        ctx.lineTo(0, 3);
                        ctx.closePath();
                        ctx.fillStyle = '#fafafa';
                        ctx.fill();
                        
                        // Pivot circle
                        ctx.beginPath();
                        ctx.arc(0, 0, 5, 0, Math.PI * 2);
                        ctx.fillStyle = '#fafafa';
                        ctx.fill();
                        ctx.restore();
                    }
                }]
            });
        }

        // Render Bento Gauges
        const mgmtScore = parseInt('{{MGMT}}') || 5;
        drawGauge('gauge-mgmt', mgmtScore, 1, 10, ['#ef4444', '#a855f7', '#3b82f6']);
        
        // Sentiment Gauge Mapping
        const sentMap = {'VERY BEARISH': 1, 'BEARISH': 3, 'NEUTRAL': 5, 'BULLISH': 7, 'VERY BULLISH': 10};
        const sVal = sentMap['{{SENT_LABEL}}'] || 5;
        drawGauge('gauge-sent', sVal, 1, 10, ['#ef4444', '#f59e0b', '#06b6d4']);
        
        // Valuation Gauge Mapping
        const valMap = {'DEEPLY OVERVALUED': 1, 'OVERVALUED': 3, 'FAIRLY VALUED': 5, 'UNDERVALUED': 7, 'DEEPLY UNDERVALUED': 10};
        const vVal = valMap['{{VAL_GRADE}}'] || 5;
        drawGauge('gauge-val', vVal, 1, 10, ['#ef4444', '#f59e0b', '#10b981']);

        // Risk vs Reward Gauge
        const rrMap = {'VERY UNFAVORABLE': 1, 'UNFAVORABLE': 3, 'NEUTRAL': 5, 'FAVORABLE': 7, 'VERY FAVORABLE': 10};
        const rrVal = rrMap['{{RISK_REWARD_RATIO}}'] || 5;
        drawGauge('gauge-risk-reward', rrVal, 1, 10, ['#ef4444', '#f59e0b', '#10b981']);

        // Interactive DCF Calculator
        const waccSlider = document.getElementById('wacc-slider');
        const tgSlider = document.getElementById('tg-slider');
        const waccVal = document.getElementById('wacc-val');
        const tgVal = document.getElementById('tg-val');
        const livePrice = document.getElementById('dcf-live-value');
        const fcfBase = parseFloat(document.getElementById('dcf-base-fcf')?.dataset.fcf || 0);

        function updateDCF() {
            if(!waccSlider || !fcfBase) return;
            const wacc = parseFloat(waccSlider.value) / 100;
            const tg = parseFloat(tgSlider.value) / 100;
            
            waccVal.innerText = waccSlider.value + '%';
            tgVal.innerText = tgSlider.value + '%';
            
            // Standard DCF
            let growth_rate_1_5 = parseFloat('{{GROWTH_RATE_DCF}}') / 100;
            if(isNaN(growth_rate_1_5)) growth_rate_1_5 = 0.15;
            // Stage 2 Linear Decay setup
            let decay_step = growth_rate_1_5 > tg ? (growth_rate_1_5 - tg) / 6 : 0;
            
            let pv_fcf = 0;
            let current_fcf = fcfBase;
            for (let i = 1; i <= 10; i++) {
                let gr = growth_rate_1_5;
                if (i > 5) {
                    gr = Math.max(tg, growth_rate_1_5 - (decay_step * (i - 5)));
                }
                current_fcf *= (1 + gr);
                pv_fcf += current_fcf / Math.pow(1 + wacc, i - 0.5); // Mid-year convention
            }
            
            const terminal_value = (current_fcf * (1 + tg)) / Math.max(wacc - tg, 0.005);
            const pv_tv = terminal_value / Math.pow(1 + wacc, 10);
            
            const enterprise_value = pv_fcf + pv_tv;
            const cash = STOCK_DATA.metrics.totalCash || 0;
            const debt = STOCK_DATA.metrics.totalDebt || 0;
            let shares = STOCK_DATA.metrics.sharesOutstanding;
            if (!shares || shares <= 1) {
                const mc = STOCK_DATA.metrics.marketCap;
                const price = STOCK_DATA.metrics.current_price;
                if (mc && price) {
                    shares = mc / price;
                } else {
                    shares = 1;
                }
            }
            
            const equity_value = enterprise_value + cash - debt;
            let implied_price = equity_value / shares;
            if(implied_price < 0 || wacc <= tg) implied_price = 0;
            
            const raw_dcf_price = implied_price;

            // Apply forward EPS sanity check in Javascript if conditions match
            const forward_eps = STOCK_DATA.metrics.forwardEps;
            const forward_pe = STOCK_DATA.metrics.forwardPE;
            const earnings_growth = STOCK_DATA.metrics.earningsGrowth || 0;
            const current_price = STOCK_DATA.metrics.current_price;
            let valuation_basis = "FCF DCF";
            let adjusted_implied_price = implied_price;

            if (forward_eps && current_price && forward_pe && forward_eps > 0 && implied_price < current_price * 0.55) {
                const current_forward_multiple = current_price / forward_eps;
                let target_forward_multiple = Math.max(current_forward_multiple, Math.min(15.0, Math.max(forward_pe * 1.25, forward_pe + 2.0)));
                if (earnings_growth && earnings_growth > 0.25) {
                    target_forward_multiple = Math.max(target_forward_multiple, Math.min(18.0, forward_pe * 1.5));
                }
                const eps_implied_price = forward_eps * target_forward_multiple;
                if (eps_implied_price > implied_price) {
                    adjusted_implied_price = eps_implied_price;
                    valuation_basis = "Forward EPS sanity-adjusted DCF";
                }
            }

            livePrice.innerText = '$' + adjusted_implied_price.toFixed(2);

            const badgeEl = document.getElementById('dcf-adjustment-badge');
            if (badgeEl) {
                if (valuation_basis.includes("sanity-adjusted")) {
                    badgeEl.innerText = "EPS-ADJUSTED";
                    badgeEl.style.backgroundColor = "rgba(6, 182, 212, 0.15)";
                    badgeEl.style.color = "var(--cyan)";
                    badgeEl.style.display = "inline-block";
                } else {
                    badgeEl.style.display = "none";
                }
            }

            // Update Basis and Raw DCF fields if they exist in the UI
            const basisEl = document.getElementById('dcf-basis-info');
            const rawEl = document.getElementById('dcf-raw-info');
            if (basisEl) {
                basisEl.innerText = "Basis: " + valuation_basis;
            }
            if (rawEl) {
                rawEl.innerHTML = `Raw DCF before sanity check: $${raw_dcf_price.toFixed(2)}` + 
                    (valuation_basis.includes("sanity-adjusted") ? 
                        ` <span style="color:var(--red); font-weight:600; font-size:0.7rem;">(Trailing FCF depressed by Capex)</span>` : '');
            }

            // Solve Reverse DCF
            const impliedG = solveReverseDCF(
                STOCK_DATA.metrics.current_price, 
                fcfBase, 
                wacc, 
                tg, 
                cash, 
                debt, 
                shares
            );
            const impliedGrowthEl = document.getElementById('reverse-dcf-implied-growth');
            if (impliedGrowthEl) {
                if (impliedG !== null) {
                    impliedGrowthEl.innerText = (impliedG * 100).toFixed(2) + "%";
                } else {
                    impliedGrowthEl.innerText = "N/A";
                }
            }
        }

        if(waccSlider) waccSlider.addEventListener('input', updateDCF);
        if(tgSlider) tgSlider.addEventListener('input', updateDCF);

        // Scenario Preset Buttons Event Listeners
        const baseWacc = parseFloat(waccSlider?.value || (STOCK_DATA.dcf_data ? STOCK_DATA.dcf_data.wacc_used : 9.0));
        
        document.querySelectorAll('.btn-scenario').forEach(btn => {
            btn.addEventListener('click', function() {
                const scenario = this.getAttribute('data-scenario');
                
                // Toggle active class on buttons
                document.querySelectorAll('.btn-scenario').forEach(b => {
                    b.classList.remove('active');
                });
                this.classList.add('active');
                
                if (scenario === 'bear') {
                    if (waccSlider) waccSlider.value = (baseWacc + 1.5).toFixed(1);
                    if (tgSlider) tgSlider.value = '1.5';
                } else if (scenario === 'base') {
                    if (waccSlider) waccSlider.value = baseWacc.toFixed(1);
                    if (tgSlider) tgSlider.value = '2.5';
                } else if (scenario === 'bull') {
                    if (waccSlider) waccSlider.value = Math.max(6.0, baseWacc - 1.5).toFixed(1);
                    if (tgSlider) tgSlider.value = '3.5';
                }
                
                updateDCF();
            });
        });
        
        // Initial solver call
        updateDCF();
        setTimeout(updateDCF, 100);

        // PDF download function with multi-page printing layout support
        function downloadPDF() {
            const body = document.body;
            body.classList.add('printing-pdf');
            
            // Dispatch a resize event so TradingView charts size correctly inside the printing layout
            window.dispatchEvent(new Event('resize'));
            
            setTimeout(() => {
                const opt = {
                    margin:       [10, 10, 10, 10],
                    filename:     STOCK_DATA.ticker + '_Terminal_Report.pdf',
                    image:        { type: 'jpeg', quality: 0.98 },
                    html2canvas:  { scale: 1.5, useCORS: true, backgroundColor: '#06070d' },
                    jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' },
                    pagebreak:    { mode: ['avoid-all', 'css', 'legacy'] }
                };
                
                html2pdf().set(opt).from(body).save()
                    .then(() => {
                        body.classList.remove('printing-pdf');
                        window.dispatchEvent(new Event('resize'));
                    })
                    .catch(err => {
                        console.error("PDF generation error:", err);
                        body.classList.remove('printing-pdf');
                        window.dispatchEvent(new Event('resize'));
                    });
            }, 500);
        }
             // TradingView Lightweight Charts with SMA, EMA, BB overlays and Volume Histograms
        const chartContainer = document.getElementById('tv-chart');
        let chart = null;
        let lineSeries = null;
        let sma50Series = null;
        let sma200Series = null;
        let ema20Series = null;
        let bbUpperSeries = null;
        let bbLowerSeries = null;
        let volumeSeries = null;

        // Keep track of toggle states
        const activeIndicators = {
            sma50: true,
            sma200: true,
            ema20: false,
            bb: false
        };

        if(chartContainer && STOCK_DATA.chart_data && STOCK_DATA.chart_data.close.length > 0) {
            try {
                if (typeof LightweightCharts !== 'undefined') {
                    chart = LightweightCharts.createChart(chartContainer, {
                        autoSize: true,
                        width: chartContainer.clientWidth || 800,
                        height: chartContainer.clientHeight || 350,
                        layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#9ca3af' },
                        grid: { vertLines: { color: 'rgba(255,255,255,0.05)' }, horzLines: { color: 'rgba(255,255,255,0.05)' } },
                        rightPriceScale: { borderVisible: false },
                        timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true }
                    });
                    
                    // Price line
                    lineSeries = chart.addSeries(LightweightCharts.LineSeries, { color: '#10b981', lineWidth: 2, title: 'Price' });
                    const data = [];
                    for(let i=0; i<STOCK_DATA.chart_data.close.length; i++) {
                        if(STOCK_DATA.chart_data.close[i] !== null && STOCK_DATA.chart_data.close[i] !== undefined) {
                            data.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.close[i] });
                        }
                    }
                    lineSeries.setData(data);

                    // Volume overlay at bottom 15% of pane
                    volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
                        color: 'rgba(37, 99, 235, 0.15)',
                        priceFormat: { type: 'volume' },
                        priceScaleId: '', // Overlay on main price axis
                    });
                    volumeSeries.priceScale().applyOptions({
                        scaleMargins: { top: 0.8, bottom: 0 } // Bottom 20%
                    });

                    const volumeData = [];
                    for(let i=0; i<STOCK_DATA.chart_data.volume.length; i++) {
                        if(STOCK_DATA.chart_data.volume[i] !== null && STOCK_DATA.chart_data.volume[i] !== undefined) {
                            const isUp = STOCK_DATA.chart_data.close[i] >= (STOCK_DATA.chart_data.close[i-1] || STOCK_DATA.chart_data.close[i]);
                            volumeData.push({
                                time: STOCK_DATA.chart_data.labels[i],
                                value: STOCK_DATA.chart_data.volume[i],
                                color: isUp ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)'
                            });
                        }
                    }
                    volumeSeries.setData(volumeData);

                    // SMA 50
                    sma50Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#ff9100', lineWidth: 1.5, title: 'SMA 50' });
                    const sma50Data = [];
                    for(let i=0; i<STOCK_DATA.chart_data.sma50.length; i++) {
                        if(STOCK_DATA.chart_data.sma50[i] !== null && STOCK_DATA.chart_data.sma50[i] !== undefined) {
                            sma50Data.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.sma50[i] });
                        }
                    }
                    sma50Series.setData(sma50Data);
                    
                    // SMA 200
                    sma200Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#7c4dff', lineWidth: 1.5, title: 'SMA 200' });
                    const sma200Data = [];
                    for(let i=0; i<STOCK_DATA.chart_data.sma200.length; i++) {
                        if(STOCK_DATA.chart_data.sma200[i] !== null && STOCK_DATA.chart_data.sma200[i] !== undefined) {
                            sma200Data.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.sma200[i] });
                        }
                    }
                    sma200Series.setData(sma200Data);

                    // EMA 20 (initially hidden)
                    ema20Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#06b6d4', lineWidth: 1.5, title: 'EMA 20' });
                    const ema20Data = [];
                    if (STOCK_DATA.chart_data.ema20) {
                        for(let i=0; i<STOCK_DATA.chart_data.ema20.length; i++) {
                            if(STOCK_DATA.chart_data.ema20[i] !== null && STOCK_DATA.chart_data.ema20[i] !== undefined) {
                                ema20Data.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.ema20[i] });
                            }
                        }
                    }
                    ema20Series.setData(ema20Data);
                    // Hide initially
                    chart.removeSeries(ema20Series);
                    ema20Series = null;

                    // Bollinger Bands Upper/Lower (initially hidden)
                    bbUpperSeries = chart.addSeries(LightweightCharts.LineSeries, { color: 'rgba(16, 185, 129, 0.4)', lineWidth: 1, title: 'BB Upper', lineStyle: 2 });
                    bbLowerSeries = chart.addSeries(LightweightCharts.LineSeries, { color: 'rgba(16, 185, 129, 0.4)', lineWidth: 1, title: 'BB Lower', lineStyle: 2 });
                    const bbUpperData = [];
                    const bbLowerData = [];
                    if (STOCK_DATA.chart_data.bb_upper && STOCK_DATA.chart_data.bb_lower) {
                        for(let i=0; i<STOCK_DATA.chart_data.bb_upper.length; i++) {
                            if(STOCK_DATA.chart_data.bb_upper[i] !== null && STOCK_DATA.chart_data.bb_upper[i] !== undefined) {
                                bbUpperData.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.bb_upper[i] });
                            }
                            if(STOCK_DATA.chart_data.bb_lower[i] !== null && STOCK_DATA.chart_data.bb_lower[i] !== undefined) {
                                bbLowerData.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.bb_lower[i] });
                            }
                        }
                    }
                    bbUpperSeries.setData(bbUpperData);
                    bbLowerSeries.setData(bbLowerData);
                    // Hide initially
                    chart.removeSeries(bbUpperSeries);
                    chart.removeSeries(bbLowerSeries);
                    bbUpperSeries = null;
                    bbLowerSeries = null;

                    chart.timeScale().fitContent();

                    // Refit scale content when window size or tabs change
                    window.addEventListener('resize', () => {
                        if (chart) {
                            chart.timeScale().fitContent();
                        }
                    });
                } else {
                    console.warn("TradingView LightweightCharts is undefined.");
                    chartContainer.innerHTML = `<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--text-muted); font-size: 0.9rem; gap: 8px;">
                        <span style="font-size: 1.5rem;">⚠️</span>
                        <span>TradingView chart library failed to load.</span>
                        <span style="font-size: 0.75rem; color: var(--text-muted);">Please check your network connection or try switching to TradingView Advanced.</span>
                    </div>`;
                }
            } catch (err) {
                console.error("Error creating LightweightChart:", err);
                chartContainer.innerHTML = `<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--text-muted); font-size: 0.9rem; gap: 8px;">
                    <span style="font-size: 1.5rem;">⚠️</span>
                    <span>Failed to initialize chart components.</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted);">${err.message}</span>
                </div>`;
            }
        }

        // Toggle Indicators handler
        window.toggleIndicator = function(name) {
            if (!chart) return;
            const btn = document.getElementById('toggle-' + name);
            if (!btn) return;

            activeIndicators[name] = !activeIndicators[name];

            if (name === 'sma50') {
                if (activeIndicators.sma50) {
                    sma50Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#ff9100', lineWidth: 1.5, title: 'SMA 50' });
                    const sma50Data = [];
                    for(let i=0; i<STOCK_DATA.chart_data.sma50.length; i++) {
                        if(STOCK_DATA.chart_data.sma50[i] !== null && STOCK_DATA.chart_data.sma50[i] !== undefined) {
                            sma50Data.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.sma50[i] });
                        }
                    }
                    sma50Series.setData(sma50Data);
                    btn.classList.add('active');
                    btn.style.background = 'rgba(255, 145, 0, 0.15)';
                    btn.style.borderColor = '#ff9100';
                    btn.style.color = '#ff9100';
                } else {
                    if (sma50Series) {
                        chart.removeSeries(sma50Series);
                        sma50Series = null;
                    }
                    btn.classList.remove('active');
                    btn.style.background = 'transparent';
                    btn.style.borderColor = 'var(--border-color)';
                    btn.style.color = 'var(--text-secondary)';
                }
            } else if (name === 'sma200') {
                if (activeIndicators.sma200) {
                    sma200Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#7c4dff', lineWidth: 1.5, title: 'SMA 200' });
                    const sma200Data = [];
                    for(let i=0; i<STOCK_DATA.chart_data.sma200.length; i++) {
                        if(STOCK_DATA.chart_data.sma200[i] !== null && STOCK_DATA.chart_data.sma200[i] !== undefined) {
                            sma200Data.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.sma200[i] });
                        }
                    }
                    sma200Series.setData(sma200Data);
                    btn.classList.add('active');
                    btn.style.background = 'rgba(124, 77, 255, 0.15)';
                    btn.style.borderColor = '#7c4dff';
                    btn.style.color = '#7c4dff';
                } else {
                    if (sma200Series) {
                        chart.removeSeries(sma200Series);
                        sma200Series = null;
                    }
                    btn.classList.remove('active');
                    btn.style.background = 'transparent';
                    btn.style.borderColor = 'var(--border-color)';
                    btn.style.color = 'var(--text-secondary)';
                }
            } else if (name === 'ema20') {
                if (activeIndicators.ema20) {
                    ema20Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#06b6d4', lineWidth: 1.5, title: 'EMA 20' });
                    const ema20Data = [];
                    for(let i=0; i<STOCK_DATA.chart_data.ema20.length; i++) {
                        if(STOCK_DATA.chart_data.ema20[i] !== null && STOCK_DATA.chart_data.ema20[i] !== undefined) {
                            ema20Data.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.ema20[i] });
                        }
                    }
                    ema20Series.setData(ema20Data);
                    btn.classList.add('active');
                    btn.style.background = 'rgba(6, 182, 212, 0.15)';
                    btn.style.borderColor = '#06b6d4';
                    btn.style.color = '#06b6d4';
                } else {
                    if (ema20Series) {
                        chart.removeSeries(ema20Series);
                        ema20Series = null;
                    }
                    btn.classList.remove('active');
                    btn.style.background = 'transparent';
                    btn.style.borderColor = 'var(--border-color)';
                    btn.style.color = 'var(--text-secondary)';
                }
            } else if (name === 'bb') {
                if (activeIndicators.bb) {
                    bbUpperSeries = chart.addSeries(LightweightCharts.LineSeries, { color: 'rgba(16, 185, 129, 0.4)', lineWidth: 1, title: 'BB Upper', lineStyle: 2 });
                    bbLowerSeries = chart.addSeries(LightweightCharts.LineSeries, { color: 'rgba(16, 185, 129, 0.4)', lineWidth: 1, title: 'BB Lower', lineStyle: 2 });
                    const bbUpperData = [];
                    const bbLowerData = [];
                    for(let i=0; i<STOCK_DATA.chart_data.bb_upper.length; i++) {
                        if(STOCK_DATA.chart_data.bb_upper[i] !== null && STOCK_DATA.chart_data.bb_upper[i] !== undefined) {
                            bbUpperData.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.bb_upper[i] });
                        }
                        if(STOCK_DATA.chart_data.bb_lower[i] !== null && STOCK_DATA.chart_data.bb_lower[i] !== undefined) {
                            bbLowerData.push({ time: STOCK_DATA.chart_data.labels[i], value: STOCK_DATA.chart_data.bb_lower[i] });
                        }
                    }
                    bbUpperSeries.setData(bbUpperData);
                    bbLowerSeries.setData(bbLowerData);
                    btn.classList.add('active');
                    btn.style.background = 'rgba(16, 185, 129, 0.15)';
                    btn.style.borderColor = '#10b981';
                    btn.style.color = '#10b981';
                } else {
                    if (bbUpperSeries) chart.removeSeries(bbUpperSeries);
                    if (bbLowerSeries) chart.removeSeries(bbLowerSeries);
                    bbUpperSeries = null;
                    bbLowerSeries = null;
                    btn.classList.remove('active');
                    btn.style.background = 'transparent';
                    btn.style.borderColor = 'var(--border-color)';
                    btn.style.color = 'var(--text-secondary)';
                }
            }
        };

        // Technical Studies Toggle & Draw
        let rsiChartInstance = null;
        let macdChartInstance = null;
        let technicalStudiesExpanded = false;

        window.toggleTechnicalStudies = function() {
            const bodyEl = document.getElementById('technical-studies-body');
            const chevron = document.getElementById('studies-chevron');
            if (!bodyEl) return;
            
            technicalStudiesExpanded = !technicalStudiesExpanded;
            if (technicalStudiesExpanded) {
                bodyEl.style.display = 'flex';
                chevron.style.transform = 'rotate(180deg)';
                setTimeout(drawTechnicalStudies, 50);
            } else {
                bodyEl.style.display = 'none';
                chevron.style.transform = 'rotate(0deg)';
            }
        };

        function drawTechnicalStudies() {
            const rsiCtx = document.getElementById('rsi-chart').getContext('2d');
            const macdCtx = document.getElementById('macd-chart').getContext('2d');
            
            const labels = STOCK_DATA.chart_data.labels;
            const rsiData = STOCK_DATA.chart_data.rsi || [];
            const macdData = STOCK_DATA.chart_data.macd || [];
            const macdSignal = STOCK_DATA.chart_data.macd_signal || [];
            const macdHist = STOCK_DATA.chart_data.macd_hist || [];

            // Draw RSI Chart
            if (rsiChartInstance) rsiChartInstance.destroy();
            rsiChartInstance = new Chart(rsiCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'RSI (14)',
                        data: rsiData,
                        borderColor: '#a855f7',
                        borderWidth: 1.5,
                        pointRadius: 0,
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { display: false },
                        y: {
                            min: 10,
                            max: 90,
                            ticks: { color: '#9ca3af', stepSize: 20 },
                            grid: {
                                color: function(context) {
                                    if (context.tick.value === 30 || context.tick.value === 70) {
                                        return 'rgba(239, 68, 68, 0.4)';
                                    }
                                    return 'rgba(255, 255, 255, 0.03)';
                                },
                                borderDash: function(context) {
                                    if (context.tick.value === 30 || context.tick.value === 70) {
                                        return [4, 4];
                                    }
                                    return [];
                                }
                            }
                        }
                    }
                }
            });

            // Draw MACD Chart
            if (macdChartInstance) macdChartInstance.destroy();
            macdChartInstance = new Chart(macdCtx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            type: 'bar',
                            label: 'Histogram',
                            data: macdHist,
                            backgroundColor: macdHist.map(v => v >= 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'),
                            borderColor: macdHist.map(v => v >= 0 ? '#10b981' : '#ef4444'),
                            borderWidth: 1.5,
                            borderRadius: 1
                        },
                        {
                            type: 'line',
                            label: 'MACD',
                            data: macdData,
                            borderColor: '#06b6d4',
                            borderWidth: 1.2,
                            pointRadius: 0,
                            fill: false
                        },
                        {
                            type: 'line',
                            label: 'Signal',
                            data: macdSignal,
                            borderColor: '#ff9100',
                            borderWidth: 1.2,
                            pointRadius: 0,
                            fill: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { display: false },
                        y: {
                            ticks: { color: '#9ca3af' },
                            grid: { color: 'rgba(255, 255, 255, 0.03)' }
                        }
                    }
                }
            });
        }

        let peerChartInstance = null;
        window.updatePeerChart = function() {
            const selectEl = document.getElementById('peer-chart-metric-select');
            const canvasEl = document.getElementById('peer-comparison-chart');
            if (!selectEl || !canvasEl) return;
            
            const metric = selectEl.value;
            const peers = STOCK_DATA.peers_data || [];
            
            const labels = [];
            const values = [];
            const colors = [];
            
            // Add the target stock itself
            const mainTicker = STOCK_DATA.ticker;
            labels.push(mainTicker + " (Target)");
            colors.push('#2563eb');
            
            let mainVal = null;
            if (metric === 'pe') mainVal = STOCK_DATA.metrics.trailingPE;
            else if (metric === 'fwd_pe') mainVal = STOCK_DATA.metrics.forwardPE;
            else if (metric === 'margins') mainVal = (STOCK_DATA.metrics.profitMargins || 0) * 100;
            else if (metric === 'rev_growth') mainVal = (STOCK_DATA.metrics.revenueGrowth || 0) * 100;
            
            values.push(mainVal !== null && mainVal !== undefined ? parseFloat(mainVal) : 0);
            
            // Add competitor peers
            peers.forEach(p => {
                labels.push(p.ticker);
                colors.push('#06b6d4');
                let val = null;
                if (metric === 'pe') val = p.pe;
                else if (metric === 'fwd_pe') val = p.fwd_pe;
                else if (metric === 'margins') val = (p.margins || 0) * 100;
                else if (metric === 'rev_growth') val = (p.rev_growth || 0) * 100;
                
                values.push(val !== null && val !== undefined ? parseFloat(val) : 0);
            });
            
            const ctx = canvasEl.getContext('2d');
            if (peerChartInstance) {
                peerChartInstance.destroy();
            }
            
            let displayMetricName = "";
            if (metric === 'pe') displayMetricName = "Trailing P/E Ratio";
            else if (metric === 'fwd_pe') displayMetricName = "Forward P/E Ratio";
            else if (metric === 'margins') displayMetricName = "Net Income Margin (%)";
            else if (metric === 'rev_growth') displayMetricName = "Revenue Growth Rate (%)";
            
            peerChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: displayMetricName,
                        data: values,
                        backgroundColor: colors.map(c => c + '40'),
                        borderColor: colors,
                        borderWidth: 1.5,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: '#9ca3af' } },
                        y: { 
                            grid: { color: 'rgba(255, 255, 255, 0.05)' }, 
                            ticks: { 
                                color: '#9ca3af',
                                callback: function(value) {
                                    if (metric === 'margins' || metric === 'rev_growth') {
                                        return value.toFixed(1) + '%';
                                    }
                                    return value;
                                }
                            } 
                        }
                    }
                }
            });
        }
        
        function renderQuantitativeModels() {
            // DDM Rendering
            const ddm = STOCK_DATA.advanced_models && STOCK_DATA.advanced_models.ddm;
            const ddmRoot = document.getElementById('ddm-root');
            if (ddmRoot) {
                if (ddm && ddm.is_applicable) {
                    ddmRoot.innerHTML = `
                        <div style="display:flex; flex-direction:column; gap:12px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:8px;">
                                <span style="font-size:0.9rem; color:var(--text-secondary);">Implied Fair Value</span>
                                <span style="font-size:1.8rem; font-weight:800; color:var(--cyan); font-family:'JetBrains Mono', monospace;">$${ddm.implied_price}</span>
                            </div>
                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:0.85rem;">
                                <div style="display:flex; flex-direction:column; gap:2px;">
                                    <span style="color:var(--text-muted);">Cost of Equity (r)</span>
                                    <span style="font-weight:600; color:var(--text-primary);">${ddm.cost_of_equity}%</span>
                                </div>
                                <div style="display:flex; flex-direction:column; gap:2px;">
                                    <span style="color:var(--text-muted);">Est. Dividend Growth (g)</span>
                                    <span style="font-weight:600; color:var(--text-primary);">${ddm.growth_rate}%</span>
                                </div>
                                <div style="display:flex; flex-direction:column; gap:2px;">
                                    <span style="color:var(--text-muted);">Current Annual Dividend</span>
                                    <span style="font-weight:600; color:var(--text-primary);">$${ddm.dividend_rate}</span>
                                </div>
                                <div style="display:flex; flex-direction:column; gap:2px;">
                                    <span style="color:var(--text-muted);">Payout Ratio</span>
                                    <span style="font-weight:600; color:var(--text-primary);">${ddm.payout_ratio}%</span>
                                </div>
                            </div>
                            <div style="font-size:0.75rem; color:var(--text-muted); background:var(--bg-panel); border:1px solid var(--border-color); border-radius:6px; padding:8px;">
                                Based on CAPM cost of equity and long-term sustainable dividend growth.
                            </div>
                        </div>
                    `;
                } else {
                    const costEquity = ddm ? ddm.cost_of_equity : 'N/A';
                    ddmRoot.innerHTML = `
                        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; min-height:150px; text-align:center; gap:8px;">
                            <svg style="width:36px; height:36px; color:var(--text-muted); margin-bottom: 5px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                            <div style="font-size:0.9rem; font-weight:600; color:var(--text-secondary);">Model Not Applicable</div>
                            <div style="font-size:0.8rem; color:var(--text-muted); max-width:250px;">This company does not pay dividends. DDM requires dividend payments. (Cost of equity is calculated at ${costEquity}%).</div>
                        </div>
                    `;
                }
            }

            // CCA Rendering
            const cca = STOCK_DATA.advanced_models && STOCK_DATA.advanced_models.cca;
            const ccaRoot = document.getElementById('cca-root');
            if (ccaRoot) {
                if (cca) {
                    const peers = STOCK_DATA.peers_data || [];
                    let tableRows = '';
                    peers.forEach(p => {
                        const formattedPe = (typeof p.pe === 'number') ? p.pe.toFixed(2) : (parseFloat(p.pe) ? parseFloat(p.pe).toFixed(2) : p.pe || 'N/A');
                        const formattedFwdPe = (typeof p.fwd_pe === 'number') ? p.fwd_pe.toFixed(2) : (parseFloat(p.fwd_pe) ? parseFloat(p.fwd_pe).toFixed(2) : p.fwd_pe || 'N/A');
                        const formattedPs = (typeof p.ps === 'number') ? p.ps.toFixed(2) : (parseFloat(p.ps) ? parseFloat(p.ps).toFixed(2) : p.ps || 'N/A');
                        const formattedPb = (typeof p.pb === 'number') ? p.pb.toFixed(2) : (parseFloat(p.pb) ? parseFloat(p.pb).toFixed(2) : p.pb || 'N/A');
                        tableRows += `
                            <tr>
                                <td style="color:var(--text-primary); font-weight:600; padding:6px 0;">${p.ticker}</td>
                                <td style="text-align:right; padding:6px 0;">${formattedPe}</td>
                                <td style="text-align:right; padding:6px 0;">${formattedFwdPe}</td>
                                <td style="text-align:right; padding:6px 0;">${formattedPs}</td>
                                <td style="text-align:right; padding:6px 0;">${formattedPb}</td>
                            </tr>
                        `;
                    });
                    
                    ccaRoot.innerHTML = `
                        <div style="display:flex; flex-direction:column; gap:12px;">
                            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;" class="statement-table">
                                <thead>
                                    <tr style="border-bottom:1px solid var(--border-color); color:var(--text-muted); font-weight:600;">
                                        <th style="text-align:left; padding-bottom:6px;">Competitor</th>
                                        <th style="text-align:right; padding-bottom:6px;">P/E (TTM)</th>
                                        <th style="text-align:right; padding-bottom:6px;">P/E (Fwd)</th>
                                        <th style="text-align:right; padding-bottom:6px;">P/S (TTM)</th>
                                        <th style="text-align:right; padding-bottom:6px;">P/B</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${tableRows}
                                    <tr style="border-top:1px solid var(--border-color); color:var(--text-secondary); font-weight:600; background:var(--bg-panel);">
                                        <td style="padding: 6px 0;">Peer Median</td>
                                        <td style="text-align:right; padding: 6px 0;">${typeof cca.peer_median_pe === 'number' ? cca.peer_median_pe.toFixed(2) : cca.peer_median_pe || 'N/A'}</td>
                                        <td style="text-align:right; padding: 6px 0;">${typeof cca.peer_median_fwd_pe === 'number' ? cca.peer_median_fwd_pe.toFixed(2) : cca.peer_median_fwd_pe || 'N/A'}</td>
                                        <td style="text-align:right; padding: 6px 0;">${typeof cca.peer_median_ps === 'number' ? cca.peer_median_ps.toFixed(2) : cca.peer_median_ps || 'N/A'}</td>
                                        <td style="text-align:right; padding: 6px 0;">${typeof cca.peer_median_pb === 'number' ? cca.peer_median_pb.toFixed(2) : cca.peer_median_pb || 'N/A'}</td>
                                    </tr>
                                    <tr style="color:var(--cyan); font-weight:700;">
                                        <td style="padding: 6px 0;">Target Ticker</td>
                                        <td style="text-align:right; padding: 6px 0;">${cca.target_pe ? Number(cca.target_pe).toFixed(2) : 'N/A'}</td>
                                        <td style="text-align:right; padding: 6px 0;">${cca.target_fwd_pe ? Number(cca.target_fwd_pe).toFixed(2) : 'N/A'}</td>
                                        <td style="text-align:right; padding: 6px 0;">${cca.target_ps ? Number(cca.target_ps).toFixed(2) : 'N/A'}</td>
                                        <td style="text-align:right; padding: 6px 0;">${cca.target_pb ? Number(cca.target_pb).toFixed(2) : 'N/A'}</td>
                                    </tr>
                                </tbody>
                            </table>
                            
                            <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:8px; border-top:1px solid var(--border-color); padding-top:8px; font-size:0.8rem;">
                                <div style="display:flex; flex-direction:column; align-items:center; background:var(--bg-panel); padding:6px; border-radius:6px; border:1px solid var(--border-color);">
                                    <span style="color:var(--text-muted); font-size:0.7rem;">PE (TTM) Implied</span>
                                    <span style="font-weight:700; color:var(--green); font-family:'JetBrains Mono', monospace;">${cca.implied_pe_price ? '$' + cca.implied_pe_price : 'N/A'}</span>
                                </div>
                                <div style="display:flex; flex-direction:column; align-items:center; background:var(--bg-panel); padding:6px; border-radius:6px; border:1px solid var(--accent-glow);">
                                    <span style="color:var(--text-muted); font-size:0.7rem;">PE (Fwd) Implied</span>
                                    <span style="font-weight:700; color:var(--accent); font-family:'JetBrains Mono', monospace;">${cca.implied_fwd_pe_price ? '$' + cca.implied_fwd_pe_price : 'N/A'}</span>
                                </div>
                                <div style="display:flex; flex-direction:column; align-items:center; background:var(--bg-panel); padding:6px; border-radius:6px; border:1px solid var(--border-color);">
                                    <span style="color:var(--text-muted); font-size:0.7rem;">PS Implied</span>
                                    <span style="font-weight:700; color:var(--green); font-family:'JetBrains Mono', monospace;">${cca.implied_ps_price ? '$' + cca.implied_ps_price : 'N/A'}</span>
                                </div>
                                <div style="display:flex; flex-direction:column; align-items:center; background:var(--bg-panel); padding:6px; border-radius:6px; border:1px solid var(--border-color);">
                                    <span style="color:var(--text-muted); font-size:0.7rem;">PB Implied</span>
                                    <span style="font-weight:700; color:var(--green); font-family:'JetBrains Mono', monospace;">${cca.implied_pb_price ? '$' + cca.implied_pb_price : 'N/A'}</span>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    ccaRoot.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; padding:20px;">Peer multiples not available.</div>';
                }
            }

            // Monte Carlo Rendering
            const mc = STOCK_DATA.advanced_models && STOCK_DATA.advanced_models.monte_carlo;
            const mcRoot = document.getElementById('monte-carlo-root');
            if (mcRoot) {
                if (mc && mc.bins && mc.counts) {
                    const maxCount = Math.max(...mc.counts);
                    let barsSvg = '';
                    const width = 400;
                    const height = 90;
                    const barWidth = (width / mc.counts.length) - 4;
                    
                    mc.counts.forEach((cnt, idx) => {
                        const barHeight = (cnt / maxCount) * (height - 15);
                        const x = idx * (width / mc.counts.length) + 2;
                        const y = height - barHeight;
                        
                        barsSvg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" fill="var(--yellow)" opacity="0.75" rx="1.5" />`;
                        if (idx % 3 === 0 || idx === mc.counts.length - 1) {
                            barsSvg += `<text x="${x + barWidth/2}" y="${height + 15}" fill="var(--text-muted)" font-size="8" text-anchor="middle">$${mc.bins[idx]}</text>`;
                        }
                    });
                    
                    const currentPrice = STOCK_DATA.metrics.current_price;
                    let currentMarker = '';
                    const minBin = mc.bins[0];
                    const maxBin = mc.bins[mc.bins.length - 1];
                    if (currentPrice >= minBin && currentPrice <= maxBin) {
                        const pct = (currentPrice - minBin) / (maxBin - minBin);
                        const markerX = pct * width;
                        currentMarker = `
                            <line x1="${markerX}" y1="0" x2="${markerX}" y2="${height}" stroke="var(--red)" stroke-width="2" stroke-dasharray="3,3" />
                            <text x="${markerX}" y="-5" fill="var(--red)" font-size="8" font-weight="700" text-anchor="middle">Current ($${currentPrice})</text>
                        `;
                    }
                    
                    let warningNoteHtml = '';
                    if (mc.p50 < currentPrice * 0.3) {
                        warningNoteHtml = `
                            <div style="margin-top: 12px; padding: 6px 10px; border-radius: 6px; background-color: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); font-size: 0.7rem; color: var(--text-secondary); display: flex; align-items: center; gap: 6px;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                                <span><strong>Warning:</strong> Monte Carlo uses trailing FCF which understate value during high-capex growth cycles.</span>
                            </div>
                        `;
                    } else if (mc.valuation_basis && mc.valuation_basis.includes("sanity-adjusted")) {
                        warningNoteHtml = `
                            <div style="margin-top: 12px; padding: 6px 10px; border-radius: 6px; background-color: rgba(6, 182, 212, 0.08); border: 1px solid rgba(6, 182, 212, 0.2); font-size: 0.7rem; color: var(--text-secondary); display: flex; align-items: center; gap: 6px;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                                <span><strong>Note:</strong> Scaled with Forward EPS sanity anchor (trailing FCF depressed by elevated Capex).</span>
                            </div>
                        `;
                    }

                    mcRoot.innerHTML = `
                        <div style="display:grid; grid-template-columns: 1fr 1.8fr; gap:15px; align-items:center;">
                            <div style="display:flex; flex-direction:column; gap:10px;">
                                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:6px;">
                                    <span style="font-size:0.85rem; color:var(--text-muted);">10% (Bear Case)</span>
                                    <span style="font-weight:700; color:var(--text-primary); font-family:'JetBrains Mono', monospace;">$${mc.p10}</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:6px;">
                                    <span style="font-size:0.85rem; color:var(--text-muted); font-weight: 600;">50% (Fair Value)</span>
                                    <span style="font-weight:800; color:var(--yellow); font-family:'JetBrains Mono', monospace;">$${mc.p50}</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:6px;">
                                    <span style="font-size:0.85rem; color:var(--text-muted);">90% (Bull Case)</span>
                                    <span style="font-weight:700; color:var(--text-primary); font-family:'JetBrains Mono', monospace;">$${mc.p90}</span>
                                </div>
                            </div>
                            <div style="display:flex; flex-direction:column; align-items:center;">
                                <div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:10px;">Probability Distribution (1,000 Trials)</div>
                                <svg viewBox="-10 -15 ${width + 20} ${height + 35}" style="width:100%; height:110px; overflow:visible;">
                                    ${barsSvg}
                                    ${currentMarker}
                                </svg>
                            </div>
                        </div>
                        ${warningNoteHtml}
                    `;
                } else {
                    mcRoot.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; padding:20px;">DCF parameters insufficient to run Monte Carlo.</div>';
                }
            }

            // Regression Rendering
            const reg = STOCK_DATA.advanced_models && STOCK_DATA.advanced_models.historical_regression;
            const regRoot = document.getElementById('regression-root');
            if (regRoot) {
                if (reg) {
                    const badgeColor = reg.status.includes('OVERBOUGHT') ? 'var(--red)' : reg.status.includes('UNDERVALUED') ? 'var(--green)' : 'var(--amber)';
                    const badgeBg = reg.status.includes('OVERBOUGHT') ? 'var(--red-glow)' : reg.status.includes('UNDERVALUED') ? 'var(--green-glow)' : 'var(--amber-glow)';
                    
                    regRoot.innerHTML = `
                        <div style="display:flex; flex-direction:column; gap:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:5px;">
                                <span style="font-size:0.8rem; color:var(--text-muted);">Historical CAGR (5Y)</span>
                                <span style="font-weight:600; color:var(--text-primary); font-family:'JetBrains Mono', monospace;">${reg.cagr}%</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:5px;">
                                <span style="font-size:0.8rem; color:var(--text-muted);">R-Squared (Fit Strength)</span>
                                <span style="font-weight:600; color:var(--text-primary); font-family:'JetBrains Mono', monospace;">${reg.r_squared}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:5px;">
                                <span style="font-size:0.8rem; color:var(--text-muted);">Channel Midpoint (Fair)</span>
                                <span style="font-weight:700; color:var(--cyan); font-family:'JetBrains Mono', monospace;">$${reg.fair_price}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-color); padding-bottom:5px;">
                                <span style="font-size:0.8rem; color:var(--text-muted);">Deviation from Trend</span>
                                <span style="font-weight:700; color:${badgeColor}; font-family:'JetBrains Mono', monospace;">${reg.deviation_pct > 0 ? '+' : ''}${reg.deviation_pct}%</span>
                            </div>
                            
                            <div style="display:flex; flex-direction:column; gap:4px; margin-top:8px;">
                                <div style="text-align:center; font-size:0.75rem; font-weight:700; padding:6px; border-radius:6px; border:1px solid ${badgeColor}30; color:${badgeColor}; background-color:${badgeBg};">
                                    ${reg.status}
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    regRoot.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; padding:20px;">Price history insufficient to calculate regression trend.</div>';
                }
            }
        }

        // Trigger initialization
        setTimeout(() => {
            updatePeerChart();
            renderQuantitativeModels();
        }, 100);

        // Render catalysts in Overview tab
        const catRoot = document.getElementById('catalysts-root');
        if (catRoot) {
            const catalysts = (STOCK_DATA.analysis && STOCK_DATA.analysis.catalysts) || [];
            if (!catalysts.length) {
                catRoot.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; padding: 20px; text-align: center;">No upcoming catalysts identified.</div>';
            } else {
                catalysts.forEach(c => {
                    const impact = (c.impact || 'POSITIVE').toUpperCase();
                    const impactColor = impact === 'POSITIVE' ? 'var(--green)' : impact === 'NEGATIVE' ? 'var(--red)' : 'var(--amber)';
                    const impactBg = impact === 'POSITIVE' ? 'var(--green-glow)' : impact === 'NEGATIVE' ? 'var(--red-glow)' : 'var(--amber-glow)';
                    catRoot.innerHTML += `
                        <div style="background-color:var(--bg-card); border:1px solid var(--border-color); border-radius:10px; padding:12px; display:flex; flex-direction:column; gap:6px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:0.75rem; color:var(--text-muted); font-family:'JetBrains Mono', monospace; font-weight: 500;">${c.timeline}</span>
                                <span style="font-size:0.65rem; font-weight:700; color:${impactColor}; background-color:${impactBg}; padding:2px 6px; border-radius:4px; border:1px solid ${impactColor}30;">${impact}</span>
                            </div>
                            <div style="font-size:0.85rem; color:var(--text-primary); line-height:1.4;">${c.catalyst}</div>
                        </div>
                    `;
                });
            }
        }

        // Style the Economic Moat Badge dynamically
        const moatBadge = document.getElementById('moat-badge');
        if (moatBadge) {
            const moatVal = moatBadge.innerText.trim().toUpperCase();
            if (['WIDE', 'VERY WIDE'].includes(moatVal)) {
                moatBadge.style.color = 'var(--green)';
                moatBadge.style.backgroundColor = 'var(--green-glow)';
                moatBadge.style.border = '1px solid rgba(16, 185, 129, 0.2)';
            } else if (moatVal === 'NARROW') {
                moatBadge.style.color = 'var(--cyan)';
                moatBadge.style.backgroundColor = 'rgba(6, 182, 212, 0.1)';
                moatBadge.style.border = '1px solid rgba(6, 182, 212, 0.2)';
            } else {
                moatBadge.style.color = 'var(--text-muted)';
                moatBadge.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                moatBadge.style.border = '1px solid var(--border-color)';
            }
        }

        let tvWidgetInitialized = false;
        window.setChartType = function(type) {
            const btnLight = document.getElementById('btn-chart-light');
            const btnTv = document.getElementById('btn-chart-tv');
            const wrapperLight = document.getElementById('tv-chart');
            const wrapperTv = document.getElementById('tv-advanced-wrapper');
            
            if (type === 'light') {
                btnLight.classList.add('active');
                btnLight.style.background = 'var(--bg-card)';
                btnLight.style.borderColor = 'var(--border-color)';
                btnLight.style.color = 'var(--text-primary)';
                
                btnTv.classList.remove('active');
                btnTv.style.background = 'transparent';
                btnTv.style.borderColor = 'transparent';
                btnTv.style.color = 'var(--text-muted)';
                
                wrapperLight.style.display = 'block';
                wrapperTv.style.display = 'none';
            } else {
                btnLight.classList.remove('active');
                btnLight.style.background = 'transparent';
                btnLight.style.borderColor = 'transparent';
                btnLight.style.color = 'var(--text-muted)';
                
                btnTv.classList.add('active');
                btnTv.style.background = 'var(--bg-card)';
                btnTv.style.borderColor = 'var(--border-color)';
                btnTv.style.color = 'var(--text-primary)';
                
                wrapperLight.style.display = 'none';
                wrapperTv.style.display = 'block';
                
                const iframe = document.getElementById('tradingview_advanced_iframe');
                if (iframe && !iframe.src.includes('tradingview.com')) {
                    const cleanTicker = "{{TICKER}}".replace("-USD", "USD").replace("=X", "");
                    iframe.src = "https://s.tradingview.com/widgetembed/?symbol=" + encodeURIComponent(cleanTicker) + "&theme=dark&style=1&timezone=exchange";
                }
            }
        }

        // Notion Research Hub initialization
        function initNotionHub() {
            if (!STOCK_DATA.notion_data || !STOCK_DATA.notion_data.subpages) {
                console.log("No Notion data available for this ticker. Skipping Notion Research Hub initialization.");
                return;
            }
            
            const notionData = STOCK_DATA.notion_data;
            const subpages = notionData.subpages;
            
            // 1. Show the sidebar tab
            const notionMenuItem = document.getElementById('menu-item-notion');
            if (notionMenuItem) {
                notionMenuItem.style.display = 'flex';
            }
            
            // 2. Set the title of the hub
            const notionTitle = document.getElementById('notion-hub-title');
            if (notionTitle) {
                notionTitle.textContent = `${notionData.company_title || 'Notion Company Hub'}`;
            }
            
            // 3. Dynamically populate sections and navigation buttons
            const navRoot = document.getElementById('notion-sub-nav-root');
            const contentArea = document.getElementById('notion-content-area');
            
            if (!navRoot || !contentArea) return;
            
            navRoot.innerHTML = '';
            contentArea.innerHTML = '';
            
            // Get all subpage keys
            const keys = Object.keys(subpages);
            if (keys.length === 0) {
                contentArea.innerHTML = '<div style="color: var(--text-muted); font-size: 0.9rem; text-align: center; padding: 40px 0;">No synchronized subpages found in this company hub.</div>';
                return;
            }
            
            // Order overview first if present
            const sortedKeys = [];
            if (keys.includes('overview')) sortedKeys.push('overview');
            keys.forEach(k => {
                if (k !== 'overview') sortedKeys.push(k);
            });
            
            let firstActiveId = null;
            
            sortedKeys.forEach(key => {
                const subpage = subpages[key];
                let title = '';
                let html = '';
                
                if (typeof subpage === 'string') {
                    title = key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
                    html = subpage;
                } else if (subpage && typeof subpage === 'object') {
                    title = subpage.title || key;
                    html = subpage.html || '';
                }
                
                if (!html || !html.trim()) return;
                
                const secId = `notion-sec-${key}`;
                
                // Create content container
                const contentDiv = document.createElement('div');
                contentDiv.id = secId;
                contentDiv.className = 'notion-sec';
                contentDiv.style.display = 'none';
                contentDiv.style.animation = 'fadeIn 0.3s ease';
                contentDiv.innerHTML = html;
                contentArea.appendChild(contentDiv);
                
                // Select dynamic icon SVG based on title
                let svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`;
                const lowerTitle = title.toLowerCase();
                if (lowerTitle.includes('overview') || lowerTitle.includes('summary')) {
                    svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`;
                } else if (lowerTitle.includes('briefing') || lowerTitle.includes('notes')) {
                    svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`;
                } else if (lowerTitle.includes('price') || lowerTitle.includes('valuation') || lowerTitle.includes('stock')) {
                    svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>`;
                } else if (lowerTitle.includes('risk') || lowerTitle.includes('red flag')) {
                    svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
                } else if (lowerTitle.includes('earnings') || lowerTitle.includes('financial') || lowerTitle.includes('statements')) {
                    svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>`;
                } else if (lowerTitle.includes('competitor') || lowerTitle.includes('peers')) {
                    svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>`;
                } else if (lowerTitle.includes('thesis') || lowerTitle.includes('model')) {
                    svgIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`;
                }
                
                // Create tab button
                const btn = document.createElement('button');
                btn.className = 'notion-sub-btn';
                btn.innerHTML = `<span style="margin-right: 8px; display: inline-flex; align-items: center; justify-content: center; vertical-align: middle;">${svgIcon}</span> <span>${title}</span>`;
                btn.onclick = (e) => switchNotionSection(key, btn);
                navRoot.appendChild(btn);
                
                if (!firstActiveId) {
                    firstActiveId = key;
                    btn.classList.add('active');
                    contentDiv.style.display = 'block';
                }
            });
        }
        
        window.switchNotionSection = function(secId, btn) {
            // Hide all notion sections
            document.querySelectorAll('.notion-sec').forEach(el => el.style.display = 'none');
            
            // Show target section
            const targetSec = document.getElementById(`notion-sec-${secId}`);
            if (targetSec) {
                targetSec.style.display = 'block';
            }
            
            // Update active button styling
            const buttons = btn.parentElement.querySelectorAll('.notion-sub-btn');
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }

        // Force a resize event after initial page load to settle the chart layout dimensions
        window.addEventListener('load', () => {
            initNotionHub();
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 300);
        });
    </script>
</body>
</html>
"""
    
    freshness = source_meta.get("freshness", {})
    availability = source_meta.get("availability", {})
    providers = source_meta.get("providers", {})
    limitations = source_meta.get("limitations", [])
    latest_price_date = freshness.get("price_history_1y_last_date", "N/A")
    stmt_dates = freshness.get("quarterly_income_statement_dates", [])
    stmt_date_text = ", ".join(stmt_dates[:4]) if stmt_dates else "N/A"
    limitation_items = "".join(f"<li>{item}</li>" for item in limitations)
    source_audit_html = f'''
    <div class="panel-grid-2">
        <div class="ai-section-box">
            <h3>Providers</h3>
            <p><strong>Market data:</strong> {providers.get("market_data", "Yahoo Finance via yfinance")}</p>
            <p><strong>SEC filings:</strong> {providers.get("sec_filings", "SEC EDGAR submissions and companyfacts APIs")}</p>
            <p><strong>News sentiment:</strong> {providers.get("news_sentiment", "Alpha Vantage NEWS_SENTIMENT API")}</p>
            <p><strong>AI analysis:</strong> {providers.get("ai_analysis", "Groq OpenAI-compatible chat completions")}</p>
            <p><strong>Local models:</strong> {providers.get("local_models", "Local Python valuation and technical models")}</p>
        </div>
        <div class="ai-section-box">
            <h3>Freshness</h3>
            <p><strong>Generated UTC:</strong> {source_meta.get("generated_at_utc", "N/A")}</p>
            <p><strong>Latest price date:</strong> {latest_price_date}</p>
            <p><strong>Latest quarterly statements:</strong> {stmt_date_text}</p>
            <p><strong>1Y price rows:</strong> {availability.get("history_1y_rows", "N/A")}</p>
        </div>
    </div>
    <div class="ai-section-box">
        <h3>Coverage & Limitations</h3>
        <p>News items: {availability.get("news_items", 0)} | Peers loaded: {availability.get("peer_count", 0)} | SEC EDGAR: {availability.get("sec_edgar", False)} | Earnings dates: {availability.get("earnings_dates", False)} | Recommendations: {availability.get("recommendations", False)}</p>
        <p style="margin-top:8px;">Raw snapshots: output/{{TICKER}}/raw/</p>
        <ul style="margin-top:10px; padding-left:18px; color:var(--text-secondary); line-height:1.7;">{limitation_items}</ul>
    </div>
    '''

    # Generate Premium Widgets HTML
    dcf_data = sd.get("dcf_data")
    if dcf_data:
        dcf_html = f'''
        <div class="panel-grid-2" style="margin-top: 10px;">
            <div class="ai-section-box dcf-interactive-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase;">Interactive DCF Value</div>
                        <div style="font-size:2rem; font-weight:700; color:var(--accent); margin:10px 0 5px 0; font-family:\'JetBrains Mono\', monospace;" id="dcf-live-value">${dcf_data["implied_price"]:.2f}</div>
                        <div id="dcf-adjustment-badge" style="display:{'inline-block' if dcf_data.get('valuation_basis', '').startswith('Forward EPS') else 'none'}; font-size:0.65rem; font-weight:700; padding:2px 6px; border-radius:4px; margin-bottom:10px; background-color:rgba(6, 182, 212, 0.15); color:var(--cyan);">EPS-ADJUSTED</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase;">Reverse DCF Implied Growth</div>
                        <div style="font-size:2rem; font-weight:700; color:var(--cyan); margin:10px 0; font-family:\'JetBrains Mono\', monospace;" id="reverse-dcf-implied-growth">Solving...</div>
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-between; gap: 8px; margin: 15px 0 10px 0;">
                    <button class="btn-scenario" data-scenario="bear" style="flex: 1; padding: 6px 12px; border-radius: 4px; background: rgba(239, 68, 68, 0.1); color: var(--red); border: 1px solid rgba(239, 68, 68, 0.2); font-weight: 600; cursor: pointer; font-size: 0.75rem; transition: all 0.2s;">Bear Case</button>
                    <button class="btn-scenario" data-scenario="base" style="flex: 1; padding: 6px 12px; border-radius: 4px; background: rgba(59, 130, 246, 0.1); color: var(--cyan); border: 1px solid rgba(59, 130, 246, 0.2); font-weight: 600; cursor: pointer; font-size: 0.75rem; transition: all 0.2s;">Base Case</button>
                    <button class="btn-scenario" data-scenario="bull" style="flex: 1; padding: 6px 12px; border-radius: 4px; background: rgba(16, 185, 129, 0.1); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.2); font-weight: 600; cursor: pointer; font-size: 0.75rem; transition: all 0.2s;">Bull Case</button>
                </div>
                
                <div style="margin-top:20px; display:flex; flex-direction:column; gap:16px;">
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:var(--text-secondary); margin-bottom:4px;">
                            <span>Cost of Capital (WACC)</span>
                            <span id="wacc-val" style="font-family:\'JetBrains Mono\', monospace;">{dcf_data["wacc_used"]}%</span>
                        </div>
                        <input type="range" id="wacc-slider" min="4" max="15" step="0.1" value="{dcf_data["wacc_used"]}" style="width:100%; accent-color:var(--accent);">
                    </div>
                    
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:var(--text-secondary); margin-bottom:4px;">
                            <span>Terminal Growth Rate</span>
                            <span id="tg-val" style="font-family:\'JetBrains Mono\', monospace;">{dcf_data["terminal_growth"]}%</span>
                        </div>
                        <input type="range" id="tg-slider" min="0" max="6" step="0.1" value="{dcf_data["terminal_growth"]}" style="width:100%; accent-color:var(--cyan);">
                    </div>
                </div>
            </div>
            
            <div style="display:flex; flex-direction:column; gap:20px;">
                <div class="ai-section-box">
                    <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase;">Base Free Cash Flow</div>
                    <div style="font-size:1.5rem; font-weight:700; color:var(--text-primary); margin:10px 0; font-family:\'JetBrains Mono\', monospace;" id="dcf-base-fcf" data-fcf="{dcf_data["fcf_base"]}">${dcf_data["fcf_base"]:,.0f}</div>
                    <div style="font-size:0.85rem; color:var(--text-secondary);">Projected 10-year discounted FCF model</div>
                    <div style="font-size:0.75rem; color:var(--text-muted); margin-top:6px;" id="dcf-basis-info">Basis: {dcf_data.get("valuation_basis", "FCF DCF")}</div>
                    <div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;" id="dcf-raw-info">Raw DCF before sanity check: ${dcf_data.get("raw_dcf_price", dcf_data["implied_price"]):,.2f}{' <span style="color:var(--red); font-weight:600; font-size:0.7rem;">(Trailing FCF depressed by Capex)</span>' if dcf_data.get('valuation_basis', '').startswith('Forward EPS') else ''}</div>
                </div>
                <div class="ai-section-box">
                    <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase;">SEC EDGAR Filings</div>
                    <ul style="list-style:none; padding:0; margin-top:10px; display:flex; flex-direction:column; gap:8px;">
                        <li><a href="https://www.sec.gov/edgar/search/#/q={t}&category=custom&forms=10-K" target="_blank" style="color:var(--accent); text-decoration:none; font-size:0.9rem; font-weight:500;">View Latest 10-K (Annual) &rarr;</a></li>
                        <li><a href="https://www.sec.gov/edgar/search/#/q={t}&category=custom&forms=10-Q" target="_blank" style="color:var(--accent); text-decoration:none; font-size:0.9rem; font-weight:500;">View Latest 10-Q (Quarterly) &rarr;</a></li>
                        <li><a href="https://www.sec.gov/edgar/search/#/q={t}&category=custom&forms=8-K" target="_blank" style="color:var(--accent); text-decoration:none; font-size:0.9rem; font-weight:500;">View 8-K (Current Reports) &rarr;</a></li>
                        <li><a href="https://www.sec.gov/edgar/search/#/q={t}&category=custom&forms=4" target="_blank" style="color:var(--accent); text-decoration:none; font-size:0.9rem; font-weight:500;">View Form 4 (Insider Trades) &rarr;</a></li>
                    </ul>
                </div>
            </div>
        </div>
        '''
    else:
        dcf_html = "<p style='color:var(--text-muted)'>DCF Valuation unavailable (missing cash flow or beta).</p>"

    peers_data = sd.get("peers_data", [])
    if peers_data:
        peers_rows = ""
        for p in peers_data:
            mg = f"{p['margins']*100:.1f}%" if isinstance(p['margins'], (int, float)) else "N/A"
            rg = f"{p['rev_growth']*100:.1f}%" if isinstance(p['rev_growth'], (int, float)) else "N/A"
            pe_val = f"{p['pe']:.2f}" if isinstance(p['pe'], (int, float)) else str(p['pe'])
            fwd_pe_val = f"{p['fwd_pe']:.2f}" if isinstance(p['fwd_pe'], (int, float)) else str(p['fwd_pe'])
            peers_rows += f"<tr><td>{p['ticker']}</td><td>{p['name']}</td><td class='val-cell'>{pe_val}</td><td class='val-cell'>{fwd_pe_val}</td><td class='val-cell'>{mg}</td><td class='val-cell'>{rg}</td></tr>"
        peers_html = f'''
        <div style="margin-bottom: 20px; display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Peer Comparison Chart</div>
                <select id="peer-chart-metric-select" onchange="updatePeerChart()" style="background-color: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-primary); padding: 4px 10px; border-radius: 4px; font-size: 0.8rem; outline: none; cursor: pointer;">
                    <option value="pe">Trailing P/E</option>
                    <option value="fwd_pe">Forward P/E</option>
                    <option value="margins">Net Margin (%)</option>
                    <option value="rev_growth">Revenue Growth (%)</option>
                </select>
            </div>
            <div style="background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 15px; height: 240px; width: 100%;">
                <canvas id="peer-comparison-chart"></canvas>
            </div>
        </div>
        <div class="table-container">
            <table class="statement-table">
                <tr class="header-row"><th>Ticker</th><th>Name</th><th style="text-align:right">Trailing P/E</th><th style="text-align:right">Forward P/E</th><th style="text-align:right">Net Margin</th><th style="text-align:right">Rev Growth</th></tr>
                {peers_rows}
            </table>
        </div>
        '''
    else:
        peers_html = "<p style='color:var(--text-muted)'>Peer data unavailable.</p>"

    insiders_data = sd.get("insider_trades", [])
    if insiders_data:
        ins_rows = ""
        for ins in insiders_data:
            val_str = f"${ins['Value']:,.0f}" if ins.get('Value') else "N/A"
            tx = ins.get('Transaction') or ""
            if not tx:
                text_desc = ins.get('Text') or ""
                if text_desc.strip().lower().startswith("sale"):
                    tx = "Sale"
                elif text_desc.strip().lower().startswith("purchase") or "buy" in text_desc.strip().lower():
                    tx = "Purchase"
                elif "award" in text_desc.strip().lower() or "grant" in text_desc.strip().lower():
                    tx = "Award / Grant"
                elif "option" in text_desc.strip().lower():
                    tx = "Option Exercise"
                else:
                    tx = text_desc.split(" at ")[0] if " at " in text_desc else text_desc[:15]
            ins_rows += f"<tr><td>{ins.get('Start Date','')}</td><td>{str(ins.get('Insider','N/A'))[:25]}</td><td>{tx}</td><td class='val-cell'>{ins.get('Shares')}</td><td class='val-cell'>{val_str}</td></tr>"
        insiders_html = f'''
        <div class="table-container">
            <table class="statement-table">
                <tr class="header-row"><th>Date</th><th>Insider</th><th>Transaction</th><th style="text-align:right">Shares</th><th style="text-align:right">Value</th></tr>
                {ins_rows}
            </table>
        </div>
        '''
    else:
        insiders_html = "<p style='color:var(--text-muted)'>No recent insider transactions found.</p>"

    # Process replacements (robust and fast)
    html = HTML_TEMPLATE
    replacements = {
        "{{TICKER}}": t,
        "{{COMPANY_NAME}}": name,
        "{{SECTOR}}": m.get("sector","N/A"),
        "{{INDUSTRY}}": m.get("industry","N/A"),
        "{{CURRENT_PRICE}}": f"{m.get('current_price', 0):.2f}",
        "{{PRICE_CHANGE_1D}}": f"{m.get('price_change_1d', 0):+.2f}",
        "{{PRICE_CHANGE_COLOR}}": "var(--green)" if m.get("price_change_1d", 0) >= 0 else "var(--red)",
        "{{MEAN_TARGET}}": str(m.get("targetMeanPrice", "N/A")),
        "{{ANALYST_COUNT}}": str(m.get("numberOfAnalystOpinions", "?")),
        "{{VERDICT}}": v,
        "{{VERDICT_CONFIDENCE}}": str(conf),
        "{{VERDICT_COLOR}}": vc,
        "{{VERDICT_BG}}": vbg,
        "{{MOAT}}": moat,
        "{{MGMT}}": str(mgmt),
        "{{SENT_LABEL}}": sent_label,
        "{{VAL_GRADE}}": val_grade,
        "{{EXECUTIVE_SUMMARY}}": analysis.get("executive_summary", "N/A"),
        "{{REVENUE_QUALITY}}": analysis.get("fundamental_analysis", {}).get("revenue_quality", "N/A"),
        "{{PROFITABILITY}}": analysis.get("fundamental_analysis", {}).get("profitability", "N/A"),
        "{{COMPETITIVE_MOAT}}": analysis.get("fundamental_analysis", {}).get("competitive_moat", "N/A"),
        "{{EARNINGS_POWER}}": analysis.get("fundamental_analysis", {}).get("earnings_power", "N/A"),
        "{{BALANCE_SHEET_HEALTH}}": analysis.get("fundamental_analysis", {}).get("balance_sheet", "N/A"),
        "{{CAPITAL_ALLOCATION}}": analysis.get("fundamental_analysis", {}).get("capital_allocation", "N/A"),
        "{{UNIT_ECONOMICS}}": analysis.get("fundamental_analysis", {}).get("unit_economics", "N/A"),
        "{{MACRO_ENVIRONMENT}}": analysis.get("macro_analysis", {}).get("macro_environment", "N/A"),
        "{{SECTOR_OUTLOOK}}": analysis.get("macro_analysis", {}).get("sector_outlook", "N/A"),
        "{{REGULATORY_ANTITRUST}}": analysis.get("macro_analysis", {}).get("regulatory_antitrust", "N/A"),
        "{{GEOPOLITICAL_RISK}}": analysis.get("macro_analysis", {}).get("geopolitical_risk", "N/A"),
        "{{GUIDANCE_EXPECTATIONS}}": analysis.get("guidance_and_expectations", "N/A"),
        "{{ANALYST_SENTIMENT}}": analysis.get("sentiment_analysis", {}).get("analyst_sentiment", "N/A"),
        "{{INSTITUTIONAL_POSITIONING}}": analysis.get("sentiment_analysis", {}).get("institutional_positioning", "N/A"),
        "{{NEWS_SENTIMENT}}": analysis.get("sentiment_analysis", {}).get("news_sentiment", "N/A"),
        "{{INTRINSIC_VALUE_ESTIMATE}}": analysis.get("valuation_assessment", {}).get("intrinsic_value_estimate", "N/A"),
        "{{MARGIN_OF_SAFETY}}": analysis.get("valuation_assessment", {}).get("margin_of_safety", "N/A"),
        "{{BEAR_CASE_TARGET}}": str(analysis.get("bear_case_target", 0)),
        "{{FAIR_VALUE_MID}}": str(analysis.get("valuation_assessment", {}).get("fair_value_mid", 0)),
        "{{BULL_CASE_TARGET}}": str(analysis.get("bull_case_target", 0)),
        "{{WORST_CASE_SCENARIO}}": analysis.get("risk_assessment", {}).get("worst_case_scenario", "N/A"),
        "{{RISK_REWARD_RATIO}}": analysis.get("risk_assessment", {}).get("risk_reward_ratio", "N/A"),
        "{{POSITION_SIZING}}": analysis.get("position_sizing", "N/A"),
        "{{INVESTMENT_THESIS}}": analysis.get("investment_thesis", ""),
        "{{REFRESH_DATE}}": source_meta.get("generated_at_utc", datetime.now().strftime("%Y-%m-%d")),
        "{{LATEST_PRICE_DATE}}": latest_price_date,
        "{{SOURCE_AUDIT_HTML}}": source_audit_html,
        "{{CITE_FUNDAMENTALS}}": source_citations["fundamentals"],
        "{{CITE_DCF}}": source_citations["dcf"],
        "{{CITE_ANALYST_TARGETS}}": source_citations["analyst_targets"],
        "{{CITE_EARNINGS}}": source_citations["earnings"],
        "{{CITE_NEWS_SENTIMENT}}": source_citations["news_sentiment"],
        "{{CITE_AI}}": source_citations["ai"],
        "{{DCF_WIDGET_HTML}}": dcf_html,
        "{{PEERS_WIDGET_HTML}}": peers_html,
        "{{INSIDERS_WIDGET_HTML}}": insiders_html,
        "{{GROWTH_RATE_DCF}}": f"{sd['dcf_data']['growth_rate']:.1f}" if sd.get("dcf_data") and "growth_rate" in sd["dcf_data"] else ("15.0" if sd.get("dcf_data") else "8.0"),
        "{{RAW_PAYLOAD}}": json.dumps(raw_data_payload, default=_safe_json)
    }
    
    for marker, value in replacements.items():
        val_str = str(value)
        # Ensure newlines in AI paragraphs are rendered as line breaks in HTML
        if marker in ["{{EXECUTIVE_SUMMARY}}", "{{REVENUE_QUALITY}}", "{{PROFITABILITY}}", 
                      "{{COMPETITIVE_MOAT}}", "{{EARNINGS_POWER}}", "{{BALANCE_SHEET_HEALTH}}", 
                      "{{CAPITAL_ALLOCATION}}", "{{UNIT_ECONOMICS}}", "{{REGULATORY_ANTITRUST}}", "{{GEOPOLITICAL_RISK}}",
                      "{{MACRO_ENVIRONMENT}}", "{{SECTOR_OUTLOOK}}", "{{GUIDANCE_EXPECTATIONS}}", 
                      "{{ANALYST_SENTIMENT}}", "{{INSTITUTIONAL_POSITIONING}}", "{{NEWS_SENTIMENT}}", 
                      "{{INTRINSIC_VALUE_ESTIMATE}}", "{{MARGIN_OF_SAFETY}}", "{{WORST_CASE_SCENARIO}}", 
                      "{{POSITION_SIZING}}", "{{INVESTMENT_THESIS}}"]:
            val_str = val_str.replace("\n", "<br>")
            
        html = html.replace(marker, val_str)
        
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return str(output_path)
