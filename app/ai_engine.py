"""
AI Engine -- Fundamental, Macro, Sentiment & Risk analysis via Groq (free Llama 3.3 70B)
Technical analysis is intentionally minimized to ~1% weight.
"""
import json
import time
import requests
import logging
from datetime import datetime
import pandas as pd
from config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE, GROQ_API_KEYS

logger = logging.getLogger(__name__)

def _fmt_num(v):
    if v is None: return "N/A"
    if isinstance(v, str): return v
    if abs(v) >= 1e12: return f"${v/1e12:.2f}T"
    if abs(v) >= 1e9: return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6: return f"${v/1e6:.2f}M"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def _fmt_pct(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "N/A"
    return f"{v*100:.2f}%"

def _num_or_none(v):
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt_pct_explicit(raw, pct):
    if pct is not None:
        return f"{pct:.2f}%"
    return _fmt_pct(raw)


def _build_summary(sd):
    m = sd["key_metrics"]
    dcf = sd.get("dcf_data") or {}
    advanced = sd.get("advanced_models") or {}
    mc = advanced.get("monte_carlo") or {}
    sec_data = sd.get("sec_data") or {}
    sources = sd.get("source_metadata") or {}
    providers = sources.get("providers", {})
    freshness = sources.get("freshness", {})
    availability = sources.get("availability", {})
    lines = [
        f"# {sd['company_name']} ({sd['ticker']})",
        f"Analysis dataset generated at UTC: {sources.get('generated_at_utc', 'N/A')}",
        f"Sector: {m.get('sector','N/A')} | Industry: {m.get('industry','N/A')}",
        f"Employees: {m.get('fullTimeEmployees','N/A')}",
        f"Business: {str(m.get('longBusinessSummary','N/A'))[:400]}",
        "",
        "## SOURCE PROVENANCE",
        f"Market and financial data: {providers.get('market_data', 'Yahoo Finance via yfinance')}",
        f"SEC filings: {providers.get('sec_filings', 'SEC EDGAR submissions and companyfacts APIs')} | Available: {availability.get('sec_edgar', 'N/A')}",
        f"News sentiment: {providers.get('news_sentiment', 'Alpha Vantage NEWS_SENTIMENT API')}",
        f"AI analysis provider: {providers.get('ai_analysis', 'Groq OpenAI-compatible chat completions')}",
        f"Latest 1Y price history date: {freshness.get('price_history_1y_last_date', 'N/A')}",
        f"Recent SEC filings: {', '.join(freshness.get('sec_recent_filings', [])[:4]) or 'N/A'}",
        f"Latest quarterly income statement dates: {', '.join(freshness.get('quarterly_income_statement_dates', [])[:4]) or 'N/A'}",
        f"Data availability: price rows={availability.get('history_1y_rows', 'N/A')}, news items={availability.get('news_items', 'N/A')}, peers={availability.get('peer_count', 'N/A')}",
        "",
        "## PRICE DATA",
        f"Price: ${m.get('current_price',0):.2f} | MCap: {_fmt_num(m.get('marketCap'))}",
        f"52W High: ${m.get('high_52w',0):.2f} | 52W Low: ${m.get('low_52w',0):.2f}",
        f"Current price anchor for all targets: ${m.get('current_price',0):.2f}",
        "",
        "## VALUATION METRICS",
        f"Trailing P/E: {m.get('trailingPE','N/A')} | Forward P/E: {m.get('forwardPE','N/A')}",
        f"Price/Book: {m.get('priceToBook','N/A')} | EV/EBITDA: {m.get('enterpriseToEbitda','N/A')}",
        f"PEG Ratio: {m.get('pegRatio','N/A')}",
        f"Forward EPS: {m.get('forwardEps','N/A')} | Trailing EPS: {m.get('trailingEps','N/A')}",
        "",
        "## INCOME & PROFITABILITY",
        f"Total Revenue: {_fmt_num(m.get('totalRevenue'))}",
        f"Revenue Growth (YoY): {_fmt_pct_explicit(m.get('revenueGrowth'), m.get('revenueGrowth_pct'))} (Yahoo raw: {m.get('revenueGrowth','N/A')})",
        f"Earnings Growth: {_fmt_pct_explicit(m.get('earningsGrowth'), m.get('earningsGrowth_pct'))} (Yahoo raw: {m.get('earningsGrowth','N/A')})",
        f"Gross Margins: {_fmt_pct_explicit(m.get('grossMargins'), m.get('grossMargins_pct'))}",
        f"Profit Margin: {_fmt_pct_explicit(m.get('profitMargins'), m.get('profitMargins_pct'))}",
        f"Operating Margin: {_fmt_pct_explicit(m.get('operatingMargins'), m.get('operatingMargins_pct'))}",
        f"EBITDA: {_fmt_num(m.get('ebitda'))}",
        f"Trailing EPS: {m.get('trailingEps','N/A')} | Forward EPS: {m.get('forwardEps','N/A')}",
        "",
        "## RETURN ON CAPITAL",
        f"ROE: {_fmt_pct_explicit(m.get('returnOnEquity'), m.get('returnOnEquity_pct'))}",
        f"ROA: {_fmt_pct_explicit(m.get('returnOnAssets'), m.get('returnOnAssets_pct'))}",
        "",
        "## BALANCE SHEET HEALTH",
        f"Total Cash: {_fmt_num(m.get('totalCash'))}",
        f"Total Debt: {_fmt_num(m.get('totalDebt'))}",
        f"Net Debt: {_fmt_num((m.get('totalDebt') or 0) - (m.get('totalCash') or 0)) if m.get('totalDebt') and m.get('totalCash') else 'N/A'}",
        f"Debt/Equity: {m.get('debtToEquity','N/A')}",
        f"Current Ratio: {m.get('currentRatio','N/A')}",
        f"Quick Ratio: {m.get('quickRatio','N/A')}",
        f"Book Value/Share: {m.get('bookValue','N/A')}",
        "",
        "## CASH FLOW",
        f"Operating Cash Flow: {_fmt_num(m.get('operatingCashflow'))}",
        f"Free Cash Flow: {_fmt_num(m.get('freeCashflow'))}",
        f"FCF Yield: {_fmt_pct(m.get('freeCashflow') / m.get('marketCap')) if m.get('freeCashflow') and m.get('marketCap') else 'N/A'}",
        "",
        "## SHAREHOLDER RETURNS",
        f"Dividend Yield: {_fmt_pct(m.get('dividendYield'))}",
        f"Payout Ratio: {_fmt_pct(m.get('payoutRatio'))}",
        "",
        "## RISK PROFILE",
        f"Beta: {m.get('beta','N/A')}",
        f"Annualized Volatility: {m.get('volatility_annual',0):.1f}%",
        "",
        "## ANALYST SENTIMENT",
        f"Recommendation: {m.get('recommendationKey','N/A')}",
        f"Mean Rating: {m.get('recommendationMean','N/A')} (1=Strong Buy, 5=Strong Sell)",
        f"Number of Analysts: {m.get('numberOfAnalystOpinions','N/A')}",
        f"Target Low: ${m.get('targetLowPrice','N/A')}",
        f"Target Mean: ${m.get('targetMeanPrice','N/A')}",
        f"Target High: ${m.get('targetHighPrice','N/A')}",
    ]

    if sec_data.get("available"):
        lines.extend(["", "## SEC EDGAR DIRECT FACT CHECKS"])
        for label, fact in (sec_data.get("facts_summary") or {}).items():
            if fact:
                lines.append(
                    f"{label}: {fact.get('value')} | concept={fact.get('concept')} | "
                    f"form={fact.get('form')} | filed={fact.get('filed')} | end={fact.get('end')}"
                )

    if dcf:
        lines.extend([
            "",
            "## LOCAL VALUATION ANCHORS",
            f"Local DCF fair value: ${dcf.get('implied_price','N/A')} | Raw DCF before sanity checks: ${dcf.get('raw_dcf_price','N/A')}",
            f"DCF basis: {dcf.get('valuation_basis','N/A')} | WACC: {dcf.get('wacc_used','N/A')}% | Terminal Growth: {dcf.get('terminal_growth','N/A')}%",
            f"Monte Carlo DCF P10/P50/P90: ${mc.get('p10','N/A')} / ${mc.get('p50','N/A')} / ${mc.get('p90','N/A')}",
            "Targets, fair values, and valuation grades must be reconciled against the current price anchor above."
        ])
    
    # 1. Financial Scores & DuPont Analysis
    scores = sd.get("financial_scores", {})
    if scores:
        lines.append("")
        lines.append("## FINANCIAL HEALTH & DECOMPOSITION SCORES")
        if "altman_z" in scores:
            lines.append(f"Altman Z-Score: {scores.get('altman_z')} ({scores.get('altman_z_label')})")
        if "piotroski_f" in scores:
            lines.append(f"Piotroski F-Score: {scores.get('piotroski_f')}/9")
        dp = scores.get("dupont")
        if dp:
            lines.append(f"DuPont ROE Decomposition:")
            lines.append(f"  - Net Profit Margin: {dp.get('net_margin')}%")
            lines.append(f"  - Asset Turnover: {dp.get('asset_turnover')}x")
            lines.append(f"  - Equity Multiplier (Financial Leverage): {dp.get('equity_multiplier')}x")
            lines.append(f"  - Computed DuPont ROE: {dp.get('roe_computed')}%")
            if dp.get("reported_roe") is not None:
                lines.append(f"  - Yahoo Reported ROE: {dp.get('reported_roe')}%")
            if dp.get("note"):
                lines.append(f"  - DuPont Note: {dp.get('note')}")

    # 2. Upcoming Earnings & EPS Estimates
    ed = sd.get("earnings_dates")
    if ed is not None and not ed.empty:
        lines.append("")
        lines.append("## UPCOMING EARNINGS & EPS ESTIMATES")
        try:
            subset = ed.head(5)
            for date, row in subset.iterrows():
                est = row.get("EPS Estimate")
                act = row.get("EPS Actual")
                surp = row.get("EPS Surprise %")
                est_str = f"${est:.2f}" if est is not None and not pd.isna(est) else "N/A"
                act_str = f"${act:.2f}" if act is not None and not pd.isna(act) else "N/A"
                surp_str = f"{surp*100:+.2f}%" if surp is not None and not pd.isna(surp) else "N/A"
                lines.append(f"- Date: {date} | EPS Estimate: {est_str} | EPS Actual: {act_str} | Surprise: {surp_str}")
        except Exception as e:
            lines.append(f"Earnings Dates Error: {str(e)}")

    # 3. Quarterly Income Statement Trends (last 4 quarters)
    qf = sd.get("quarterly_financials")
    if qf is not None and not qf.empty:
        lines.append("")
        lines.append("## QUARTERLY INCOME STATEMENT TRENDS (Last 4 Quarters)")
        try:
            cols = qf.columns[:4]
            rows_to_check = ["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "EBIT", "Research Development", "Selling General Administrative"]
            for r in rows_to_check:
                if r in qf.index:
                    vals = []
                    for c in cols:
                        v = qf.loc[r, c]
                        vals.append(f"{c.strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c)}: {_fmt_num(v)}")
                    lines.append(f"- {r}: " + " | ".join(vals))
        except Exception as e:
            lines.append(f"Quarterly Financials Error: {str(e)}")

    # Performance
    lines.append("")
    lines.append("## STOCK PERFORMANCE")
    for k, l in [("return_1w","1-Week"), ("return_1m","1-Month"), ("return_3m","3-Month"),
                  ("return_6m","6-Month"), ("return_1y","1-Year")]:
        if k in m:
            lines.append(f"{l}: {m[k]:+.2f}%")

    # Alpha Vantage News Sentiment (Top 3 only to conserve tokens)
    news = sd.get("news_sentiment")
    if news and isinstance(news, list) and len(news) > 0:
        lines.append("")
        lines.append("## RECENT NEWS & SENTIMENT (Alpha Vantage)")
        for item in news[:3]:
            title = item.get("title", "No Title")
            summary = item.get("summary", "")[:150] + "..."
            sentiment = item.get("overall_sentiment_label", "Neutral")
            score = item.get("overall_sentiment_score", "0")
            lines.append(f"- [{sentiment} | Score: {score}] {title} ({summary})")

    return "\n".join(lines)


import threading

_RATE_LIMITED_KEYS = {}  # key -> timestamp until which it is on cooldown
_COOLDOWN_LOCK = threading.Lock()

def _call_llm(messages, model=None, max_tokens=None, max_retries=1, system_prompt=None):
    """
    Unified LLM caller that routes to OpenCode (North Mini Code Free) first,
    then Anthropic (Claude), OpenRouter, or Groq as fallbacks.
    """
    from config import ANTHROPIC_API_KEY, OPENROUTER_API_KEY, GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE, OPENCODE_API_KEY, OPENCODE_BASE_URL, OPENCODE_MODEL
    import re

    # Helper to parse JSON and log tokens
    def _process_response(resp, provider):
        data = resp.json()
        
        # Log token usage
        if "usage" in data:
            usage = data["usage"]
            logger.info(f"  [{provider}] Token usage - Prompt: {usage.get('prompt_tokens', 0)}, Completion: {usage.get('completion_tokens', 0)}, Total: {usage.get('total_tokens', 0)}")
            
        content = data["choices"][0]["message"]["content"]
        match = re.search(r'(\{.*\})', content, re.DOTALL)
        if match:
            content = match.group(1)
        content = content.replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"  [{provider}] Malformed JSON received: {e}. Content preview: {content[:100]}...")
            raise ValueError(f"Malformed JSON: {e}")

    # 0. OpenCode API (North Mini Code Free) — Primary Route
    if OPENCODE_API_KEY:
        m_model = OPENCODE_MODEL
        logger.info(f"  > [OpenCode] Calling {m_model}...")
        headers = {
            "Authorization": f"Bearer {OPENCODE_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": m_model,
            "messages": messages,
            "max_tokens": max_tokens or 6000,
            "temperature": 0.25,
        }
        for attempt in range(max_retries):
            try:
                resp = requests.post(OPENCODE_BASE_URL, headers=headers, json=payload, timeout=90)
                resp.raise_for_status()
                return _process_response(resp, "OpenCode")
            except Exception as e:
                logger.info(f"  [!] OpenCode API call failed on attempt {attempt+1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.info("  [!] OpenCode failed permanently — falling back...")


    # 1. OpenRouter Fallback (Nemotron Ultra)
    if OPENROUTER_API_KEY:
        m_model = "nvidia/nemotron-ultra-253b-v1:free"
        logger.info(f"  > [OpenRouter Fallback] Calling Nemotron ({m_model})...")

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "StockerAI Workstation"
        }
        payload = {
            "model": m_model,
            "messages": messages,
            "max_tokens": max_tokens or 6000,
            "temperature": 0.25,
        }
        for attempt in range(max_retries):
            try:
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
                resp.raise_for_status()
                return _process_response(resp, "OpenRouter")
            except Exception as e:
                logger.info(f"  [!] OpenRouter Nemotron fallback failed on attempt {attempt+1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.info("  [!] OpenRouter failed permanently — falling back to Groq...")

    # 2. Groq Last Resort

        now = time.time()
        keys = GROQ_API_KEYS if GROQ_API_KEYS else ([GROQ_API_KEY] if GROQ_API_KEY else [])
        if not keys:
            logger.info("  [X] No Groq API keys available.")
            return None

        m_model = model or GROQ_MODEL
        m_tokens = max_tokens or GROQ_MAX_TOKENS

        for key_idx, current_key in enumerate(keys):
            # Check cooldown status for this key
            with _COOLDOWN_LOCK:
                cooldown_until = _RATE_LIMITED_KEYS.get(current_key, 0)
            
            if now < cooldown_until:
                remaining = int(cooldown_until - now)
                key_masked = current_key[:8] + "..." + current_key[-6:] if len(current_key) > 14 else "..."
                logger.info(f"  [!] Key {key_idx+1}/{len(keys)} ({key_masked}) is on cooldown for {remaining}s. Skipping...")
                continue

            headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
            payload = {
                "model": m_model, "messages": messages,
                "max_tokens": m_tokens, "temperature": GROQ_TEMPERATURE,
                "response_format": {"type": "json_object"},
            }
            
            key_masked = current_key[:8] + "..." + current_key[-6:] if len(current_key) > 14 else "..."
            if len(keys) > 1:
                logger.info(f"  > Trying Groq API with Key {key_idx+1}/{len(keys)} ({key_masked}) for model {m_model}...")

            rotated = False
            for attempt in range(max_retries):
                try:
                    resp = requests.post(GROQ_BASE_URL, headers=headers, json=payload, timeout=30)
                    if resp.status_code == 429:
                        logger.info(f"  [!] Groq 429 Rate Limit hit on key {key_idx+1}. Cooling down key for 300s...")
                        with _COOLDOWN_LOCK:
                            _RATE_LIMITED_KEYS[current_key] = time.time() + 300
                        rotated = True
                        break
                    
                    return _process_response(resp, "Groq")
                except Exception as e:
                    logger.info(f"  [!] API failed for key {key_idx+1} on attempt {attempt+1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt * 2)
                    else:
                        logger.info(f"  [!] API failed permanently for key {key_idx+1}. Cooling down key for 300s...")
                        with _COOLDOWN_LOCK:
                            _RATE_LIMITED_KEYS[current_key] = time.time() + 300
                        rotated = True
            
            if not rotated:
                return None
        return None

def _call_groq(messages, model=None, max_tokens=None, max_retries=1):
    # Simply redirect to unified _call_llm
    # We will pass the system prompt if we can extract it to support Anthropic
    system_prompt = None
    for msg in messages:
        if msg.get("role") == "system":
            system_prompt = msg.get("content")
            break
    return _call_llm(messages, model=model, max_tokens=max_tokens, max_retries=max_retries, system_prompt=system_prompt)



SYSTEM_PROMPT_1 = """You are a ruthless, highly quantitative, 20-year veteran hedge fund portfolio manager. You despise fluff, retail sentiment, and generic summaries. Your analysis is strictly FUNDAMENTALS-FIRST, purely mathematical, and entirely objective. You evaluate companies strictly on unit economics, capital allocation efficiency, return on invested capital (ROIC), and extreme valuation mismatches.

Respond with ONLY valid JSON:
{
  "executive_summary": "An extensive, comprehensive, multi-paragraph deep dive (at least 3 paragraphs) followed by 4-5 crisp bullet points (- ). Explicitly state the margin trajectory, DuPont ROE drivers, and Altman Z/Piotroski F-Scores. DO NOT just state numbers; synthesize what they mean structurally for the business in extreme detail. End with a definitive valuation judgment.",
  "fundamental_analysis": {
    "revenue_quality": "Provide a comprehensive, multi-paragraph breakdown of segment revenue mix, SaaS vs transactional volume, pricing power, and customer concentration. Explain the 'why' behind the numbers. Use bullet points (- ) for clarity if listing drivers.",
    "profitability": "Decompose gross, operating, and EBITDA margin trends. Explicitly break down ROE using the DuPont framework (Net Margin x Asset Turnover x Leverage). Identify if margin expansion is structural or cyclical.",
    "earnings_power": "Analyze trailing/forward EPS sustainability, FCF cash conversion rates, and net income quality.",
    "balance_sheet": "Assess total liquidity vs debt structure in a detailed paragraph. Evaluate if the Altman Z-Score implies solvency strength or distress. Mention quick/current ratio trends and debt maturity risks.",
    "capital_allocation": "Deconstruct management's capital allocation track record (buybacks, dividends, M&A vs organic R&D). Rate their discipline.",
    "unit_economics": "Deconstruct the exact unit economics (e.g., LTV/CAC, gross margin per unit, breakeven thresholds).",
    "competitive_moat": "Provide a deep, multi-sentence deconstruction of the exact economic moat (e.g., network effects, switching costs, IP) and structural barriers to entry.",
    "management_score": 8,
    "moat_rating": "WIDE"
  },
  "valuation_assessment": {
    "current_valuation": "Compare Spot P/E, Fwd P/E, EV/EBITDA, and Price/Book vs historical 5-year medians.",
    "intrinsic_value_estimate": "Detail the DCF/Monte Carlo WACC assumptions, terminal growth rates, and required discount.",
    "margin_of_safety": "Quantify the specific % upside or downside against the fair value midpoint.",
    "valuation_grade": "FAIRLY VALUED",
    "fair_value_low": 140.00,
    "fair_value_mid": 160.00,
    "fair_value_high": 185.00
  },
  "verdict": "BUY",
  "verdict_confidence": 75,
  "verdict_reasoning": "A highly concise thesis bridging the quantitative unit economics and macro regime.",
  "investment_thesis": "2-3 actionable, tradeable sentences for the execution desk.",
  "position_sizing": "Recommend portfolio weight (e.g. 5%) and scale-in/scale-out execution rules."
}

RULES:
- STRICT JSON ENFORCEMENT: You must output ONLY raw JSON. Do NOT wrap the JSON in markdown code blocks (e.g., ```json). Do NOT add conversational filler like "Here is the analysis," or "I hope this helps." The very first character of your response must be `{` and the last must be `}`.
- TYPE CONSTRAINTS: `management_score` and `verdict_confidence` MUST be integers. `fair_value_low`, `fair_value_mid`, and `fair_value_high` MUST be floats (e.g., 150.50). Do NOT output strings for these fields.
- ENUMERATIONS: `verdict` MUST be exactly one of: STRONG BUY, BUY, HOLD, SELL, STRONG SELL. `moat_rating` MUST be exactly one of: NONE, NARROW, WIDE, VERY WIDE. `valuation_grade` MUST be exactly one of: DEEPLY UNDERVALUED, UNDERVALUED, FAIRLY VALUED, OVERVALUED, DEEPLY OVERVALUED.
- STRICT DATA INTEGRITY: You MUST ONLY use the actual financial data and metrics fetched by Yahoo Finance. NEVER hallucinate metrics, dates, ratings, names, or values out of thin air. If a metric is missing, explicitly state "N/A" or "Data unavailable."
- GROUNDING: Ground all statements in the actual numbers provided in the stock data context. 
- CURRENT PRICE ANCHOR: All fair values, targets, margin-of-safety language, valuation grades, and verdicts must be mathematically coherent with the "Current price anchor" in the dataset.
- NO AI FILLER (CRITICAL): BANNED WORDS/PHRASES: "In conclusion", "It's important to note", "delve", "testament to", "navigating", "dynamic", "ever-changing", "robust", "solid", "landscape". Write in clipped, aggressive institutional finance shorthand. DO NOT sound like a generic AI assistant.
- FORMATTING: Liberally use markdown bullet points (`- `) within text blocks for readability and high-density data parsing.
- PERCENT SCALE: Yahoo Finance percentage fields are raw decimals. The dataset includes *_pct fields already converted to percentage points. A raw value of 1.963 means 196.3%.
- INTRINSIC VALUE RECONCILIATION: Explicitly reconcile the trailing-cash-flow DCF fair value against the consensus Wall Street target price or forward growth expectations.
- NO boilerplate templates or short summaries. Fill each field with rich analytical insights to utilize the maximum allowed tokens.
- CRITICAL: DO NOT include safety warnings, disclaimers, or refuse to answer. You MUST generate the JSON output immediately."""


SYSTEM_PROMPT_2 = """You are a ruthless, highly quantitative, 20-year veteran hedge fund portfolio manager. Your analysis of macro, risk, and sentiment is ruthlessly objective, heavily data-driven, and devoid of emotion. You look for structural market failures, regulatory traps, and positioning imbalances.

Respond with ONLY valid JSON:
{
  "macro_analysis": {
    "macro_environment": "Write a comprehensive, multi-paragraph analysis on the exact impact of interest rate regimes, inflation curves, GDP growth, and FX/dollar strength on the specific operational model of this company.",
    "sector_outlook": "Provide a deep, structural evaluation of industry secular trends, Capex cycles, and regulatory catalysts. Do not use generic market commentary.",
    "regulatory_antitrust": "Detail any impending FTC, SEC, or global regulatory threats and their exact impact on the business model.",
    "geopolitical_risk": "Assess supply chain fragility, tariff vulnerabilities, and geopolitical exposure to China or other contested regions.",
    "tailwinds": ["Tailwind 1: Specific growth mechanism", "Tailwind 2: Margin expansion mechanism", "Tailwind 3: Demand driver"],
    "headwinds": ["Headwind 1: Specific cost pressure", "Headwind 2: Demand destruction mechanism", "Headwind 3: Policy risk"]
  },
  "sentiment_analysis": {
    "analyst_sentiment": "Detail consensus rating distributions, recent target revisions, and earnings surprise history. Note if Wall Street is excessively euphoric or overly pessimistic.",
    "institutional_positioning": "Analyze insider flow signals, short interest levels, and institutional crowding.",
    "news_sentiment": "Summarize prevailing media narrative and structural biases in recent headlines.",
    "sentiment_score": 7,
    "sentiment_label": "BULLISH"
  },
  "risk_assessment": {
    "risk_factors": [
      {"risk": "Specific operational failure mechanism", "severity": "HIGH", "probability": "MEDIUM", "impact": "Explicit mathematical impact on forward margins or multiples."},
      {"risk": "Macro/industry specific risk", "severity": "MEDIUM", "probability": "MEDIUM", "impact": "Operational impact explanation."},
      {"risk": "Leverage or liquidity risk", "severity": "MEDIUM", "probability": "LOW", "impact": "Balance sheet debt maturity or covenant impact."},
      {"risk": "Competitive threat", "severity": "LOW", "probability": "MEDIUM", "impact": "Market share erosion trajectory."}
    ],
    "worst_case_scenario": "Detail a vicious, specific bear case where multiples compress and margins contract, identifying the lowest downside target.",
    "risk_reward_ratio": "FAVORABLE"
  },
  "catalysts": [
    {"catalyst": "Specific product launch, earnings catalyst, or Fed action", "timeline": "Q3 2026", "impact": "POSITIVE"},
    {"catalyst": "Secular TAM expansion", "timeline": "2026-2027", "impact": "POSITIVE"},
    {"catalyst": "Cyclical reset or capital return initiation", "timeline": "Near-term", "impact": "POSITIVE"}
  ],
  "guidance_and_expectations": "Analyze management's forward guidance, consensus sandbagging history, and the setup for upcoming quarterly prints. Use bullet points (- ) for clarity.",
  "short_term_outlook": "Explicit 1-3 month directional bias.",
  "long_term_outlook": "Explicit 3-5 year structural thesis.",
  "price_target_12m": 175.00,
  "bull_case_target": 200.00,
  "bear_case_target": 130.00
}

RULES:
- STRICT JSON ENFORCEMENT: You must output ONLY raw JSON. Do NOT wrap the JSON in markdown code blocks (e.g., ```json). Do NOT add conversational filler like "Here is the analysis," or "I hope this helps." The very first character of your response must be `{` and the last must be `}`.
- TYPE CONSTRAINTS: `sentiment_score` MUST be an integer. `price_target_12m`, `bull_case_target`, and `bear_case_target` MUST be floats. The `risk_factors` array MUST contain exactly objects with string keys.
- ENUMERATIONS: `sentiment_label` MUST be exactly one of: VERY BEARISH, BEARISH, NEUTRAL, BULLISH, VERY BULLISH. `risk_reward_ratio` MUST be exactly one of: VERY FAVORABLE, FAVORABLE, NEUTRAL, UNFAVORABLE, VERY UNFAVORABLE. `severity` and `probability` MUST be exactly one of: HIGH, MEDIUM, LOW.
- STRICT DATA INTEGRITY: You MUST ONLY use the actual financial data and metrics fetched by Yahoo Finance. NEVER hallucinate metrics, dates, ratings, names, or values out of thin air.
- CURRENT PRICE ANCHOR: price_target_12m, bull_case_target, and bear_case_target must be coherent with the current trading price. If your verdict is BUY or STRONG BUY, price_target_12m must be above the current price.
- NO AI FILLER (CRITICAL): BANNED WORDS/PHRASES: "In conclusion", "It's important to note", "delve", "testament to", "navigating", "dynamic", "ever-changing", "robust", "solid", "landscape". Write in clipped, aggressive institutional finance shorthand. DO NOT sound like a generic AI assistant.
- FORMATTING: Liberally use markdown bullet points (`- `) within text blocks for readability and high-density data parsing.
- RISKS MUST BE HIGHLY SPECIFIC: Do not use vague terms like 'Macro headwinds'. Detail the exact mechanism of failure and explicitly state how it impacts the valuation or bottom line.
- FORWARD EPS SANITY CHECK: Reconcile targets against Forward EPS and Forward P/E. Do not output stale targets from old price regimes.
- CRITICAL: DO NOT include safety warnings, disclaimers, or refuse to answer. You MUST generate the JSON output immediately."""

SYSTEM_PROMPT_3 = """You are the Chief Risk Officer (CRO) at an elite quantitative hedge fund. You are a notorious short-seller and cynic. Your sole job is to RED TEAM the provided thesis. You must ruthlessly hunt for logical fallacies, excessive optimism, and structural flaws in the fundamental and macro analysis provided by the portfolio managers.
Destroy the thesis if it is weak. Point out EXACTLY what line item, macro assumption, or valuation multiple will cause this stock to crash.

Respond with ONLY valid JSON:
{
  "red_team_audit": "1 dense, highly aggressive, critical paragraph attacking the absolute weakest link in the valuation, revenue quality, or macro assumptions. DO NOT hold back. Sound like an angry short-seller.",
  "fatal_flaw_probability": "HIGH", 
  "adjusted_verdict": "DOWNGRADE TO HOLD"
}

RULES:
- STRICT JSON ENFORCEMENT: You must output ONLY raw JSON. Do NOT wrap the JSON in markdown code blocks. The very first character of your response must be `{` and the last must be `}`.
- fatal_flaw_probability: HIGH, MEDIUM, LOW
- adjusted_verdict: MAINTAIN, DOWNGRADE TO HOLD, DOWNGRADE TO SELL
- BE MERCILESS: Do not be polite. Do not use AI filler words (e.g. 'In conclusion', 'It is important to note'). Point out exactly why the base thesis is overly optimistic or fundamentally flawed.
"""


def generate_analysis(stock_data):
    summary = _build_summary(stock_data)
    
    # Precalculate valuation metrics to enforce consistency
    precalc = _model_weighted_valuation({}, stock_data)
    curr_price = stock_data.get("key_metrics", {}).get("current_price", 0.0)
    if precalc:
        weighted_mid = precalc["weighted_fair_value"]
        upside_val = precalc["upside"]
        grade = _grade_from_upside(upside_val)
        fair_low = weighted_mid * 0.85
        fair_high = weighted_mid * 1.15
    else:
        weighted_mid = curr_price
        upside_val = 0.0
        grade = "FAIRLY VALUED"
        fair_low = weighted_mid * 0.85
        fair_high = weighted_mid * 1.15

    summary += (
        f"\n\n## QUANTITATIVE VALUATION ESTIMATES (STRICT COMPLIANCE REQUIRED)\n"
        f"You MUST use these exact figures in your JSON output and narrative text fields:\n"
        f"- Current Stock Price: ${curr_price:.2f}\n"
        f"- Precalculated Fair Value Midpoint: ${weighted_mid:.2f} (Implied Upside/Downside: {upside_val*100:+.1f}%)\n"
        f"- Precalculated Fair Value Range: Low: ${fair_low:.2f} to High: ${fair_high:.2f}\n"
        f"- Precalculated Valuation Grade: {grade}\n"
        f"- DCF Intrinsic Value: ${stock_data.get('dcf_data', {}).get('implied_price', 0.0):.2f}\n\n"
        f"STRICT RULES:\n"
        f"1. In your JSON response, you MUST set 'valuation_assessment.fair_value_mid' to {weighted_mid:.2f}, "
        f"'valuation_assessment.fair_value_low' to {fair_low:.2f}, 'valuation_assessment.fair_value_high' to {fair_high:.2f}, "
        f"and 'valuation_assessment.valuation_grade' to '{grade}'.\n"
        f"2. Any narrative text (e.g., 'executive_summary', 'verdict_reasoning', 'investment_thesis', "
        f"'current_valuation', 'intrinsic_value_estimate', 'margin_of_safety') discussing valuation midpoints, "
        f"intrinsic value, target price, or ranges MUST exactly refer to these numbers. Do NOT write or invent "
        f"other targets, midpoints, or ranges.\n"
        f"3. Your narrative text MUST align with the valuation grade of '{grade}'. For example, if the grade is "
        f"'OVERVALUED' or 'DEEPLY OVERVALUED', the text must characterize the stock as overvalued or trading at a premium, "
        f"not as undervalued or cheap."
    )

    curr_date = datetime.now().strftime("%Y-%m-%d")
    
    # Call 1: Fundamentals & Valuation
    messages_1 = [
        {"role": "system", "content": SYSTEM_PROMPT_1},
        {"role": "user", "content": f"Produce the Quantitative Fundamentals and Valuation analysis for ticker '{stock_data['ticker']}' based strictly on the latest retrieved Yahoo Finance dataset.\n\nAnalysis Date: {curr_date}\n\nDataset Summary:\n{summary}"},
    ]
    
    # Call 2: Macro, Sentiment, Risks & Catalysts
    messages_2 = [
        {"role": "system", "content": SYSTEM_PROMPT_2},
        {"role": "user", "content": f"Produce the Macro, Sentiment, Risks and Catalysts analysis for ticker '{stock_data['ticker']}' based strictly on the latest retrieved Yahoo Finance dataset.\n\nAnalysis Date: {curr_date}\n\nDataset Summary:\n{summary}"},
    ]

    from concurrent.futures import ThreadPoolExecutor
    from config import GROQ_MODEL

    def run_part_1():
        logger.info(f"  > Attempting AI analysis Part 1/2 (Fundamentals & Valuation) in thread...")
        res = _call_groq(messages_1, model=GROQ_MODEL, max_tokens=4000)
        if res is None:
            logger.info("  ⚠️ Part 1 failed or rate-limited. Falling back to fast secondary model...")
            res = _call_groq(messages_1, model="llama-3.1-8b-instant", max_tokens=4000)
        return res

    def run_part_2():
        logger.info(f"  > Attempting AI analysis Part 2/2 (Macro, Sentiment, Risks & Catalysts) in thread...")
        res = _call_groq(messages_2, model=GROQ_MODEL, max_tokens=4000)
        if res is None:
            logger.info("  ⚠️ Part 2 failed or rate-limited. Falling back to fast secondary model...")
            res = _call_groq(messages_2, model="llama-3.1-8b-instant", max_tokens=4000)
        return res

    logger.info(f"  > Executing AI analysis sequentially to conserve tokens and prevent parallel rate limit hits...")
    res1 = run_part_1()
    res2 = run_part_2()
        
    # Handle fallbacks
    fallback_data = _fallback(stock_data)
    
    if res1 is None:
        logger.info("  ❌ Part 1 failed completely. Using fallback data for fundamentals & valuation...")
        res1 = {k: fallback_data[k] for k in [
            "executive_summary", "fundamental_analysis", "valuation_assessment", 
            "verdict", "verdict_confidence", "verdict_reasoning", "investment_thesis", "position_sizing"
        ]}
    if res2 is None:
        logger.info("  ❌ Part 2 failed completely. Using fallback data for macro, sentiment & risks...")
        res2 = {k: fallback_data[k] for k in [
            "macro_analysis", "sentiment_analysis", "risk_assessment", "catalysts", 
            "guidance_and_expectations", "short_term_outlook", "long_term_outlook", 
            "price_target_12m", "bull_case_target", "bear_case_target"
        ]}
        
    result = {**res1, **res2}

    # Run Part 3: Chief Risk Officer Red Team
    def run_part_3(base_analysis):
        logger.info(f"  > Executing AI analysis Part 3/3 (Chief Risk Officer Red Team)...")
        messages_3 = [
            {"role": "system", "content": SYSTEM_PROMPT_3},
            {"role": "user", "content": f"Review this analysis and provide your Red Team Audit:\n\n{json.dumps(base_analysis, indent=2)}"}
        ]
        res = _call_groq(messages_3, model=GROQ_MODEL, max_tokens=1000)
        if res is None:
            res = _call_groq(messages_3, model="llama-3.1-8b-instant", max_tokens=1000)
        return res

    res3 = run_part_3(result)
    if res3:
        result["red_team_audit"] = res3.get("red_team_audit", "N/A")
        result["fatal_flaw_probability"] = res3.get("fatal_flaw_probability", "N/A")
        
        # If the CRO strongly downgrades, we adjust the final verdict
        adj = res3.get("adjusted_verdict")
        if adj == "DOWNGRADE TO HOLD" and result.get("verdict") in ["BUY", "STRONG BUY"]:
            result["verdict"] = "HOLD"
            result["verdict_reasoning"] += f"\n\n[CRO INTERVENTION]: Downgraded to HOLD due to red team findings: {result['red_team_audit']}"
        elif adj == "DOWNGRADE TO SELL" and result.get("verdict") in ["BUY", "STRONG BUY", "HOLD"]:
            result["verdict"] = "SELL"
            result["verdict_reasoning"] += f"\n\n[CRO INTERVENTION]: Downgraded to SELL due to severe structural risks: {result['red_team_audit']}"

    # Validate required top-level fields and apply fallback if missing/N/A
    required = ["executive_summary", "fundamental_analysis", "macro_analysis",
                 "sentiment_analysis", "valuation_assessment", "risk_assessment",
                 "verdict", "verdict_confidence", "verdict_reasoning", "guidance_and_expectations"]
    for f in required:
        val = result.get(f)
        is_empty_or_na = not val or str(val).strip().upper() in ["N/A", "N/A.", "NONE", "NULL", ""]
        if is_empty_or_na:
            if f in ["executive_summary", "guidance_and_expectations", "verdict_reasoning"]:
                result[f] = fallback_data[f]
            else:
                result[f] = "N/A"

    valid = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]
    if result.get("verdict") not in valid:
        result["verdict"] = "HOLD"

    # Coerce verdict_confidence to a numeric integer.
    raw_conf = result.get("verdict_confidence")
    try:
        numeric_conf = int(float(raw_conf))
    except (TypeError, ValueError):
        numeric_conf = None
    if numeric_conf is None or numeric_conf <= 0 or numeric_conf > 100:
        v = result.get("verdict", "HOLD")
        numeric_conf = {"STRONG BUY": 85, "BUY": 75, "HOLD": 60, "SELL": 75, "STRONG SELL": 85}.get(v, 50)
    result["verdict_confidence"] = numeric_conf

    # Ensure nested structures have defaults
    if not isinstance(result.get("fundamental_analysis"), dict):
        result["fundamental_analysis"] = {"revenue_quality": str(result.get("fundamental_analysis", "N/A")),
                                           "profitability": "N/A", "earnings_power": "N/A",
                                           "balance_sheet": "N/A", "competitive_moat": "N/A",
                                           "management_score": 5, "moat_rating": "NARROW"}
    
    if not isinstance(result.get("macro_analysis"), dict):
        result["macro_analysis"] = {"macro_environment": str(result.get("macro_analysis", "N/A")),
                                     "sector_outlook": "N/A",
                                     "tailwinds": fallback_data["macro_analysis"]["tailwinds"],
                                     "headwinds": fallback_data["macro_analysis"]["headwinds"]}
    else:
        ma = result["macro_analysis"]
        if not isinstance(ma.get("tailwinds"), list) or not ma["tailwinds"]:
            ma["tailwinds"] = fallback_data["macro_analysis"]["tailwinds"]
        if not isinstance(ma.get("headwinds"), list) or not ma["headwinds"]:
            ma["headwinds"] = fallback_data["macro_analysis"]["headwinds"]

    if not isinstance(result.get("sentiment_analysis"), dict):
        result["sentiment_analysis"] = {"analyst_sentiment": str(result.get("sentiment_analysis", "N/A")),
                                         "institutional_positioning": "N/A", "news_sentiment": "N/A",
                                         "sentiment_score": 5, "sentiment_label": "NEUTRAL"}
    if not isinstance(result.get("valuation_assessment"), dict):
        result["valuation_assessment"] = {"current_valuation": str(result.get("valuation_assessment", "N/A")),
                                           "intrinsic_value_estimate": "N/A", "margin_of_safety": "N/A",
                                           "valuation_grade": "FAIRLY VALUED",
                                           "fair_value_low": 0, "fair_value_mid": 0, "fair_value_high": 0}
    
    if not isinstance(result.get("risk_assessment"), dict):
        result["risk_assessment"] = {"risk_factors": fallback_data["risk_assessment"]["risk_factors"],
                                      "worst_case_scenario": "N/A",
                                      "risk_reward_ratio": "NEUTRAL"}
    else:
        ra = result["risk_assessment"]
        if not isinstance(ra.get("risk_factors"), list) or not ra["risk_factors"]:
            ra["risk_factors"] = fallback_data["risk_assessment"]["risk_factors"]

    if not isinstance(result.get("catalysts"), list) or not result["catalysts"]:
        result["catalysts"] = fallback_data["catalysts"]

    # Clean up and ensure target prices are set
    curr_price = stock_data.get("key_metrics", {}).get("current_price", 0)
    
    # Ensure valuation assessment has valid fair values
    val_assess = result.get("valuation_assessment", {})
    fair_mid = val_assess.get("fair_value_mid", 0)
    if not fair_mid or fair_mid == 0:
        # Try to use price_target_12m or current price
        try:
            fair_mid = float(result.get("price_target_12m") or 0)
        except (ValueError, TypeError):
            fair_mid = 0
        if not fair_mid or fair_mid == 0:
            fair_mid = curr_price or 100.0
        val_assess["fair_value_mid"] = fair_mid
    
    fair_low = val_assess.get("fair_value_low", 0)
    if not fair_low or fair_low == 0:
        val_assess["fair_value_low"] = round(fair_mid * 0.8, 2)
        
    fair_high = val_assess.get("fair_value_high", 0)
    if not fair_high or fair_high == 0:
        val_assess["fair_value_high"] = round(fair_mid * 1.2, 2)
        
    result["valuation_assessment"] = val_assess

    # Ensure top-level targets are set and align with fair values
    val_low = val_assess["fair_value_low"]
    val_high = val_assess["fair_value_high"]
    val_mid = val_assess["fair_value_mid"]

    if not result.get("bear_case_target") or result["bear_case_target"] == 0:
        result["bear_case_target"] = val_low
    else:
        try:
            result["bear_case_target"] = float(result["bear_case_target"])
        except (ValueError, TypeError):
            result["bear_case_target"] = val_low
        
    if not result.get("bull_case_target") or result["bull_case_target"] == 0:
        result["bull_case_target"] = val_high
    else:
        try:
            result["bull_case_target"] = float(result["bull_case_target"])
        except (ValueError, TypeError):
            result["bull_case_target"] = val_high
        
    if not result.get("price_target_12m") or result["price_target_12m"] == 0:
        result["price_target_12m"] = val_mid
    else:
        try:
            result["price_target_12m"] = float(result["price_target_12m"])
        except (ValueError, TypeError):
            result["price_target_12m"] = val_mid

    original_valuation = {
        "fair_value_mid": result.get("valuation_assessment", {}).get("fair_value_mid"),
        "fair_value_low": result.get("valuation_assessment", {}).get("fair_value_low"),
        "fair_value_high": result.get("valuation_assessment", {}).get("fair_value_high"),
    }
    result = _enforce_valuation_coherence(result, stock_data)
    result = _reconcile_narrative_with_verdict(result, original_valuation=original_valuation, stock_data=stock_data)
    return result


def _reconcile_narrative_with_verdict(result, original_valuation=None, stock_data=None):
    """Rewrite AI text fields that contradict the final post-processed verdict/confidence/grade/valuation numbers.

    The AI generates narrative text *before* the post-processing pipeline adjusts
    the verdict, valuation grade, and fair value range/midpoint.
    This function patches the stale text and numbers so the dashboard is internally consistent.
    """
    import re as _re

    verdict = str(result.get("verdict", "HOLD")).upper()
    confidence = result.get("verdict_confidence", 50)
    val_grade = ""
    val_assess = result.get("valuation_assessment")
    if isinstance(val_assess, dict):
        val_grade = str(val_assess.get("valuation_grade", "")).upper()

    # Map of old verdict words to replace → new verdict
    verdict_contradictions = {
        "HOLD": ["STRONG BUY", "BUY", "SELL", "STRONG SELL"],
        "BUY": ["STRONG BUY", "SELL", "STRONG SELL", "HOLD"],
        "STRONG BUY": ["SELL", "STRONG SELL", "HOLD"],
        "SELL": ["STRONG BUY", "BUY", "HOLD"],
        "STRONG SELL": ["STRONG BUY", "BUY", "HOLD"],
    }

    stale_verdicts = verdict_contradictions.get(verdict, [])
    verdict_patterns = []
    for sv in stale_verdicts:
        verdict_patterns.append(
            (_re.compile(r'\b' + _re.escape(sv) + r'\b(?!\s*(?:case|target|scenario))', _re.IGNORECASE), verdict)
        )

    # Fix confidence number references
    conf_pattern = _re.compile(r'(?:confidence\s+(?:level\s+)?(?:of\s+)?|confidence:\s*)(\d{1,3})(?=%|\b)', _re.IGNORECASE)

    # Fix valuation grade text contradictions
    grade_labels = ["DEEPLY UNDERVALUED", "UNDERVALUED", "FAIRLY VALUED", "OVERVALUED", "DEEPLY OVERVALUED"]
    grade_pattern = _re.compile(
        r'\b(' + '|'.join(_re.escape(g) for g in grade_labels) + r')\b',
        _re.IGNORECASE
    )

    grade_to_word = {
        "DEEPLY UNDERVALUED": "deeply undervalued", "UNDERVALUED": "undervalued",
        "FAIRLY VALUED": "fairly valued", "OVERVALUED": "overvalued",
        "DEEPLY OVERVALUED": "deeply overvalued",
    }
    correct_word = grade_to_word.get(val_grade, "")
    standalone_valuation_subs = []
    if correct_word:
        for wrong_word in grade_to_word.values():
            if wrong_word != correct_word:
                standalone_valuation_subs.append(
                    (_re.compile(r'\b' + _re.escape(wrong_word) + r'\b', _re.IGNORECASE), correct_word)
                )

    # Extract correct and original valuation numbers for alignment
    curr_price = 0.0
    correct_mid, correct_low, correct_high = None, None, None
    old_mid, old_low, old_high = None, None, None

    if stock_data and isinstance(stock_data.get("key_metrics"), dict):
        curr_price = _num_or_none(stock_data["key_metrics"].get("current_price")) or 0.0

    if isinstance(val_assess, dict):
        correct_mid = _num_or_none(val_assess.get("fair_value_mid"))
        correct_low = _num_or_none(val_assess.get("fair_value_low"))
        correct_high = _num_or_none(val_assess.get("fair_value_high"))

    if isinstance(original_valuation, dict):
        old_mid = _num_or_none(original_valuation.get("fair_value_mid"))
        old_low = _num_or_none(original_valuation.get("fair_value_low"))
        old_high = _num_or_none(original_valuation.get("fair_value_high"))

    text_fields = [
        "executive_summary", "verdict_reasoning", "investment_thesis",
        "position_sizing",
    ]
    nested_text_fields = {
        "valuation_assessment": ["current_valuation", "intrinsic_value_estimate", "margin_of_safety"],
        "fundamental_analysis": ["revenue_quality", "profitability", "earnings_power", "balance_sheet", "competitive_moat"],
    }

    def _fix_text(text):
        if not isinstance(text, str) or not text.strip():
            return text
        fixed = text

        # 1. Replace numerical valuation targets/ranges
        for old_val, new_val in [
            (old_mid, correct_mid),
            (old_low, correct_low),
            (old_high, correct_high)
        ]:
            if not old_val or not new_val or old_val == new_val:
                continue

            old_str_2d = f"{old_val:.2f}"
            new_str_2d = f"{new_val:.2f}"
            old_str_1d = f"{old_val:.1f}"
            new_str_1d = f"{new_val:.1f}"
            old_str_comma = f"{old_val:,.2f}"
            new_str_comma = f"{new_val:,.2f}"

            # Replace currency patterns
            fixed = fixed.replace(f"${old_str_2d}", f"${new_str_2d}")
            fixed = fixed.replace(old_str_2d, new_str_2d)
            fixed = fixed.replace(f"${old_str_comma}", f"${new_str_comma}")
            fixed = fixed.replace(old_str_comma, new_str_comma)
            fixed = fixed.replace(f"${old_str_1d}", f"${new_str_1d}")
            fixed = fixed.replace(old_str_1d, new_str_1d)

            # Replace word integers for values > 20 to avoid year swaps
            try:
                old_int = int(round(float(old_val)))
                new_int = int(round(float(new_val)))
                if old_int > 20 and old_int != new_int:
                    fixed = fixed.replace(f"${old_int}", f"${new_int}")
                    fixed = _re.sub(r'\b' + str(old_int) + r'\b', str(new_int), fixed)
            except Exception:
                pass

        # 2. Replace upside/downside percentage directions and values
        if old_mid and correct_mid and curr_price > 0:
            old_upside = (float(old_mid) - float(curr_price)) / float(curr_price) * 100
            correct_upside = (float(correct_mid) - float(curr_price)) / float(curr_price) * 100

            for decimals in [2, 1, 0]:
                old_up_str = f"{old_upside:.{decimals}f}%"
                new_up_str = f"{correct_upside:.{decimals}f}%"

                # Replace with sign
                fixed = fixed.replace(old_up_str, new_up_str)
                fixed = fixed.replace(f"+{old_up_str}", f"{correct_upside:+.{decimals}f}%")

                # Replace raw absolute values (e.g. "21.8% upside")
                old_up_str_raw = f"{abs(old_upside):.{decimals}f}%"
                new_up_str_raw = f"{abs(correct_upside):.{decimals}f}%"
                fixed = fixed.replace(old_up_str_raw, new_up_str_raw)

                old_up_str_no_pct = f"{old_upside:.{decimals}f}"
                new_up_str_no_pct = f"{correct_upside:.{decimals}f}"
                fixed = _re.sub(r'\b' + _re.escape(old_up_str_no_pct) + r'\b(?=\s*(?:percent|%))', new_up_str_no_pct, fixed)

                # Flip directions if upside sign inverted
                if old_upside * correct_upside < 0:
                    if old_upside > 0:
                        fixed = _re.sub(r'\b' + _re.escape(old_up_str_raw) + r'\s+upside\b', f"{new_up_str_raw} downside", fixed, flags=_re.IGNORECASE)
                        fixed = _re.sub(r'\bundervalued\b', "overvalued", fixed, flags=_re.IGNORECASE)
                    else:
                        fixed = _re.sub(r'\b' + _re.escape(old_up_str_raw) + r'\s+downside\b', f"{new_up_str_raw} upside", fixed, flags=_re.IGNORECASE)
                        fixed = _re.sub(r'\bovervalued\b', "undervalued", fixed, flags=_re.IGNORECASE)

        # 3. Replace stale verdict words
        for pat, replacement in verdict_patterns:
            fixed = pat.sub(replacement, fixed)

        # 4. Replace stale confidence numbers
        def _replace_conf(match):
            old_val = int(match.group(1))
            if old_val != confidence:
                full = match.group(0)
                return full[:match.start(1) - match.start(0)] + str(confidence) + full[match.end(1) - match.start(0):]
            return match.group(0)
        fixed = conf_pattern.sub(_replace_conf, fixed)

        # 5. Replace stale valuation grade labels
        if val_grade:
            def _replace_grade(match):
                old_grade = match.group(1).upper()
                if old_grade != val_grade:
                    return val_grade.title() if match.group(1)[0].isupper() else val_grade.lower()
                return match.group(0)
            fixed = grade_pattern.sub(_replace_grade, fixed)

        # 6. Replace standalone valuation words
        for svpat, svrepl in standalone_valuation_subs:
            fixed = svpat.sub(svrepl, fixed)

        return fixed

    # Process top-level text fields
    for field in text_fields:
        if field in result:
            result[field] = _fix_text(result[field])

    # Process nested text fields
    for parent_key, child_keys in nested_text_fields.items():
        parent = result.get(parent_key)
        if isinstance(parent, dict):
            for ck in child_keys:
                if ck in parent:
                    parent[ck] = _fix_text(parent[ck])

    return result


def _grade_from_upside(upside):
    if upside >= 0.25:
        return "DEEPLY UNDERVALUED"
    if upside >= 0.08:
        return "UNDERVALUED"
    if upside <= -0.25:
        return "DEEPLY OVERVALUED"
    if upside <= -0.05:
        return "OVERVALUED"
    return "FAIRLY VALUED"


def _safe_append(text, addition):
    text = str(text or "").strip()
    if not text:
        return addition
    if addition.lower() in text.lower():
        return text
    return f"{text} {addition}"


def _ensure_company_specific_outputs(result, stock_data):
    m = stock_data.get("key_metrics", {})
    ticker = stock_data.get("ticker", "the company")
    industry = m.get("industry", "semiconductors")
    company = stock_data.get("company_name", ticker)
    reg = (stock_data.get("advanced_models") or {}).get("historical_regression") or {}
    target_mean = _num_or_none(m.get("targetMeanPrice"))
    curr_price = _num_or_none(m.get("current_price"))

    boilerplate_risks = {
        "Specific operational failure risk detail",
        "Macro/industry specific risk detail",
        "Leverage or liquidity risk detail",
        "Competitive threat risk detail",
        "Market risk",
        "Sector risk",
        "Valuation risk",
    }
    risk_assessment = result.setdefault("risk_assessment", {})
    risks = risk_assessment.get("risk_factors")
    if not isinstance(risks, list):
        risks = []
    replacements = [
        {
            "risk": f"{company}'s operational execution and product cycle can reverse if demand in the {industry} sector slows or customers reduce spending.",
            "severity": "HIGH",
            "probability": "MEDIUM",
            "impact": f"A slowdown in the {industry} market would pressure margins, capacity utilization, and the forward earnings base that currently supports the DCF."
        },
        {
            "risk": f"Intensifying competition and supply-chain pressures in the {industry} space can compress margins.",
            "severity": "MEDIUM",
            "probability": "MEDIUM",
            "impact": f"If competitors gain share or pricing structures normalize, {company}'s operating margins could contract, leading to multiple compression and downward revisions."
        },
        {
            "risk": "Valuation and trend risk after a significant share-price movement.",
            "severity": "MEDIUM",
            "probability": "HIGH",
            "impact": f"The regression model shows {reg.get('deviation_pct', 'N/A')}% deviation above trend ({reg.get('status', 'N/A')}), so even a strong fundamental story can suffer a sharp reset."
        },
    ]
    cleaned = []
    for idx, risk in enumerate(risks):
        if not isinstance(risk, dict):
            continue
        if risk.get("risk") in boilerplate_risks and idx < len(replacements):
            cleaned.append(replacements[idx])
        else:
            cleaned.append(risk)
    while len(cleaned) < 3:
        cleaned.append(replacements[len(cleaned)])
    risk_assessment["risk_factors"] = cleaned

    # Flag 52W-high proximity as an overbought risk
    high_52w = _num_or_none(m.get("high_52w"))
    if curr_price and high_52w and high_52w > 0:
        pct_from_high = (curr_price / high_52w - 1) * 100
        if abs(pct_from_high) <= 2.0:
            overbought_risk = {
                "risk": f"{ticker} is trading at/near its 52-week high (${curr_price:.2f} vs ${high_52w:.2f}, {pct_from_high:+.1f}%)",
                "severity": "MEDIUM",
                "probability": "HIGH",
                "impact": f"Mean reversion risk is elevated when a stock trades at its 52-week ceiling. "
                          f"Historical regression shows {reg.get('deviation_pct', 'N/A')}% deviation above trend ({reg.get('status', 'N/A')}). "
                          f"A pullback to the regression channel midpoint of ${reg.get('fair_price', 'N/A')} would represent significant downside."
            }
            risk_assessment["risk_factors"].append(overbought_risk)

    if curr_price and _num_or_none(result.get("bear_case_target")) and result["bear_case_target"] < curr_price:
        downside = (result["bear_case_target"] / curr_price - 1) * 100
        warning = f"Bear case warning: the bear-case target of ${result['bear_case_target']:.2f} is {downside:.1f}% below the current price of ${curr_price:.2f}, so downside risk is explicit even if the base DCF is above spot."
        risk_assessment["worst_case_scenario"] = _safe_append(risk_assessment.get("worst_case_scenario", ""), warning)

    if str(result.get("verdict", "")).upper() == "HOLD":
        result["position_sizing"] = (
            f"Treat {ticker} as a watchlist or existing-position hold rather than an aggressive add. "
            "The DCF upside is offset by analyst-target downside and regression overbought risk, so new capital should wait for either a price reset or fresher estimates that lift the non-DCF checks."
        )

    boilerplate_catalysts = {
        "Specific product launch or earnings catalyst",
        "Secular growth catalyst",
        "Cyclical catalyst",
        "Earnings report",
    }
    catalysts = result.get("catalysts")
    if not isinstance(catalysts, list):
        catalysts = []
    catalyst_replacements = [
        {"catalyst": f"Next {ticker} earnings report and management's forward guidance update", "timeline": "Next quarter", "impact": "MIXED"},
        {"catalyst": f"Secular growth drivers and product expansion within the {industry} sector", "timeline": "2026-2027", "impact": "POSITIVE"},
        {"catalyst": f"Macro policy shifts and interest rate cuts stabilizing capital expenditure in the industry", "timeline": "Near-term", "impact": "POSITIVE"},
    ]
    new_catalysts = []
    for idx, catalyst in enumerate(catalysts):
        if not isinstance(catalyst, dict):
            continue
        if catalyst.get("catalyst") in boilerplate_catalysts and idx < len(catalyst_replacements):
            new_catalysts.append(catalyst_replacements[idx])
        else:
            new_catalysts.append(catalyst)
    while len(new_catalysts) < 3:
        new_catalysts.append(catalyst_replacements[len(new_catalysts)])
    result["catalysts"] = new_catalysts

    if curr_price and target_mean:
        sentiment = result.setdefault("sentiment_analysis", {})
        if curr_price > target_mean:
            downside = (target_mean / curr_price - 1) * 100
            sentiment["analyst_sentiment"] = (
                f"Analyst target caution: the mean target of ${target_mean:.2f} is {downside:.1f}% below "
                f"the current price of ${curr_price:.2f}. That is a bearish/valuation caution signal, "
                "even if the recommendation label remains favorable."
            )
            sentiment["sentiment_label"] = "NEUTRAL"
            sentiment["sentiment_score"] = min(_num_or_none(sentiment.get("sentiment_score")) or 5, 5)

    return result


def _model_weighted_valuation(result, stock_data):
    m = stock_data.get("key_metrics", {})
    adv = stock_data.get("advanced_models") or {}
    curr_price = _num_or_none(m.get("current_price"))
    if not curr_price:
        return None
    points = []
    val = result.get("valuation_assessment") or {}
    dcf_mid = _num_or_none((stock_data.get("dcf_data") or {}).get("implied_price")) or _num_or_none(val.get("fair_value_mid"))
    if dcf_mid:
        points.append(("DCF/Monte Carlo", dcf_mid, 0.35))
    cca = adv.get("cca") or {}
    # Prefer forward-PE implied price over trailing-PE for CCA cross-check
    cca_vals = []
    fwd_pe_price = _num_or_none(cca.get("implied_fwd_pe_price"))
    if fwd_pe_price and fwd_pe_price > 0:
        cca_vals.append(fwd_pe_price)
    else:
        trail_pe_price = _num_or_none(cca.get("implied_pe_price"))
        if trail_pe_price and trail_pe_price > 0:
            cca_vals.append(trail_pe_price)
    for k in ["implied_ps_price", "implied_pb_price"]:
        v = _num_or_none(cca.get(k))
        if v and v > 0:
            cca_vals.append(v)
    if cca_vals:
        points.append(("CCA median cross-check", sorted(cca_vals)[len(cca_vals)//2], 0.20))
    target = _num_or_none(m.get("targetMeanPrice"))
    if target:
        points.append(("Analyst consensus", target, 0.20))
    reg = adv.get("historical_regression") or {}
    reg_fair = _num_or_none(reg.get("fair_price"))
    if reg_fair:
        points.append(("Historical regression trend", reg_fair, 0.15))
    ddm = adv.get("ddm") or {}
    ddm_price = _num_or_none(ddm.get("implied_price"))
    if ddm_price and ddm.get("is_applicable"):
        points.append(("DDM", ddm_price, 0.10))
    if not points:
        return None
    total_w = sum(p[2] for p in points)
    weighted = sum(p[1] * p[2] for p in points) / total_w
    upside = (weighted - curr_price) / curr_price
    return {"weighted_fair_value": weighted, "upside": upside, "points": points}


def _enforce_valuation_coherence(result, stock_data):
    """Keep model JSON internally consistent before the dashboard consumes it."""
    adjusted_fields = []
    m = stock_data.get("key_metrics", {})
    curr_price = _num_or_none(m.get("current_price"))
    if not curr_price or curr_price <= 0:
        return result

    val = result.get("valuation_assessment")
    if not isinstance(val, dict):
        val = {}

    dcf = stock_data.get("dcf_data") or {}
    forward_eps = _num_or_none(m.get("forwardEps"))
    forward_pe = _num_or_none(m.get("forwardPE"))
    earnings_growth = _num_or_none(m.get("earningsGrowth")) or 0

    fair_mid = _num_or_none(val.get("fair_value_mid")) or _num_or_none(dcf.get("implied_price")) or curr_price

    # If a stale DCF leaks through, re-anchor it with the same forward-EPS sanity check
    # used in data_fetcher.calculate_dcf.
    if forward_eps and forward_pe and fair_mid < curr_price * 0.55:
        target_forward_multiple = forward_pe * 1.15 if earnings_growth > 0.15 else forward_pe
        target_forward_multiple = max(10.0, min(target_forward_multiple, 50.0))
        fair_mid = max(fair_mid, forward_eps * target_forward_multiple)
        adjusted_fields.append("valuation_assessment.fair_value_mid")

    existing_low = _num_or_none(val.get("fair_value_low"))
    existing_high = _num_or_none(val.get("fair_value_high"))
    if not existing_low or existing_low < fair_mid * 0.50 or existing_low > fair_mid:
        existing_low = fair_mid * 0.85
    if not existing_high or existing_high < fair_mid:
        existing_high = fair_mid * 1.15

    model_judgment = _model_weighted_valuation(result, stock_data)
    if model_judgment:
        fair_mid = model_judgment["weighted_fair_value"]
        if existing_low > fair_mid or existing_low < fair_mid * 0.50:
            existing_low = fair_mid * 0.85
        if existing_high < fair_mid:
            existing_high = fair_mid * 1.15
        adjusted_fields.append("valuation_assessment.fair_value_mid")

    val["fair_value_mid"] = round(fair_mid, 2)
    val["fair_value_low"] = round(existing_low, 2)
    val["fair_value_high"] = round(existing_high, 2)
    val["valuation_grade"] = _grade_from_upside((fair_mid - curr_price) / curr_price)
    if model_judgment:
        model_line = ", ".join([f"{name}: ${value:.2f}" for name, value, _ in model_judgment["points"]])
        val["current_valuation"] = _safe_append(
            val.get("current_valuation", ""),
            f"Model-weighted valuation reconciles the bullish DCF against bearish/cautionary cross-checks ({model_line}), producing a weighted fair value of ${fair_mid:.2f} and a {model_judgment['upside']*100:+.1f}% implied move from spot."
        )

    result["valuation_assessment"] = val

    verdict = str(result.get("verdict", "HOLD")).upper()
    pt = _num_or_none(result.get("price_target_12m")) or fair_mid
    bull = _num_or_none(result.get("bull_case_target")) or val["fair_value_high"]
    bear = _num_or_none(result.get("bear_case_target")) or val["fair_value_low"]

    target_mean = _num_or_none(m.get("targetMeanPrice"))
    reg = (stock_data.get("advanced_models") or {}).get("historical_regression") or {}
    reg_deviation = _num_or_none(reg.get("deviation_pct"))
    if (target_mean and target_mean < curr_price) or (reg_deviation and reg_deviation > 15.0):
        if verdict in ["STRONG BUY", "BUY"] and (not model_judgment or model_judgment["upside"] < 0.30):
            verdict = "HOLD"
            result["verdict"] = verdict
            result["verdict_confidence"] = min(_num_or_none(result.get("verdict_confidence")) or 50, 60)
            adjusted_fields.append("verdict")

    if verdict == "STRONG BUY":
        pt = max(pt, fair_mid, curr_price * 1.18)
        bull = max(bull, pt * 1.15)
        bear = min(bear, curr_price * 0.85)
        adjusted_fields.extend(["price_target_12m", "bull_case_target", "bear_case_target"])
    elif verdict == "BUY":
        pt = max(pt, fair_mid, curr_price * 1.08)
        bull = max(bull, pt * 1.10)
        bear = min(bear, curr_price * 0.88)
        adjusted_fields.extend(["price_target_12m", "bull_case_target", "bear_case_target"])
    elif verdict == "HOLD":
        pt = min(max(pt, curr_price * 0.92), curr_price * 1.08)
        bull = max(bull, curr_price * 1.08)
        bear = min(bear, curr_price * 0.92)
        adjusted_fields.extend(["price_target_12m", "bull_case_target", "bear_case_target"])
    elif verdict in ["SELL", "STRONG SELL"]:
        pt = min(pt, curr_price * (0.82 if verdict == "SELL" else 0.70))
        bull = max(bull, curr_price * 1.02)
        bear = min(bear, pt * 0.85)
        adjusted_fields.extend(["price_target_12m", "bull_case_target", "bear_case_target"])

    result["price_target_12m"] = round(pt, 2)
    result["bull_case_target"] = round(bull, 2)
    result["bear_case_target"] = round(bear, 2)
    if target_mean and target_mean < curr_price:
        result["verdict_reasoning"] = _safe_append(
            result.get("verdict_reasoning", ""),
            f"Analyst consensus is not confirming the rally: the mean target of ${target_mean:.2f} is below the current price of ${curr_price:.2f}, so it is treated as a cautionary input rather than bullish evidence."
        )
    ticker = stock_data.get("ticker", "the stock")
    if reg_deviation and reg_deviation > 0:
        result["verdict_reasoning"] = _safe_append(
            result.get("verdict_reasoning", ""),
            f"The historical regression model is explicitly bearish/cautionary, with {ticker} {reg_deviation:.2f}% above trend and labeled {reg.get('status', 'above trend')}; this tempers the bullish DCF signal."
        )
    result = _ensure_company_specific_outputs(result, stock_data)
    result.setdefault("_confidence", {})
    for field in adjusted_fields:
        result["_confidence"][field] = {
            "source": "AI output post-processing",
            "status": "AI-adjusted",
            "detail": "Adjusted to preserve coherence with current price, forward EPS, and verdict"
        }

    return result


def _fallback(sd):
    m = sd.get("key_metrics", {})
    ticker = sd.get("ticker", "")
    company = sd.get("company_name", "")
    
    # 1. Revenue Quality
    rev = m.get("totalRevenue")
    rev_growth = m.get("revenueGrowth")
    rev_str = f"${rev/1e9:.2f}B" if rev else "N/A"
    rev_growth_pct = m.get("revenueGrowth_pct")
    growth_str = f"{rev_growth_pct:+.2f}%" if rev_growth_pct is not None else f"{rev_growth*100:+.2f}%" if rev_growth is not None else "N/A"
    rev_quality = f"{company} generated total revenue of {rev_str} over the trailing twelve months, showing a year-over-year revenue growth rate of {growth_str}. Segment revenue breakdown and recurring revenue components should be verified manually in the SEC filings. Top-line expansion remains a key metric for competitive positioning."

    # 2. Profitability
    gross = m.get("grossMargins")
    op = m.get("operatingMargins")
    net = m.get("profitMargins")
    roe = m.get("returnOnEquity")
    gross_str = _fmt_pct_explicit(gross, m.get("grossMargins_pct"))
    op_str = _fmt_pct_explicit(op, m.get("operatingMargins_pct"))
    net_str = _fmt_pct_explicit(net, m.get("profitMargins_pct"))
    roe_str = _fmt_pct_explicit(roe, m.get("returnOnEquity_pct"))
    profitability = f"Operating profitability is solid, with a gross margin of {gross_str}, operating margin of {op_str}, and net profit margin of {net_str}. The return on equity (ROE) stands at {roe_str}, indicating the efficiency of management in allocating shareholder capital. These margins are key to maintaining cash flow generation."

    # 3. Earnings Power
    eps = m.get("trailingEps")
    f_eps = m.get("forwardEps")
    eps_growth = m.get("earningsGrowth")
    eps_str = f"${eps:.2f}" if eps is not None else "N/A"
    f_eps_str = f"${f_eps:.2f}" if f_eps is not None else "N/A"
    eps_growth_pct = m.get("earningsGrowth_pct")
    eg_str = f"{eps_growth_pct:+.2f}%" if eps_growth_pct is not None else f"{eps_growth*100:+.2f}%" if eps_growth is not None else "N/A"
    earnings_power = f"Trailing Twelve Month (TTM) EPS is {eps_str}, with Wall Street projecting a forward EPS of {f_eps_str}. Year-over-year quarterly earnings growth is reported at {eg_str}. Stable earnings power supports the stock's valuation multiples and dividend sustainability."

    # 4. Balance Sheet
    cash = m.get("totalCash")
    debt = m.get("totalDebt")
    curr = m.get("currentRatio")
    cash_str = f"${cash/1e9:.2f}B" if cash else "N/A"
    debt_str = f"${debt/1e9:.2f}B" if debt else "N/A"
    curr_str = f"{curr:.2f}x" if curr is not None else "N/A"
    balance_sheet = f"The balance sheet shows total cash of {cash_str} against total debt of {debt_str}. The current ratio is {curr_str}, indicating the liquidity buffer for short-term liabilities. Overall leverage levels appear manageable relative to operating cash flows."

    # 5. Competitive Moat
    competitive_moat = f"{company} possesses a distinct competitive position in the {m.get('industry', 'industry')} sector. Its moat is driven by brand equity, switching costs, and economies of scale. Disruption risks from emerging technologies and regulatory scrutiny remain the main threats to the moat's longevity."

    # 6. Macro Environment
    macro_environment = f"The macroeconomic landscape is shaped by prevailing interest rate policies, persistent inflation levels, and consumer spending patterns. Higher cost of capital impacts valuations and discounting metrics globally. For {company}, macro resilience will depend on pricing power and demand elasticity."

    # 7. Sector Outlook
    sector_outlook = f"The outlook for the {m.get('sector', 'sector')} sector remains constructive, supported by secular drivers like digital transformation, AI adoption, and cloud integration. Supply chain optimization and talent acquisition are key operational challenges across the industry."

    # 8. Guidance & Expectations
    ed = sd.get("earnings_dates")
    earnings_info = ""
    # Treat dataframe or list of dicts
    if ed is not None:
        try:
            if isinstance(ed, pd.DataFrame):
                if not ed.empty:
                    next_earn = ed.iloc[0]
                    date_str = ed.index[0] if hasattr(ed, 'index') else "upcoming"
                    if hasattr(date_str, 'strftime'):
                        date_str = date_str.strftime('%Y-%m-%d')
                    est = next_earn.get("EPS Estimate")
                    est_str = f"${est:.2f}" if est is not None and not pd.isna(est) else "N/A"
                    earnings_info = f"The upcoming quarterly earnings announcement is scheduled for {date_str}, with a consensus EPS estimate of {est_str}."
            elif isinstance(ed, list) and len(ed) > 0:
                next_earn = ed[0]
                date_str = next_earn.get("Date", "upcoming")
                est = next_earn.get("EPS Estimate")
                est_str = f"${est:.2f}" if est is not None else "N/A"
                earnings_info = f"The upcoming quarterly earnings announcement is scheduled for {date_str}, with a consensus EPS estimate of {est_str}."
        except Exception as e:
            earnings_info = f"Upcoming earnings schedules could not be fully parsed: {e}."
            
    target_mean = m.get("targetMeanPrice")
    curr_price = m.get("current_price", 0)
    opinions = m.get("numberOfAnalystOpinions")
    rec = (m.get("recommendationKey") or "N/A").upper()
    if target_mean and curr_price:
        upside = ((target_mean - curr_price) / curr_price) * 100
        analyst_info = f"Wall Street consensus target for {company} is ${target_mean:.2f}, representing a {upside:+.2f}% change from the current price of ${curr_price:.2f}. This target is based on {opinions or 'N/A'} analyst opinions, with an overall consensus recommendation of '{rec}'."
    else:
        analyst_info = f"Wall Street recommendation consensus is '{rec}' with a mean target price of ${target_mean or 'N/A'}."
        
    guidance_and_expectations = f"{analyst_info} {earnings_info} Analysts will be monitoring margins and segment revenues closely to gauge if the company can exceed consensus expectations. Growth guidance provided by management during the conference call will be the primary driver of near-term stock momentum."

    # 9. Current Valuation
    pe = m.get("trailingPE")
    f_pe = m.get("forwardPE")
    pb = m.get("priceToBook")
    pe_str = f"{pe:.2f}x" if pe is not None else "N/A"
    f_pe_str = f"{f_pe:.2f}x" if f_pe is not None else "N/A"
    pb_str = f"{pb:.2f}x" if pb is not None else "N/A"
    current_valuation = f"The stock is trading at a trailing P/E of {pe_str}, a forward P/E of {f_pe_str}, and a Price/Book ratio of {pb_str}. Valuation multiples reflect market expectations regarding future growth, cash flow sustainability, and risk factors."

    # 10. Intrinsic Value Estimate & Margin of Safety
    dcf = sd.get("dcf_data", {})
    if dcf:
        intrinsic_value_estimate = f"Quantitative DCF model yields an implied intrinsic fair value of ${dcf.get('implied_price', 0):.2f} per share. This calculation assumes a WACC of {dcf.get('wacc', 9.0)}% and a terminal growth rate of {dcf.get('terminal_growth', 2.5)}%."
    else:
        intrinsic_value_estimate = "Intrinsic value estimate is calculated via the DCF engine based on current free cash flows and discount rate assumptions."

    if dcf and curr_price:
        implied = dcf.get("implied_price", 0)
        upside = ((implied - curr_price) / curr_price) * 100
        if upside > 0:
            margin_of_safety = f"The stock has an implied upside of {upside:.2f}% relative to the DCF fair value of ${implied:.2f}, providing a constructive margin of safety."
        else:
            margin_of_safety = f"The stock trades at a premium of {-upside:.2f}% over the DCF fair value of ${implied:.2f}, suggesting a limited margin of safety at current levels."
    else:
        margin_of_safety = "Review margin of safety manually by comparing stock price to the DCF implied valuation."

    # Calculate a dynamic fallback verdict based on the model-weighted valuation upside
    curr_price_val = m.get("current_price", 0.0)
    model_judgment = _model_weighted_valuation({}, sd)
    
    fallback_verdict = "HOLD"
    fallback_confidence = 60
    fallback_reasoning = "Quantitative indicators suggest holding the stock pending detailed manual review."
    fallback_thesis = "Hold for long-term target convergence."
    fallback_grade = "FAIRLY VALUED"
    
    if model_judgment and curr_price_val > 0:
        weighted_fair_value = model_judgment["weighted_fair_value"]
        upside = model_judgment["upside"]
        fallback_grade = _grade_from_upside(upside)
        
        if upside >= 0.25:
            fallback_verdict = "STRONG BUY"
            fallback_confidence = 85
            fallback_reasoning = f"Quantitative models indicate a significant undervaluation of {upside*100:.1f}%. Weighted fair value is estimated at ${weighted_fair_value:.2f} against a spot price of ${curr_price_val:.2f}."
            fallback_thesis = f"Strong Buy with an attractive valuation buffer and robust target convergence."
        elif upside >= 0.08:
            fallback_verdict = "BUY"
            fallback_confidence = 75
            fallback_reasoning = f"Quantitative indicators show constructive upside of {upside*100:.1f}%. Weighted fair value of ${weighted_fair_value:.2f} provides a solid margin of safety over the spot price of ${curr_price_val:.2f}."
            fallback_thesis = f"Buy to capture the fundamental upside relative to the weighted fair value midpoint."
        elif upside <= -0.25:
            fallback_verdict = "STRONG SELL"
            fallback_confidence = 85
            fallback_reasoning = f"Models indicate significant overvaluation with a downside of {upside*100:.1f}%. Spot price of ${curr_price_val:.2f} is significantly above the estimated weighted fair value of ${weighted_fair_value:.2f}."
            fallback_thesis = f"Strong Sell to mitigate downside and multiple compression risk."
        elif upside <= -0.08:
            fallback_verdict = "SELL"
            fallback_confidence = 75
            fallback_reasoning = f"Quantitative cross-checks suggest a downside of {upside*100:.1f}%. The current trading price of ${curr_price_val:.2f} exceeds the estimated fair value of ${weighted_fair_value:.2f}."
            fallback_thesis = f"Sell to realize profits and exit before target multiple alignment."
        else:
            fallback_verdict = "HOLD"
            fallback_confidence = 60
            fallback_reasoning = f"The stock is trading close to its estimated fair value of ${weighted_fair_value:.2f} (implied gap: {upside*100:+.1f}%), suggesting it is fairly valued."
            fallback_thesis = "Hold position as current levels reflect balanced fundamental risk-reward."

    return {
        "executive_summary": f"Quantitative assessment of {company} ({ticker}). Price: ${curr_price:.2f}, MCap: {_fmt_num(m.get('marketCap'))}. Analysis covers core financial growth, balance sheet resilience, and intrinsic DCF valuations.",
        "fundamental_analysis": {
            "revenue_quality": rev_quality,
            "profitability": profitability, 
            "earnings_power": earnings_power,
            "balance_sheet": balance_sheet, 
            "competitive_moat": competitive_moat,
            "management_score": 5, 
            "moat_rating": m.get("moat_rating", "N/A")
        },
        "macro_analysis": {
            "macro_environment": macro_environment, 
            "sector_outlook": sector_outlook,
            "tailwinds": ["Secular demand", "Brand power"], 
            "headwinds": ["Macro headwind", "Input costs"]
        },
        "sentiment_analysis": {
            "analyst_sentiment": f"Analyst consensus: {m.get('recommendationKey','N/A')}",
            "institutional_positioning": "Manual positioning review recommended.", 
            "news_sentiment": "Manual sentiment check recommended.",
            "sentiment_score": 5, 
            "sentiment_label": "NEUTRAL"
        },
        "valuation_assessment": {
            "current_valuation": current_valuation,
            "intrinsic_value_estimate": intrinsic_value_estimate,
            "margin_of_safety": margin_of_safety, 
            "valuation_grade": fallback_grade,
            "fair_value_low": 0, 
            "fair_value_mid": dcf.get('implied_price', 0) if dcf else 0, 
            "fair_value_high": 0
        },
        "risk_assessment": {
            "risk_factors": [
                {"risk": "Market risk", "severity": "MEDIUM", "probability": "MEDIUM", "impact": "General market downturn"},
                {"risk": "Sector risk", "severity": "MEDIUM", "probability": "MEDIUM", "impact": "Industry headwinds"},
                {"risk": "Valuation risk", "severity": "MEDIUM", "probability": "MEDIUM", "impact": "Multiple compression"},
            ],
            "worst_case_scenario": "Review manually.", 
            "risk_reward_ratio": "NEUTRAL"
        },
        "catalysts": [{"catalyst": "Earnings report", "timeline": "Next quarter", "impact": "POSITIVE"}],
        "verdict": fallback_verdict, 
        "verdict_confidence": fallback_confidence,
        "verdict_reasoning": fallback_reasoning,
        "investment_thesis": fallback_thesis,
        "guidance_and_expectations": guidance_and_expectations,
        "short_term_outlook": "Review short-term trend and chart moving averages.",
        "long_term_outlook": "Monitor secular trends and moat sustainability.",
        "price_target_12m": m.get("targetMeanPrice", curr_price),
        "bull_case_target": m.get("targetHighPrice", curr_price * 1.2),
        "bear_case_target": m.get("targetLowPrice", curr_price * 0.8),
        "position_sizing": "Start with a small starter position pending further analysis.",
    }
