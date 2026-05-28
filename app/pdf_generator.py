"""
PDF Generator -- Fundamental/Macro/Sentiment focused PDF report
"""
from fpdf import FPDF
from pathlib import Path
from datetime import datetime

def _s(text):
    if not isinstance(text,str): text=str(text)
    reps={'\u2014':'--','\u2013':'-','\u2018':"'",'\u2019':"'",'\u201c':'"','\u201d':'"',
          '\u2022':'*','\u2026':'...','\u00b7':'*','\u2212':'-','\u2264':'<=','\u2265':'>='}
    for o,n in reps.items(): text=text.replace(o,n)
    return text.encode('latin-1',errors='replace').decode('latin-1')

class StockPDF(FPDF):
    def __init__(self,ticker,company):
        super().__init__()
        self.ticker=ticker; self.company=_s(company)
        self.set_auto_page_break(True,margin=20)
    def header(self):
        if self.page_no()==1: return
        self.set_font("Helvetica","B",8); self.set_text_color(150,150,150)
        self.cell(0,8,f"{self.company} ({self.ticker}) - AI Equity Research",align="L")
        self.ln(3); self.set_draw_color(37,99,235); self.set_line_width(0.5)
        self.line(10,self.get_y(),200,self.get_y()); self.ln(5)
    def footer(self):
        self.set_y(-15); self.set_font("Helvetica","I",7); self.set_text_color(120,120,120)
        self.cell(0,10,f"Page {self.page_no()}/{{nb}} | {datetime.now().strftime('%Y-%m-%d')} | AI Equity Research",align="C")

def _cover(pdf,sd,a):
    pdf.add_page(); pdf.set_fill_color(8,8,16); pdf.rect(0,0,210,297,"F")
    pdf.set_y(50); pdf.set_font("Helvetica","B",42); pdf.set_text_color(37,99,235)
    pdf.cell(0,20,_s(sd["ticker"]),align="C",new_x="LMARGIN",new_y="NEXT")
    pdf.set_font("Helvetica","",14); pdf.set_text_color(200,200,200)
    pdf.cell(0,10,_s(sd["company_name"]),align="C",new_x="LMARGIN",new_y="NEXT")
    pdf.set_font("Helvetica","",9); pdf.set_text_color(130,130,130)
    pdf.cell(0,8,f"{sd['key_metrics'].get('sector','N/A')} | {sd['key_metrics'].get('industry','N/A')}",align="C",new_x="LMARGIN",new_y="NEXT")
    pdf.ln(5); pdf.cell(0,8,"AI Equity Research Report",align="C",new_x="LMARGIN",new_y="NEXT")
    pdf.cell(0,8,datetime.now().strftime("%B %d, %Y"),align="C",new_x="LMARGIN",new_y="NEXT")
    # Verdict
    pdf.ln(15); v=a.get("verdict","HOLD"); conf=a.get("verdict_confidence",50)
    vc=(16,185,129) if v in ["BUY","STRONG BUY"] else (239,68,68) if v in ["SELL","STRONG SELL"] else (245,158,11)
    pdf.set_fill_color(*vc); bw=80; bx=(210-bw)/2
    pdf.set_xy(bx,pdf.get_y()); pdf.set_font("Helvetica","B",24); pdf.set_text_color(255,255,255)
    pdf.cell(bw,18,_s(v),align="C",fill=True,new_x="LMARGIN",new_y="NEXT")
    pdf.set_xy(bx,pdf.get_y()); pdf.set_font("Helvetica","",10)
    pdf.cell(bw,10,f"Confidence: {conf}%",align="C",fill=True,new_x="LMARGIN",new_y="NEXT")
    # Key stats
    pdf.ln(12); m=sd["key_metrics"]
    def fmt(val):
        if val is None: return "N/A"
        if isinstance(val,str): return val
        if abs(val)>=1e12: return f"${val/1e12:.2f}T"
        if abs(val)>=1e9: return f"${val/1e9:.2f}B"
        if abs(val)>=1e6: return f"${val/1e6:.2f}M"
        return f"${val:,.0f}"
    scores = sd.get("financial_scores", {})
    z = scores.get("altman_z_label", "N/A")
    f = scores.get("piotroski_f_label", "N/A")
    stats1 = f"Price: ${m.get('current_price',0):.2f} | MCap: {fmt(m.get('marketCap'))} | P/E: {m.get('trailingPE','N/A')} | Target: ${m.get('targetMeanPrice','N/A')}"
    stats2 = f"Altman Z-Score: {z} | Piotroski F-Score: {f}"
    pdf.set_font("Helvetica", "", 9); pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 5, _s(stats1), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, _s(stats2), align="C", new_x="LMARGIN", new_y="NEXT")
    # Investment thesis
    pdf.ln(10); pdf.set_font("Helvetica","I",10); pdf.set_text_color(180,180,200)
    pdf.multi_cell(0,6,_s(str(a.get("investment_thesis",""))),align="C")

