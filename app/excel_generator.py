import pandas as pd
from pathlib import Path
import math

TOTAL_LINE_KEYWORDS = [
    "total revenue", "revenue", "gross profit", "operating income", "ebitda", 
    "net income", "total assets", "total liabilities", "total equity",
    "operating cash flow", "free cash flow", "cash at end of period"
]

def format_sheet(writer, sheet_name, df):
    worksheet = writer.sheets[sheet_name]
    workbook = writer.book
    
    # Custom Formats
    header_fmt = workbook.add_format({
        'bold': True,
        'bg_color': '#0e0e11',
        'font_color': '#fafafa',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_name': 'Segoe UI',
        'font_size': 10
    })
    
    label_fmt = workbook.add_format({
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border': 1
    })
    
    num_fmt = workbook.add_format({
        'font_name': 'Segoe UI',
        'font_size': 10,
        'num_format': '$#,##0',
        'border': 1
    })
    
    # Totals Format (Wall Street style: bold + double underline bottom)
    total_label_fmt = workbook.add_format({
        'bold': True,
        'font_name': 'Segoe UI',
        'font_size': 10,
        'border': 1,
        'bg_color': '#f4f4f5'
    })
    
    total_num_fmt = workbook.add_format({
        'bold': True,
        'font_name': 'Segoe UI',
        'font_size': 10,
        'num_format': '$#,##0',
        'border': 1,
        'top': 1,
        'bottom': 6, # Double bottom border
        'bg_color': '#f4f4f5'
    })

    # 1. Overwrite headers with our custom header format
    headers = [df.index.name or 'Line Item'] + [
        col.strftime('%Y-%m-%d') if hasattr(col, 'strftime') else str(col) 
        for col in df.columns
    ]
    for col_idx, text in enumerate(headers):
        worksheet.write(0, col_idx, text, header_fmt)
        
    # 2. Iterate and apply row styling
    for row_idx, (line_item, row_data) in enumerate(df.iterrows()):
        is_total = any(k in str(line_item).lower() for k in TOTAL_LINE_KEYWORDS)
        
        # Determine format
        l_fmt = total_label_fmt if is_total else label_fmt
        n_fmt = total_num_fmt if is_total else num_fmt
        
        # Write Column A (Label)
        worksheet.write(row_idx + 1, 0, str(line_item), l_fmt)
        
        # Write data columns
        for col_idx, val in enumerate(row_data):
            if pd.isna(val) or val == "":
                worksheet.write_blank(row_idx + 1, col_idx + 1, None, n_fmt)
            else:
                worksheet.write_number(row_idx + 1, col_idx + 1, float(val), n_fmt)
                
    # 3. Auto-fit columns based on text length
    max_len = len(df.index.name or 'Line Item')
    for line_item in df.index:
        max_len = max(max_len, len(str(line_item)))
    worksheet.set_column(0, 0, max_len + 3) # Line Item column width
    
    for col_idx, col in enumerate(df.columns):
        col_name = col.strftime('%Y-%m-%d') if hasattr(col, 'strftime') else str(col)
        col_width = max(len(col_name), 12) + 2
        worksheet.set_column(col_idx + 1, col_idx + 1, col_width)