def _sec(pdf,title,body,color=(37,99,235)):
    pdf.set_font("Helvetica","B",13); pdf.set_text_color(*color)
    pdf.cell(0,12,_s(title),new_x="LMARGIN",new_y="NEXT")
    pdf.set_draw_color(*color); pdf.set_line_width(0.4)
    pdf.line(10,pdf.get_y(),80,pdf.get_y()); pdf.ln(4)
    pdf.set_font("Helvetica","",9.5); pdf.set_text_color(60,60,60)
    if isinstance(body,list):
        for i in body: pdf.multi_cell(0,5.5,_s(f"  *  {i}"),new_x="LMARGIN",new_y="NEXT")
    elif body and str(body)!="N/A":
        pdf.multi_cell(0,5.5,_s(str(body)))
    pdf.ln(5)

def _subsec(pdf,title,body):
    pdf.set_font("Helvetica","B",10); pdf.set_text_color(80,80,120)
    pdf.cell(0,8,_s(title),new_x="LMARGIN",new_y="NEXT"); pdf.ln(1)
    pdf.set_font("Helvetica","",9.5); pdf.set_text_color(60,60,60)
    if body and str(body)!="N/A": pdf.multi_cell(0,5.5,_s(str(body)))
    pdf.ln(4)

def _chart(pdf,path,title=None):
    if path and Path(path).exists():
        if title:
            pdf.set_font("Helvetica","B",10); pdf.set_text_color(37,99,235)
            pdf.cell(0,10,_s(title),new_x="LMARGIN",new_y="NEXT")
        if 297-pdf.get_y()-20<70: pdf.add_page()
        pdf.image(str(path),x=10,w=190); pdf.ln(5)