def generate_excel_model(ticker: str, stock_data: dict, output_dir: Path, analysis: dict = None):
    """
    Generates a professional Excel financial model containing:
    - AI Equity Research & Valuation Reconciliations (First tab!)
    - Historical Financials (Income Statement, Balance Sheet, Cash Flow)
    - Dynamic DCF Projections with LIVE Excel formulas
    - Financial Health & Solvency Check (Altman Z-Score, Piotroski F-Score)
    """
    if analysis is None:
        analysis = stock_data.get("analysis") or {}
        
    excel_path = output_dir / f"{ticker}_Financial_Model.xlsx"
    
    with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # ─── 0. AI RESEARCH & VERDICT SHEET (Added as the first tab!) ────────────────────
        if analysis:
            ai_worksheet = workbook.add_worksheet('AI Research & Verdict')
            writer.sheets['AI Research & Verdict'] = ai_worksheet
            
            # Hide grid lines
            ai_worksheet.hide_gridlines(2)
            
            # Style Formats
            ai_title_fmt = workbook.add_format({
                'bold': True, 'font_size': 14, 'font_name': 'Segoe UI', 
                'bg_color': '#0e0e11', 'font_color': '#fafafa', 'align': 'center', 'valign': 'vcenter'
            })
            ai_section_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#18181b', 'font_color': '#fafafa', 'border': 1,
                'font_name': 'Segoe UI', 'font_size': 10, 'border_color': '#27272a'
            })
            ai_label_bold_fmt = workbook.add_format({
                'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'bold': True, 
                'bg_color': '#f4f4f5', 'border_color': '#e4e4e7', 'valign': 'top'
            })
            ai_label_fmt = workbook.add_format({
                'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 
                'border_color': '#e4e4e7', 'valign': 'top'
            })
            ai_text_wrap_fmt = workbook.add_format({
                'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 
                'border_color': '#e4e4e7', 'text_wrap': True, 'valign': 'top'
            })
            
            # Metric Number Formats
            num_price_fmt = workbook.add_format({
                'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'num_format': '$#,##0.00',
                'border_color': '#e4e4e7', 'valign': 'top'
            })
            total_pct_fmt = workbook.add_format({
                'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'top': 1, 'bottom': 6,
                'bg_color': '#f4f4f5', 'num_format': '0.0%', 'border_color': '#e4e4e7', 'valign': 'top'
            })
            
            # Colored Verdict Formats
            verdict = str(analysis.get('verdict', 'HOLD')).upper()
            if verdict in ["STRONG BUY", "BUY"]:
                verdict_fmt = workbook.add_format({
                    'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'border': 1,
                    'bg_color': '#d1fae5', 'font_color': '#065f46', 'align': 'left', 'valign': 'top',
                    'border_color': '#e4e4e7'
                })
            elif verdict in ["SELL", "STRONG SELL"]:
                verdict_fmt = workbook.add_format({
                    'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'border': 1,
                    'bg_color': '#fee2e2', 'font_color': '#991b1b', 'align': 'left', 'valign': 'top',
                    'border_color': '#e4e4e7'
                })
            else:  # HOLD
                verdict_fmt = workbook.add_format({
                    'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'border': 1,
                    'bg_color': '#fef3c7', 'font_color': '#92400e', 'align': 'left', 'valign': 'top',
                    'border_color': '#e4e4e7'
                })
                
            # Setup columns widths
            ai_worksheet.set_column(0, 0, 32)  # Category
            ai_worksheet.set_column(1, 1, 95)  # Values & Narratives
            
            # Title Row
            ai_worksheet.merge_range("A1:B2", f"{ticker} — AI Equity Research & Verdict Terminal", ai_title_fmt)
            ai_worksheet.set_row(0, 20)
            ai_worksheet.set_row(1, 20)
            
            # Section 1: Dashboard
            ai_worksheet.merge_range("A4:B4", "AI Valuation & Verdict Dashboard", ai_section_fmt)
            ai_worksheet.set_row(3, 22)
            
            metrics = stock_data.get('key_metrics') or {}
            
            dash_items = [
                ("AI Investment Verdict", verdict, verdict_fmt),
                ("Target Price (12-Month)", float(analysis.get('price_target_12m') or 0), num_price_fmt),
                ("Current Stock Price", float(metrics.get('current_price') or 0), num_price_fmt),
                ("Implied 12M Return (%)", "=(B6-B7)/B7", total_pct_fmt),
                ("Fair Value Midpoint", float((analysis.get('valuation_assessment') or {}).get('fair_value_mid') or 0), num_price_fmt),
                ("Fair Value Range", f"Low: ${float((analysis.get('valuation_assessment') or {}).get('fair_value_low') or 0):.2f} to High: ${float((analysis.get('valuation_assessment') or {}).get('fair_value_high') or 0):.2f}", ai_text_wrap_fmt),
                ("Valuation Grade", (analysis.get('valuation_assessment') or {}).get('valuation_grade') or "N/A", ai_text_wrap_fmt),
                ("Verdict Confidence Score", f"{analysis.get('verdict_confidence', 50)}%", ai_text_wrap_fmt),
            ]
            
            for idx, (label, val, fmt) in enumerate(dash_items):
                r = 4 + idx
                ai_worksheet.set_row(r, 20)
                ai_worksheet.write(r, 0, label, ai_label_bold_fmt)
                if isinstance(val, str) and val.startswith("="):
                    ai_worksheet.write_formula(r, 1, val, fmt)
                elif isinstance(val, (int, float)):
                    ai_worksheet.write_number(r, 1, val, fmt)
                else:
                    ai_worksheet.write(r, 1, str(val), fmt)
                    
            # Section 2: Thesis & Strategy
            ai_worksheet.merge_range("A14:B14", "AI Investment Thesis & Sizing Strategy", ai_section_fmt)
            ai_worksheet.set_row(13, 22)
            
            thesis_items = [
                ("Executive Summary", analysis.get('executive_summary') or "N/A"),
                ("Verdict Reasoning Thesis", analysis.get('verdict_reasoning') or "N/A"),
                ("Target Position Sizing & Rules", analysis.get('position_sizing') or "N/A"),
            ]
            
            def get_row_height(text, width=90):
                if not text:
                    return 18
                lines = math.ceil(len(str(text)) / width)
                return max(18, lines * 15.5 + 8)

            for idx, (label, text) in enumerate(thesis_items):
                r = 14 + idx
                h = get_row_height(text, width=95)
                ai_worksheet.set_row(r, h)
                ai_worksheet.write(r, 0, label, ai_label_bold_fmt)
                ai_worksheet.write(r, 1, text, ai_text_wrap_fmt)
                
            # Section 3: Deep Fundamental Analysis
            ai_worksheet.merge_range("A19:B19", "Fundamental Deep-Dive Analysis", ai_section_fmt)
            ai_worksheet.set_row(18, 22)
            
            fund_analysis = analysis.get('fundamental_analysis') or {}
            fund_items = [
                ("Revenue Quality & Mix", fund_analysis.get('revenue_quality') or "N/A"),
                ("Profitability & DuPont ROE", fund_analysis.get('profitability') or "N/A"),
                ("Earnings Power & EPS Quality", fund_analysis.get('earnings_power') or "N/A"),
                ("Balance Sheet Health & Solvency", fund_analysis.get('balance_sheet') or "N/A"),
                ("Competitive Moat & Disruption", fund_analysis.get('competitive_moat') or "N/A"),
            ]
            
            for idx, (label, text) in enumerate(fund_items):
                r = 19 + idx
                h = get_row_height(text, width=95)
                ai_worksheet.set_row(r, h)
                ai_worksheet.write(r, 0, label, ai_label_bold_fmt)
                ai_worksheet.write(r, 1, text, ai_text_wrap_fmt)
                
            # Section 4: Macro & Sentiment
            ai_worksheet.merge_range("A26:B26", "Macro Environment & Sentiment Outlook", ai_section_fmt)
            ai_worksheet.set_row(25, 22)
            
            macro_analysis = analysis.get('macro_analysis') or {}
            sentiment_analysis = analysis.get('sentiment_analysis') or {}
            macro_items = [
                ("Macro Environment Impact", macro_analysis.get('macro_environment') or "N/A"),
                ("Sector Outlook & Growth", macro_analysis.get('sector_outlook') or "N/A"),
                ("Wall Street Analyst Sentiment", sentiment_analysis.get('analyst_sentiment') or "N/A"),
                ("Institutional Flow & Insider Activity", sentiment_analysis.get('institutional_positioning') or "N/A"),
                ("Media Coverage & Public Sentiment", sentiment_analysis.get('news_sentiment') or "N/A"),
                ("Forward Guidance & Expectations", analysis.get('guidance_and_expectations') or "N/A"),
            ]
            
            for idx, (label, text) in enumerate(macro_items):
                r = 26 + idx
                h = get_row_height(text, width=95)
                ai_worksheet.set_row(r, h)
                ai_worksheet.write(r, 0, label, ai_label_bold_fmt)
                ai_worksheet.write(r, 1, text, ai_text_wrap_fmt)
                
            # Section 5: Catalysts Table
            ai_worksheet.merge_range("A33:B33", "Upcoming Catalysts & Timeline", ai_section_fmt)
            ai_worksheet.set_row(32, 22)
            
            catalysts = analysis.get('catalysts') or []
            cat_count = 0
            for idx, cat in enumerate(catalysts[:4]):
                r = 33 + idx
                c_text = cat.get('catalyst', 'N/A')
                c_timeline = cat.get('timeline', 'N/A')
                c_impact = cat.get('impact', 'POSITIVE')
                
                full_text = f"[{c_timeline} | Impact: {c_impact}] {c_text}"
                h = get_row_height(full_text, width=95)
                
                ai_worksheet.set_row(r, h)
                ai_worksheet.write(r, 0, f"Catalyst {idx+1}", ai_label_bold_fmt)
                ai_worksheet.write(r, 1, full_text, ai_text_wrap_fmt)
                cat_count += 1
                
            # Section 6: Risks Table
            start_r_risk = 33 + cat_count
            ai_worksheet.merge_range(f"A{start_r_risk+1}:B{start_r_risk+1}", "Operational Risks & Threat Severity", ai_section_fmt)
            ai_worksheet.set_row(start_r_risk, 22)
            
            risks = (analysis.get('risk_assessment') or {}).get('risk_factors') or []
            for idx, rk in enumerate(risks[:4]):
                r = start_r_risk + 1 + idx
                r_text = rk.get('risk', 'N/A')
                r_sev = rk.get('severity', 'MEDIUM')
                r_prob = rk.get('probability', 'MEDIUM')
                r_impact = rk.get('impact', 'N/A')
                
                full_text = f"[{r_sev} Severity | {r_prob} Probability] {r_text} Impact: {r_impact}"
                h = get_row_height(full_text, width=95)
                
                ai_worksheet.set_row(r, h)
                ai_worksheet.write(r, 0, f"Risk {idx+1}", ai_label_bold_fmt)
                ai_worksheet.write(r, 1, full_text, ai_text_wrap_fmt)
    """
    Generates a professional Excel financial model containing:
    - Historical Financials (Income Statement, Balance Sheet, Cash Flow)
    - Dynamic DCF Projections with LIVE Excel formulas
    - Financial Health & Solvency Check (Altman Z-Score, Piotroski F-Score)
    """
    excel_path = output_dir / f"{ticker}_Financial_Model.xlsx"
    
    with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # 1. Income Statement
        if not stock_data.get('quarterly_financials', pd.DataFrame()).empty:
            df_inc = stock_data['quarterly_financials'].copy()
            df_inc.index.name = 'Line Item'
            df_inc.to_excel(writer, sheet_name='Income Statement', index=True)
            format_sheet(writer, 'Income Statement', df_inc)
            
        # 2. Balance Sheet
        if not stock_data.get('quarterly_balance_sheet', pd.DataFrame()).empty:
            df_bal = stock_data['quarterly_balance_sheet'].copy()
            df_bal.index.name = 'Line Item'
            df_bal.to_excel(writer, sheet_name='Balance Sheet', index=True)
            format_sheet(writer, 'Balance Sheet', df_bal)
            
        # 3. Cash Flow
        if not stock_data.get('quarterly_cashflow', pd.DataFrame()).empty:
            df_cf = stock_data['quarterly_cashflow'].copy()
            df_cf.index.name = 'Line Item'
            df_cf.to_excel(writer, sheet_name='Cash Flow', index=True)
            format_sheet(writer, 'Cash Flow', df_cf)
            
        # 4. DCF Model & Health Sheet
        worksheet = workbook.add_worksheet('DCF Model & Health')
        writer.sheets['DCF Model & Health'] = worksheet
        
        # Enable Gridlines
        worksheet.hide_gridlines(2)
        
        # Style Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_name': 'Segoe UI', 'font_color': '#0e0e11'
        })
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#0e0e11', 'font_color': '#fafafa', 'border': 1,
            'align': 'center', 'valign': 'vcenter', 'font_name': 'Segoe UI', 'font_size': 10
        })
        section_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#e4e4e7', 'font_color': '#0f172a', 'border': 1,
            'font_name': 'Segoe UI', 'font_size': 10
        })
        label_fmt = workbook.add_format({
            'font_name': 'Segoe UI', 'font_size': 10, 'border': 1
        })
        label_bold_fmt = workbook.add_format({
            'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'bold': True
        })
        num_fmt = workbook.add_format({
            'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'num_format': '$#,##0'
        })
        num_pct_fmt = workbook.add_format({
            'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'num_format': '0.0%'
        })
        num_price_fmt = workbook.add_format({
            'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'num_format': '$#,##0.00'
        })
        num_shares_fmt = workbook.add_format({
            'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'num_format': '#,##0'
        })
        total_label_fmt = workbook.add_format({
            'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'bg_color': '#f4f4f5'
        })
        total_num_fmt = workbook.add_format({
            'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'top': 1, 'bottom': 6,
            'bg_color': '#f4f4f5', 'num_format': '$#,##0.00'
        })
        total_pct_fmt = workbook.add_format({
            'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'border': 1, 'top': 1, 'bottom': 6,
            'bg_color': '#f4f4f5', 'num_format': '0.0%'
        })
        
        # Title Row
        worksheet.write(0, 0, f"{ticker} - Interactive DCF Valuation Model", title_fmt)
        
        # 1. Inputs & Assumptions Header
        worksheet.write(2, 0, "Inputs & Assumptions", section_fmt)
        worksheet.write(2, 1, "Value", section_fmt)
        
        dcf_data = stock_data.get('dcf_data') or {}
        metrics = stock_data.get('key_metrics') or {}
        
        fcf_base = float(dcf_data.get('fcf_base') or metrics.get('freeCashflow') or 0)
        wacc_used = float(dcf_data.get('wacc_used') or 9.0) / 100
        growth_1_5 = 0.15
        growth_6_10 = 0.10
        terminal_growth = float(dcf_data.get('terminal_growth') or 2.5) / 100
        
        total_cash = float(metrics.get('totalCash') or 0)
        total_debt = float(metrics.get('totalDebt') or 0)
        
        # Resolve Shares Outstanding
        shares_out = metrics.get('sharesOutstanding')
        if not shares_out or shares_out <= 1:
            mc = metrics.get('marketCap')
            cp = metrics.get('current_price') or metrics.get('currentPrice')
            if mc and cp:
                shares_out = float(mc / cp)
            else:
                shares_out = 1.0
        else:
            shares_out = float(shares_out)
            
        current_price = float(metrics.get('current_price') or 0)
        
        # Add assumptions list
        assumptions = [
            ("Base Free Cash Flow", fcf_base, num_fmt),
            ("WACC (%)", wacc_used, num_pct_fmt),
            ("Growth Rate Years 1-5 (%)", growth_1_5, num_pct_fmt),
            ("Growth Decay Step (%)", (growth_1_5 - terminal_growth) / 6 if growth_1_5 > terminal_growth else 0, num_pct_fmt),
            ("Terminal Growth Rate (%)", terminal_growth, num_pct_fmt),
            ("Total Cash", total_cash, num_fmt),
            ("Total Debt", total_debt, num_fmt),
            ("Shares Outstanding", shares_out, num_shares_fmt),
            ("Current Stock Price", current_price, num_price_fmt),
        ]
        
        for idx, (label, val, fmt) in enumerate(assumptions):
            row = 3 + idx
            worksheet.write(row, 0, label, label_bold_fmt)
            worksheet.write_number(row, 1, val, fmt)
            
        # 2. 10-Year Projections Table Header
        worksheet.write(14, 0, "10-Year DCF Projection Model", section_fmt)
        for c in range(1, 12):
            worksheet.write(14, c, "", section_fmt)
            
        proj_headers = ["Line Item", "Base (Yr 0)", "Yr 1", "Yr 2", "Yr 3", "Yr 4", "Yr 5", "Yr 6", "Yr 7", "Yr 8", "Yr 9", "Yr 10"]
        for c, text in enumerate(proj_headers):
            worksheet.write(15, c, text, header_fmt)
            
        # Write Year Numbers Row 17 (index 16)
        worksheet.write(16, 0, "Year Index", label_bold_fmt)
        worksheet.write_number(16, 1, 0, label_fmt)
        for i in range(1, 11):
            worksheet.write_number(16, 1 + i, i, label_fmt)
            
        # Write Growth Rates Row 18 (index 17)
        worksheet.write(17, 0, "Growth Rate (%)", label_bold_fmt)
        worksheet.write_blank(17, 1, None, num_pct_fmt)
        for i in range(1, 11):
            if i <= 5:
                ref_cell = "$B$6"
            else:
                ref_cell = f"MAX($B$8, $B$6 - ($B$7 * {i - 5}))"
            worksheet.write_formula(17, 1 + i, f"={ref_cell}", num_pct_fmt)
            
        # Write Free Cash Flows Row 19 (index 18)
        worksheet.write(18, 0, "Free Cash Flow", label_bold_fmt)
        worksheet.write_formula(18, 1, "=$B$4", num_fmt)
        for i in range(1, 11):
            prev_col = chr(ord('A') + i)
            this_col = chr(ord('A') + 1 + i)
            worksheet.write_formula(18, 1 + i, f"={prev_col}19*(1+{this_col}18)", num_fmt)
            
        # Write Discount Factors Row 20 (index 19)
        worksheet.write(19, 0, "Discount Factor (Mid-Year)", label_bold_fmt)
        worksheet.write_number(19, 1, 1.0, num_price_fmt)
        for i in range(1, 11):
            this_col = chr(ord('A') + 1 + i)
            worksheet.write_formula(19, 1 + i, f"=1/((1+$B$5)^({this_col}17-0.5))", num_price_fmt)
            
        # Write PV of FCFs Row 21 (index 20)
        worksheet.write(20, 0, "PV of Free Cash Flow", label_bold_fmt)
        worksheet.write_blank(20, 1, None, num_fmt)
        for i in range(1, 11):
            this_col = chr(ord('A') + 1 + i)
            worksheet.write_formula(20, 1 + i, f"={this_col}19*{this_col}20", num_fmt)
            
        # 3. DCF Valuation Summary Row 23 (index 22)
        worksheet.write(22, 0, "DCF Valuation Summary", section_fmt)
        worksheet.write(22, 1, "Value", section_fmt)
        
        worksheet.write(23, 0, "Cumulative PV of FCFs", label_bold_fmt)
        worksheet.write_formula(23, 1, "=SUM(C21:L21)", num_fmt)
        
        worksheet.write(24, 0, "Terminal Value (at Yr 10)", label_bold_fmt)
        worksheet.write_formula(24, 1, "=(L19*(1+$B$8))/($B$5-$B$8)", num_fmt)
        
        worksheet.write(25, 0, "PV of Terminal Value", label_bold_fmt)
        worksheet.write_formula(25, 1, "=B25*L20", num_fmt)
        
        worksheet.write(26, 0, "Enterprise Value", label_bold_fmt)
        worksheet.write_formula(26, 1, "=B24+B26", num_fmt)
        
        worksheet.write(27, 0, "Add: Cash & Equivalents", label_bold_fmt)
        worksheet.write_formula(27, 1, "=$B$9", num_fmt)
        
        worksheet.write(28, 0, "Less: Total Debt", label_bold_fmt)
        worksheet.write_formula(28, 1, "=$B$10", num_fmt)
        
        worksheet.write(29, 0, "Implied Equity Value", label_bold_fmt)
        worksheet.write_formula(29, 1, "=B27+B28-B29", num_fmt)
        
        worksheet.write(30, 0, "Shares Outstanding", label_bold_fmt)
        worksheet.write_formula(30, 1, "=$B$11", num_shares_fmt)
        
        worksheet.write(31, 0, "Implied Fair Value per Share", total_label_fmt)
        worksheet.write_formula(31, 1, "=B30/B31", total_num_fmt)
        
        worksheet.write(32, 0, "Current Stock Price", label_bold_fmt)
        worksheet.write_formula(32, 1, "=$B$12", num_price_fmt)
        
        worksheet.write(33, 0, "Upside / (Downside)", label_bold_fmt)
        worksheet.write_formula(33, 1, "=(B32-B33)/B33", total_pct_fmt)
        
        # 4. Financial Health & Solvency Check Row 36 (index 35)
        worksheet.write(35, 0, "Financial Health & Solvency Check", section_fmt)
        worksheet.write(35, 1, "", section_fmt)
        
        scores = stock_data.get('financial_scores') or {}
        worksheet.write(36, 0, "Altman Z-Score", label_bold_fmt)
        worksheet.write(36, 1, scores.get("altman_z_label", "N/A"), label_fmt)
        
        worksheet.write(37, 0, "Piotroski F-Score", label_bold_fmt)
        worksheet.write(37, 1, scores.get("piotroski_f_label", "N/A"), label_fmt)
        
        # Setup column widths
        worksheet.set_column(0, 0, 30) # Line Item Column
        worksheet.set_column(1, 1, 20) # Value Column
        for c in range(2, 12):
            worksheet.set_column(c, c, 14) # Yr 1-10 Columns
            
    return excel_path