def generate_pdf(stock_data,analysis,charts,output_path):
    output_path=Path(output_path); output_path.parent.mkdir(parents=True,exist_ok=True)
    pdf=StockPDF(stock_data["ticker"],stock_data["company_name"]); pdf.alias_nb_pages()
    fa=analysis.get("fundamental_analysis",{}) if isinstance(analysis.get("fundamental_analysis"),dict) else {}
    ma=analysis.get("macro_analysis",{}) if isinstance(analysis.get("macro_analysis"),dict) else {}
    sa=analysis.get("sentiment_analysis",{}) if isinstance(analysis.get("sentiment_analysis"),dict) else {}
    va=analysis.get("valuation_assessment",{}) if isinstance(analysis.get("valuation_assessment"),dict) else {}
    ra=analysis.get("risk_assessment",{}) if isinstance(analysis.get("risk_assessment"),dict) else {}

    _cover(pdf,stock_data,analysis)

    # Executive Summary
    pdf.add_page()
    _sec(pdf,"Executive Summary",analysis.get("executive_summary","N/A"))
    _chart(pdf,charts.get("price"),"Price Context (1Y)")

    # Fundamentals (40%)
    pdf.add_page()
    _sec(pdf,"Fundamental Analysis (40% Weight)","")
    _subsec(pdf,"Revenue Quality",fa.get("revenue_quality"))
    _subsec(pdf,"Profitability & Margins",fa.get("profitability"))
    _subsec(pdf,"Earnings Power",fa.get("earnings_power"))
    _subsec(pdf,"Balance Sheet Health",fa.get("balance_sheet"))
    _subsec(pdf,"Competitive Moat",fa.get("competitive_moat"))
    _chart(pdf,charts.get("financials"),"Revenue & Profitability")

    # Macro (25%)
    pdf.add_page()
    _sec(pdf,"Macro & Sector Analysis (25% Weight)","",color=(6,182,212))
    _subsec(pdf,"Macroeconomic Environment",ma.get("macro_environment"))
    _subsec(pdf,"Sector Outlook",ma.get("sector_outlook"))
    tw=ma.get("tailwinds",[])
    hw=ma.get("headwinds",[])
    if tw: _sec(pdf,"Tailwinds",tw if isinstance(tw,list) else [],color=(16,185,129))
    if hw: _sec(pdf,"Headwinds",hw if isinstance(hw,list) else [],color=(239,68,68))

    # Sentiment (20%)
    pdf.add_page()
    _sec(pdf,"Sentiment Analysis (20% Weight)","",color=(168,85,247))
    _subsec(pdf,"Analyst Sentiment",sa.get("analyst_sentiment"))
    _subsec(pdf,"Institutional Positioning",sa.get("institutional_positioning"))
    _subsec(pdf,"News & Market Sentiment",sa.get("news_sentiment"))

    # Valuation
    _sec(pdf,"Valuation Assessment","")
    _subsec(pdf,"Current Valuation",va.get("current_valuation"))
    _subsec(pdf,"Intrinsic Value Estimate",va.get("intrinsic_value_estimate"))
    _subsec(pdf,"Margin of Safety",va.get("margin_of_safety"))
    _chart(pdf,charts.get("returns"),"Cumulative Returns")

    # Risks (14%)
    pdf.add_page()
    _sec(pdf,"Risk Assessment (14% Weight)","",color=(239,68,68))
    rfs=ra.get("risk_factors",[])
    if isinstance(rfs,list):
        for rf in rfs:
            if isinstance(rf,dict):
                pdf.set_font("Helvetica","B",9); pdf.set_text_color(200,60,60)
                pdf.cell(0,6,_s(f"[{rf.get('severity','?')}] {rf.get('risk','')}"),new_x="LMARGIN",new_y="NEXT")
                pdf.set_font("Helvetica","",9); pdf.set_text_color(80,80,80)
                pdf.multi_cell(0,5,_s(f"  {rf.get('impact','')}"),new_x="LMARGIN",new_y="NEXT"); pdf.ln(3)
            else:
                pdf.set_font("Helvetica","",9); pdf.set_text_color(80,80,80)
                pdf.multi_cell(0,5,_s(f"  * {rf}"),new_x="LMARGIN",new_y="NEXT")
    _subsec(pdf,"Worst Case Scenario",ra.get("worst_case_scenario"))

    # Catalysts
    cats=analysis.get("catalysts",[])
    if isinstance(cats,list) and cats:
        _sec(pdf,"Catalysts & Timeline","")
        for c in cats:
            if isinstance(c,dict):
                pdf.set_font("Helvetica","B",9); pdf.set_text_color(60,60,80)
                pdf.cell(0,6,_s(f"[{c.get('timeline','')}] {c.get('catalyst','')}"),new_x="LMARGIN",new_y="NEXT"); pdf.ln(2)

    # Outlook
    _sec(pdf,"Outlook & Position Sizing","")
    _subsec(pdf,"Short-Term (1-3 months)",analysis.get("short_term_outlook"))
    _subsec(pdf,"Long-Term (1-5 years)",analysis.get("long_term_outlook"))
    _subsec(pdf,"Position Sizing",analysis.get("position_sizing"))
    _subsec(pdf,"Verdict Reasoning",analysis.get("verdict_reasoning"))

    # Disclaimer
    pdf.ln(10); pdf.set_font("Helvetica","I",7); pdf.set_text_color(130,130,130)
    pdf.multi_cell(0,4,"DISCLAIMER: This report was generated by AI for informational purposes only. "
        "Not financial advice. Always do your own research and consult a qualified advisor.")
    pdf.output(str(output_path))
    return str(output_path)
