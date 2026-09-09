"""
AI Engine -- Institutional analysis via Groq gpt-oss-120b (verified live 2026-09-08; Qwen params gated)
Fundamentals + Macro/Sentiment/Risk + CRO red-team. Qwen thinking mode for deep reasoning, fallback to Llama/OpenRouter.
"""
import json
import time
import requests
try:
    from config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE, GROQ_API_KEYS, GROQ_REASONING_EFFORT, GROQ_REASONING_FORMAT
except ImportError:
    from app.config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE, GROQ_API_KEYS, GROQ_REASONING_EFFORT, GROQ_REASONING_FORMAT


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


import pandas as pd

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


def _prepare_messages(messages, system_prompt=None):
    prepared = [
        {
            "role": message.get("role", "user"),
            "content": str(message.get("content", "")),
        }
        for message in (messages or [])
        if isinstance(message, dict)
    ]
    if system_prompt and not any(message["role"] == "system" for message in prepared):
        prepared.insert(0, {"role": "system", "content": system_prompt})
    return prepared


def _extract_message_text(message):
    if not isinstance(message, dict):
        return str(message or "")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("text")
        )
    return str(content or message.get("reasoning_content") or "")


def _parse_json_response(content):
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("Model response did not contain text or a JSON object")

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "", 1).replace("```JSON", "", 1)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Model response did not contain a valid JSON object")


def _call_llm(messages, model=None, max_tokens=None, max_retries=1, system_prompt=None, reasoning_effort=None):
    """Call configured providers in order and return one validated JSON object."""
    import os
    if os.environ.get("STOCKER_TEST_MODE") == "1":
        logger.info("  [TEST MODE] Skipping LLM API calls, returning None for fallback")
        return None

    try:
        from config import (
            ANTHROPIC_API_KEY,
            OPENROUTER_API_KEYS,
            OPENROUTER_BASE_URL,
            OPENROUTER_FALLBACK_MODEL,
            OPENROUTER_MODEL,
            OPENROUTER_TEMPERATURE,
            OPENROUTER_TIMEOUT,
            OPENCODE_API_KEY,
            OPENCODE_BASE_URL,
            OPENCODE_MODEL,
            OPENCODE_REASONING_EFFORT,
            OPENCODE_TIMEOUT,
        )
    except ImportError:
        from app.config import (
            ANTHROPIC_API_KEY,
            OPENROUTER_API_KEYS,
            OPENROUTER_BASE_URL,
            OPENROUTER_FALLBACK_MODEL,
            OPENROUTER_MODEL,
            OPENROUTER_TEMPERATURE,
            OPENROUTER_TIMEOUT,
            OPENCODE_API_KEY,
            OPENCODE_BASE_URL,
            OPENCODE_MODEL,
            OPENCODE_REASONING_EFFORT,
            OPENCODE_TIMEOUT,
        )

    prepared_messages = _prepare_messages(messages, system_prompt)
    attempts = max(1, int(max_retries or 1))
    token_limit = max_tokens or GROQ_MAX_TOKENS

    def _is_qwen(model_name: str) -> bool:
        return "qwen" in (model_name or "").lower()

    def call_openai_compatible(
        provider,
        url,
        api_key,
        provider_model,
        timeout,
        temperature,
        response_format=False,
        extra_headers=None,
        extra_body=None,
    ):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        headers.update(extra_headers or {})
        payload = {
            "model": provider_model,
            "messages": prepared_messages,
            "max_tokens": token_limit,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = {"type": "json_object"}
        if extra_body:
            payload.update(extra_body)
        # Qwen thinking mode - Groq reasoning_effort + reasoning_format (only when a Qwen model is configured)
        if _is_qwen(provider_model):
            try:
                from config import GROQ_REASONING_EFFORT as _cfg_eff, GROQ_REASONING_FORMAT as _cfg_fmt
            except ImportError:
                try:
                    from app.config import GROQ_REASONING_EFFORT as _cfg_eff, GROQ_REASONING_FORMAT as _cfg_fmt
                except ImportError:
                    _cfg_eff, _cfg_fmt = "default", "hidden"
            _eff = reasoning_effort or _cfg_eff
            _fmt = _cfg_fmt
            # sanitize
            if _eff not in ("low", "medium", "default", "high", "none"):
                _eff = "default"
            if _fmt not in ("hidden","parsed"):
                _fmt = "hidden"
            payload["reasoning_effort"] = _eff
            payload["reasoning_format"] = _fmt
            # Groq Qwen best-practice sampling (override if temp was generic low)
            if temperature < 0.3:
                payload["top_p"] = 0.95
                payload["top_k"] = 20

        last_error = None
        for attempt in range(attempts):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                choices = response.json().get("choices") or []
                if not choices:
                    raise ValueError("provider returned no choices")
                content = _extract_message_text(choices[0].get("message") or {})
                return _parse_json_response(content)
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(min(4, 2 ** attempt))
        logger.info("  [!] %s failed: %s", provider, last_error)
        return None

    now = time.time()
    keys = GROQ_API_KEYS if GROQ_API_KEYS else ([GROQ_API_KEY] if GROQ_API_KEY else [])
    for key_index, current_key in enumerate(keys):
        with _COOLDOWN_LOCK:
            cooldown_until = _RATE_LIMITED_KEYS.get(current_key, 0)
        if now < cooldown_until:
            logger.info(
                "  [!] Groq key %s/%s cooling down for %ss",
                key_index + 1,
                len(keys),
                int(cooldown_until - now),
            )
            continue

        logger.info("  > [Groq primary] %s (key %s/%s)...", model or GROQ_MODEL, key_index + 1, len(keys))
        result = call_openai_compatible(
            "Groq",
            GROQ_BASE_URL,
            current_key,
            model or GROQ_MODEL,
            45,
            GROQ_TEMPERATURE,
            response_format=True,
            extra_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        if result is not None:
            return result
        with _COOLDOWN_LOCK:
            _RATE_LIMITED_KEYS[current_key] = time.time() + 120

    if OPENCODE_API_KEY:
        # Zen endpoint requires a browser UA (CF 1010 without one) and accepts
        # reasoning_effort medium|high (verified 2026-09-09: no 400s on either).
        _oc_eff = reasoning_effort or OPENCODE_REASONING_EFFORT or "medium"
        if _oc_eff not in ("medium", "high"):
            _oc_eff = "medium"
        logger.info("  > [OpenCode] Calling %s (reasoning_effort=%s)...", OPENCODE_MODEL, _oc_eff)
        result = call_openai_compatible(
            "OpenCode",
            OPENCODE_BASE_URL,
            OPENCODE_API_KEY,
            OPENCODE_MODEL,
            OPENCODE_TIMEOUT,
            0.15,
            response_format=True,
            extra_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            extra_body={"reasoning_effort": _oc_eff},
        )
        if result is not None:
            return result

    openrouter_models = [OPENROUTER_MODEL]
    if OPENROUTER_FALLBACK_MODEL and OPENROUTER_FALLBACK_MODEL not in openrouter_models:
        openrouter_models.append(OPENROUTER_FALLBACK_MODEL)
    for openrouter_key in OPENROUTER_API_KEYS:
        for openrouter_model in openrouter_models:
            logger.info("  > [OpenRouter] Calling %s...", openrouter_model)
            result = call_openai_compatible(
                "OpenRouter",
                OPENROUTER_BASE_URL,
                openrouter_key,
                openrouter_model,
                OPENROUTER_TIMEOUT,
                OPENROUTER_TEMPERATURE,
                response_format=True,
                extra_headers={
                    "HTTP-Referer": "http://127.0.0.1:5001",
                    "X-Title": "StockerAI Workstation",
                },
            )
            if result is not None:
                return result

    if ANTHROPIC_API_KEY:
        system_text = "\n\n".join(
            message["content"]
            for message in prepared_messages
            if message["role"] == "system"
        )
        anthropic_messages = [
            message for message in prepared_messages if message["role"] != "system"
        ]
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": token_limit,
            "temperature": 0.15,
            "messages": anthropic_messages,
        }
        if system_text:
            payload["system"] = system_text
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            blocks = response.json().get("content") or []
            text = "\n".join(
                block.get("text", "")
                for block in blocks
                if isinstance(block, dict)
            )
            return _parse_json_response(text)
        except Exception as exc:
            logger.info("  [!] Anthropic failed: %s", exc)


    logger.info("  [X] All configured AI providers failed or are unavailable.")
    return None


def _call_groq(messages, model=None, max_tokens=None, max_retries=1, reasoning_effort=None):
    # Simply redirect to unified _call_llm
    # We will pass the system prompt if we can extract it to support Anthropic
    system_prompt = None
    for msg in messages:
        if msg.get("role") == "system":
            system_prompt = msg.get("content")
            break
    return _call_llm(messages, model=model, max_tokens=max_tokens, max_retries=max_retries, system_prompt=system_prompt, reasoning_effort=reasoning_effort)


from datetime import datetime
import logging
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_1 = """You are gpt-oss-120b - senior buy-side equity analyst at a $20B long/short fund, running in THINKING mode (reasoning_effort=default, 131K context, 450 tps).

THINKING PROTOCOL (internal, NOT in output):
- Think step-by-step: decompose each metric, cross-check math (DuPont = NetMargin x AssetTurnover x Leverage must foot), reconcile DCF against consensus target and regression trend, flag missing evidence before writing.
- If a KPI, segment mix, customer concentration, historical median, or management quote is absent from DATASET, mark DATA UNAVAILABLE - never invent.
- Use hidden reasoning trace to verify: fair_value_mid coherence with current price anchor, margin-of-safety sign, and verdict direction. Correct silently before emitting JSON.

OUTPUT - ONLY valid JSON (first char `{`, last `}`), no markdown fences, no filler:
{
  "executive_summary": "3 dense paragraphs (margin trajectory, DuPont ROE drivers, FCF conversion, Altman Z / Piotroski) + 4-5 bullets (- ). Synthesize structure, not numbers. End with definitive valuation judgment anchored to current price.",
  "fundamental_analysis": {
    "revenue_quality": "Reported revenue, growth, durability, concentration. If segment/recurring/pricing/customer data absent -> DATA UNAVAILABLE + what filing would confirm.",
    "profitability": "Gross/operating/EBITDA trends. DuPont breakdown explicitly: Net Margin x Asset Turnover x Equity Multiplier = ROE. State if expansion is structural or cyclical.",
    "earnings_power": "Trailing/forward EPS sustainability, FCF cash conversion (FCF/Net Income), quality of earnings.",
    "balance_sheet": "Liquidity vs debt, Altman Z implication (safe/grey/distress), current/quick trends, maturity/refi risk.",
    "capital_allocation": "Buybacks/dividends/M&A vs R&D, discipline rating.",
    "unit_economics": "Only if supplied. Never fabricate LTV, CAC, retention, per-unit margin, breakeven.",
    "competitive_moat": "Specific moat source (network effects, switching costs, IP, scale, data flywheel) and barriers.",
    "management_score": 8,
    "moat_rating": "WIDE"
  },
  "valuation_assessment": {
    "current_valuation": "Spot multiples vs cross-checks. No historical median claim unless median in dataset.",
    "intrinsic_value_estimate": "DCF/Monte Carlo: WACC, terminal growth, FCF basis - tie to numbers in LOCAL VALUATION ANCHORS.",
    "margin_of_safety": "Exact % upside/downside vs fair_value_mid. Sign must match grade.",
    "valuation_grade": "FAIRLY VALUED",
    "fair_value_low": 140.00,
    "fair_value_mid": 160.00,
    "fair_value_high": 185.00
  },
  "verdict": "BUY",
  "verdict_confidence": 75,
  "verdict_reasoning": "2-3 sentences: bridge unit economics + macro regime -> verdict. Name metrics.",
  "investment_thesis": "2-3 tradable sentences for execution desk (entry, catalyst, invalidation).",
  "position_sizing": "Weight (e.g. 2-4%) + scale-in/out, stop, trim rules."
}

RULES:
- ENUMS: verdict in {STRONG BUY,BUY,HOLD,SELL,STRONG SELL}; moat_rating in {NONE,NARROW,WIDE,VERY WIDE}; valuation_grade in {DEEPLY UNDERVALUED,UNDERVALUED,FAIRLY VALUED,OVERVALUED,DEEPLY OVERVALUED}
- TYPES: management_score, verdict_confidence = int; fair_value_* = float
- ANCHOR: All targets/grades/verdicts must be mathematically coherent with "Current price anchor". BUY => target > spot. SELL => target < spot.
- GROUNDING: Every claim names its metric or is labeled inference. Q-10K facts_summary and LOCAL VALUATION ANCHORS are truth.
- PERCENT SCALE: dataset *_pct are already pp. Raw 1.963 = 196.3%
- RECONCILIATION: Explicitly reconcile DCF fair value vs Wall Street mean target and forward growth. If DCF far above/below consensus, explain why you trust or fade it.
- NO AI FILLER (CRITICAL): BANNED: "In conclusion","It's important to note","delve","testament to","navigating","dynamic","ever-changing","robust","solid","landscape". Use clipped institutional shorthand.
- DENSITY: Markdown bullets (- ) inside text blocks for scan-ability. Prefer metrics over boilerplate.
"""


SYSTEM_PROMPT_2 = """You are gpt-oss-120b - senior portfolio risk & macro strategist (thinking mode). Skeptical, evidence-first. Separate FACTS vs MODEL IMPLICATION vs UNKNOWN. Do not invent regulation, geography, positioning, guidance, filings, dates, or catalysts.

THINKING PROTOCOL: Use hidden reasoning to stress-test: rates/FX pass-through to this company's model, sector capex cycle position, and whether sentiment is crowded. Map each headwind/tailwind to a P&L or multiple mechanism.

OUTPUT - ONLY valid JSON (first char `{`, last `}`):
{
  "macro_analysis": {
    "macro_environment": "Multi-paragraph: rates regime, inflation curve, GDP, FX/dollar pass-through to THIS company's costs/pricing/demand. Name mechanism, not generic macro.",
    "sector_outlook": "Structural: secular trends, capex cycle, AI/cloud adoption, supply chain, regulation catalysts specific to sector. No generic market commentary.",
    "regulatory_antitrust": "Only supplied evidence. Else DATA UNAVAILABLE + evidence needed.",
    "geopolitical_risk": "Only supplied geo/supply-chain/tariff. Do not assume China exposure.",
    "tailwinds": ["Specific growth mechanism 1","Margin expansion mechanism 2","Demand driver 3"],
    "headwinds": ["Cost pressure mechanism 1","Demand destruction mechanism 2","Policy risk 3"]
  },
  "sentiment_analysis": {
    "analyst_sentiment": "Rating distribution, target revisions, surprise history. Call out euphoria vs pessimism.",
    "institutional_positioning": "Insider flow, short interest, crowding if supplied; else DATA UNAVAILABLE.",
    "news_sentiment": "Structural bias in headlines (3-item sample).",
    "sentiment_score": 7,
    "sentiment_label": "BULLISH"
  },
  "risk_assessment": {
    "risk_factors": [
      {"risk": "Operational failure mechanism","severity": "HIGH","probability": "MEDIUM","impact": "Math on margins/multiples"},
      {"risk": "Macro/industry risk","severity": "MEDIUM","probability": "MEDIUM","impact": "Operational impact"},
      {"risk": "Leverage/liquidity","severity": "MEDIUM","probability": "LOW","impact": "Maturity/covenant"},
      {"risk": "Competitive threat","severity": "LOW","probability": "MEDIUM","impact": "Share erosion path"}
    ],
    "worst_case_scenario": "Vicious bear case: multiple compression + margin contraction -> downside target.",
    "risk_reward_ratio": "FAVORABLE"
  },
  "catalysts": [
    {"catalyst": "Evidence checkpoint 1","timeline": "Known date or UNKNOWN","impact": "POSITIVE|NEGATIVE|MIXED"},
    {"catalyst": "Evidence checkpoint 2","timeline": "Known date or UNKNOWN","impact": "POSITIVE|NEGATIVE|MIXED"},
    {"catalyst": "Evidence checkpoint 3","timeline": "Known date or UNKNOWN","impact": "POSITIVE|NEGATIVE|MIXED"}
  ],
  "guidance_and_expectations": "Forward guidance, sandbagging history, setup into next print. Bullets (- ).",
  "short_term_outlook": "1-3 month directional bias + invalidation.",
  "long_term_outlook": "3-5 year structural thesis.",
  "price_target_12m": 175.00,
  "bull_case_target": 200.00,
  "bear_case_target": 130.00
}

RULES:
- ENUMS: sentiment_label in {VERY BEARISH,BEARISH,NEUTRAL,BULLISH,VERY BULLISH}; risk_reward_ratio in {VERY FAVORABLE,FAVORABLE,NEUTRAL,UNFAVORABLE,VERY UNFAVORABLE}; severity/probability in {HIGH,MEDIUM,LOW}; impact in {POSITIVE,NEGATIVE,MIXED}
- TYPES: sentiment_score int; price_target_12m/bull/bear float
- ANCHOR: targets coherent with spot. BUY => target > spot.
- SPECIFICITY: Risks name failure mechanism and $/margin/multiple impact. No vague "macro headwinds".
- FORWARD EPS CHECK: Reconcile targets vs Forward EPS x Forward P/E. Flag stale targets.
- NO FILLER: Same banned list as Prompt 1. Institutional shorthand only.
"""

SYSTEM_PROMPT_3 = """You are gpt-oss-120b - Chief Risk Officer (thinking mode) red-teaming the thesis. Audit reasoning, data quality, valuation sensitivity, contradictions. Be adversarial but evidence-based - do not invent failure modes.

THINKING PROTOCOL: Identify the single weakest evidenced assumption, the metric that would falsify it, and the valuation delta if wrong. Check for: DCF vs consensus divergence, regression overbought, stale target, leverage blind spot, moat overstatement.

OUTPUT - ONLY valid JSON (first char `{`, last `}`):
{
  "red_team_audit": "One dense paragraph: weakest assumption + falsification metric + valuation consequence. Cite numbers.",
  "fatal_flaw_probability": "HIGH",
  "adjusted_verdict": "DOWNGRADE TO HOLD"
}

RULES:
- fatal_flaw_probability in {HIGH,MEDIUM,LOW}
- adjusted_verdict in {MAINTAIN,DOWNGRADE TO HOLD,DOWNGRADE TO SELL}
- No tone as substitute for numbers. Point to concrete missing evidence or inconsistency.
"""


def _deep_merge_defaults(defaults, value):
    if not isinstance(defaults, dict):
        return value if value not in [None, ""] else defaults
    source = value if isinstance(value, dict) else {}
    merged = {}
    for key, default_value in defaults.items():
        merged[key] = _deep_merge_defaults(default_value, source.get(key))
    for key, source_value in source.items():
        if key not in merged and source_value not in [None, ""]:
            merged[key] = source_value
    return merged


def _enum_value(value, allowed, default):
    normalized = str(value or "").strip().upper()
    return normalized if normalized in allowed else default


def _bounded_number(value, default, low=None, high=None):
    parsed = _num_or_none(value)
    if parsed is None:
        parsed = default
    if low is not None:
        parsed = max(low, parsed)
    if high is not None:
        parsed = min(high, parsed)
    return parsed


def _normalize_analysis_payload(result, fallback):
    merged = _deep_merge_defaults(fallback, result if isinstance(result, dict) else {})

    merged["verdict"] = _enum_value(
        merged.get("verdict"),
        {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"},
        fallback.get("verdict", "HOLD"),
    )
    merged["verdict_confidence"] = int(
        round(_bounded_number(merged.get("verdict_confidence"), 50, 0, 100))
    )

    fundamentals = merged.setdefault("fundamental_analysis", {})
    fundamentals["management_score"] = int(
        round(_bounded_number(fundamentals.get("management_score"), 5, 0, 10))
    )
    fundamentals["moat_rating"] = _enum_value(
        fundamentals.get("moat_rating"),
        {"NONE", "NARROW", "WIDE", "VERY WIDE"},
        "NARROW",
    )

    valuation = merged.setdefault("valuation_assessment", {})
    for key in ("fair_value_low", "fair_value_mid", "fair_value_high"):
        valuation[key] = round(_bounded_number(valuation.get(key), 0, 0), 2)
    positive_values = [
        valuation[key]
        for key in ("fair_value_low", "fair_value_mid", "fair_value_high")
        if valuation[key] > 0
    ]
    if positive_values:
        low, high = min(positive_values), max(positive_values)
        mid = valuation["fair_value_mid"] or sorted(positive_values)[len(positive_values) // 2]
        valuation["fair_value_low"] = round(min(low, mid), 2)
        valuation["fair_value_mid"] = round(mid, 2)
        valuation["fair_value_high"] = round(max(high, mid), 2)
    valuation["valuation_grade"] = _enum_value(
        valuation.get("valuation_grade"),
        {
            "DEEPLY UNDERVALUED",
            "UNDERVALUED",
            "FAIRLY VALUED",
            "OVERVALUED",
            "DEEPLY OVERVALUED",
        },
        "FAIRLY VALUED",
    )

    sentiment = merged.setdefault("sentiment_analysis", {})
    sentiment["sentiment_score"] = int(
        round(_bounded_number(sentiment.get("sentiment_score"), 5, 0, 10))
    )
    sentiment["sentiment_label"] = _enum_value(
        sentiment.get("sentiment_label"),
        {"VERY BEARISH", "BEARISH", "NEUTRAL", "BULLISH", "VERY BULLISH"},
        "NEUTRAL",
    )

    macro = merged.setdefault("macro_analysis", {})
    for key in ("tailwinds", "headwinds"):
        value = macro.get(key)
        if not isinstance(value, list):
            value = [value] if value else []
        macro[key] = [str(item) for item in value if item not in [None, ""]][:6]

    risk = merged.setdefault("risk_assessment", {})
    normalized_risks = []
    for item in risk.get("risk_factors") or []:
        if not isinstance(item, dict):
            continue
        normalized_risks.append(
            {
                "risk": str(item.get("risk") or "Unspecified risk"),
                "severity": _enum_value(
                    item.get("severity"), {"LOW", "MEDIUM", "HIGH"}, "MEDIUM"
                ),
                "probability": _enum_value(
                    item.get("probability"), {"LOW", "MEDIUM", "HIGH"}, "MEDIUM"
                ),
                "impact": str(item.get("impact") or "Impact requires manual review."),
            }
        )
    if not normalized_risks:
        normalized_risks = fallback.get("risk_assessment", {}).get("risk_factors", [])
    risk["risk_factors"] = normalized_risks[:8]
    risk["risk_reward_ratio"] = _enum_value(
        risk.get("risk_reward_ratio"),
        {
            "VERY FAVORABLE",
            "FAVORABLE",
            "NEUTRAL",
            "UNFAVORABLE",
            "VERY UNFAVORABLE",
        },
        "NEUTRAL",
    )

    catalysts = []
    for item in merged.get("catalysts") or []:
        if not isinstance(item, dict):
            continue
        catalysts.append(
            {
                "catalyst": str(item.get("catalyst") or "Evidence checkpoint"),
                "timeline": str(item.get("timeline") or "UNKNOWN"),
                "impact": _enum_value(
                    item.get("impact"),
                    {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL"},
                    "MIXED",
                ),
            }
        )
    merged["catalysts"] = catalysts[:6] or fallback.get("catalysts", [])

    for key in ("price_target_12m", "bull_case_target", "bear_case_target"):
        merged[key] = round(_bounded_number(merged.get(key), 0, 0), 2)
    return merged


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
        logger.info(f"  > Attempting AI Part 1/2 gpt-oss-120b Fundamentals & Valuation (thinking=default)...")
        res = _call_groq(messages_1, model=GROQ_MODEL, max_tokens=4000)
        if res is None:
            logger.info("  ⚠️ Part 1 failed or rate-limited. Falling back to fast secondary model...")
            res = _call_groq(messages_1, model="openai/gpt-oss-20b", max_tokens=4000)
        return res

    def run_part_2():
        logger.info(f"  > Attempting AI Part 2/2 gpt-oss-120b Macro/Sentiment/Risk (thinking=default)...")
        res = _call_groq(messages_2, model=GROQ_MODEL, max_tokens=4000)
        if res is None:
            logger.info("  ⚠️ Part 2 failed or rate-limited. Falling back to fast secondary model...")
            res = _call_groq(messages_2, model="openai/gpt-oss-20b", max_tokens=4000)
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
        
    result = _normalize_analysis_payload({**res1, **res2}, fallback_data)

    # Run Part 3: Chief Risk Officer Red Team
    def run_part_3(base_analysis):
        logger.info(f"  > Executing AI Part 3/3 gpt-oss-120b CRO Red Team (thinking=default)...")
        messages_3 = [
            {"role": "system", "content": SYSTEM_PROMPT_3},
            {"role": "user", "content": f"Review this analysis and provide your Red Team Audit:\n\n{json.dumps(base_analysis, indent=2)}"}
        ]
        # CRO red-team uses high reasoning effort for deepest adversarial reasoning
        res = _call_llm(messages_3, model=GROQ_MODEL, max_tokens=2500, system_prompt=SYSTEM_PROMPT_3, reasoning_effort="high")
        if res is None:
            res = _call_groq(messages_3, model="openai/gpt-oss-20b", max_tokens=1000)
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

    result = _normalize_analysis_payload(result, fallback_data)

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

    # Map of old verdict words to replace -> new verdict
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
    points = [
        point
        for point in points
        if curr_price * 0.20 <= point[1] <= curr_price * 5.0
    ]
    if not points:
        return None

    total_w = sum(p[2] for p in points)
    weighted_mean = sum(p[1] * p[2] for p in points) / total_w
    cumulative = 0
    weighted_median = weighted_mean
    for _, value, weight in sorted(points, key=lambda point: point[1]):
        cumulative += weight
        if cumulative >= total_w / 2:
            weighted_median = value
            break

    # Blend toward the weighted median so one extreme DCF or stale target
    # cannot dominate every other cross-check.
    weighted = (weighted_median * 0.65) + (weighted_mean * 0.35)
    upside = (weighted - curr_price) / curr_price
    return {
        "weighted_fair_value": weighted,
        "upside": upside,
        "points": points,
        "method": "65% weighted median / 35% weighted mean",
    }


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


# ---------------------------------------------------------------------------
# AI MACRO-IMPACT LAYER (append-only; single-ticker rates/Fed regime impact)
# Chain: OpenCode -> OpenRouter -> Anthropic -> Groq via _call_llm
# (response_format=True is enforced inside the chain per provider).
# STOCKER_TEST_MODE=1 makes _call_llm return None -> rules fallback, no network.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_MACRO = """You are gpt-oss-120b - senior macro strategist (thinking mode) translating rates/Fed/inflation regime into single-ticker impact. Skeptical, evidence-first. Separate FACTS vs MODEL IMPLICATION vs UNKNOWN. Do not invent yields, CPI prints, FOMC dates, guidance, filings, geography, or positioning.

THINKING PROTOCOL (internal, NOT in output):
- Map the regime to THIS ticker only through three channels: duration (long-dated growth cash flows vs near-term cash cow), funding (leverage, refi wall, floating-rate share), demand (housing/auto turnover, capex deferral, NIM for banks, fuel pass-through for energy).
- Cross-check discount-rate math against the supplied DCF WACC: higher-for-longer lifts WACC and compresses the justified multiple; cuts do the reverse. Direction + rough magnitude only, never a false-precision target.
- If a yield, gauge, Fed stance, or company field is absent from MACRO SNAPSHOT / DATASET, write DATA UNAVAILABLE + the print or filing that would confirm it. Never interpolate missing macro data.

OUTPUT - ONLY valid JSON (first char `{`, last `}`), no markdown fences, no filler:
{
  "regime_read": "1-2 sentences: current rates/Fed/inflation regime (higher-for-longer, cutting cycle, on-hold, re-acceleration) grounded ONLY in the supplied snapshot.",
  "rate_sensitivity": {"level": "HIGH", "why": "Duration + leverage mechanism specific to this ticker (e.g. long-duration growth multiple + floating refi wall)."},
  "winners_losers_mechanism": "Why this ticker's sector wins, loses, or is mixed under the stated regime (pass-through, NIM, capex deferral, housing turnover, ad budgets).",
  "earnings_impact": "P&L path: revenue, margins, interest expense, buyback capacity. Name the line item or mark DATA UNAVAILABLE.",
  "valuation_impact": "Discount-rate math: current DCF WACC vs regime-implied direction, justified-multiple expansion/compression. No new price target.",
  "positioning": "What to watch: next CPI prints, FOMC decision/statement, 10Y-2Y curve shape, plus the ticker-specific invalidation metric.",
  "risk_flags": ["Concrete macro risk 1 with transmission", "Concrete macro risk 2"]
}

RULES:
- ENUMS: rate_sensitivity.level in {HIGH,MED,LOW}
- TYPES: regime_read/winners_losers_mechanism/earnings_impact/valuation_impact/positioning = string; rate_sensitivity = object with level + why; risk_flags = array of strings (empty array allowed, never null)
- GROUNDING: Every regime claim cites the snapshot (yield level, gauge, or Fed stance) or is labeled inference. Absent fields -> DATA UNAVAILABLE.
- NO FILLER: BANNED: "In conclusion","It's important to note","delve","testament to","navigating","dynamic","ever-changing","robust","solid","landscape". Institutional shorthand only.
"""


def _macro_base_sensitivity(sector):
    """Map sector -> (level, why). Energy/Financials are LOW (mixed/beneficiary of higher rates)."""
    s = str(sector or "").lower()
    if any(k in s for k in ("utilit", "real estate", "reit", "consumer defensive", "staple")):
        return ("HIGH", "Defensive yield-proxy sector: dividend yield competes directly with risk-free rates, so higher-for-longer compresses justified multiples; REITs/utilities also carry regulated-capex funding needs.")
    if any(k in s for k in ("energy", "oil", "gas", "coal", "uranium")):
        return ("LOW", "Energy is mixed-to-beneficiary under higher rates: inflation/higher-for-longer typically coincides with firm commodity prices and pricing power, partly offsetting discount-rate drag.")
    if any(k in s for k in ("financial", "bank", "insurance")):
        return ("LOW", "Financials are mixed-to-beneficiary of higher rates via net interest margin expansion, offset by credit-loss/mark-to-market risk if the curve inverts or stays high.")
    return ("MED", "MED-HIGH in practice: duration-sensitive cash flows (growth multiple, capex cycle, ad/subscription demand) transmit rate moves to both earnings and the discount rate.")


def _macro_apply_amplifiers(level, beta, debt_to_equity):
    """Shift base level one notch per amplifier. debtToEquity >10 assumed percent-scale (/100)."""
    order = ["LOW", "MED", "HIGH"]
    idx = order.index(level) if level in order else 1
    notes = []
    try:
        b = float(beta) if beta is not None else None
    except (TypeError, ValueError):
        b = None
    try:
        d = float(debt_to_equity) if debt_to_equity is not None else None
    except (TypeError, ValueError):
        d = None
    if d is not None and d > 10:
        d = d / 100.0
    if b is not None and b >= 1.3 and idx < 2:
        idx += 1
        notes.append(f"Beta {b:.2f} amplifies market-rate beta: lifting one notch.")
    elif b is not None and b <= 0.7 and idx > 0:
        idx -= 1
        notes.append(f"Beta {b:.2f} dampens market-rate beta: lowering one notch.")
    if d is not None and d >= 1.0 and idx < 2:
        idx += 1
        notes.append(f"Debt/Equity {d:.2f}x forces refi at higher coupons: lifting one notch.")
    return order[idx], notes


def _normalize_macro_payload(result, ticker):
    src = result if isinstance(result, dict) else {}
    rs = src.get("rate_sensitivity", {})
    if not isinstance(rs, dict):
        rs = {"level": rs, "why": ""}

    def _s(v, default="DATA UNAVAILABLE"):
        t = str(v or "").strip()
        return t if t else default

    flags = src.get("risk_flags", [])
    if isinstance(flags, str):
        flags = [flags]
    try:
        flags = [str(f).strip() for f in (flags or []) if str(f).strip()][:8]
    except Exception:
        flags = []
    return {
        "ticker": ticker,
        "source": "llm",
        "regime_read": _s(src.get("regime_read")),
        "rate_sensitivity": {
            "level": _enum_value(rs.get("level"), {"HIGH", "MED", "LOW"}, "MED"),
            "why": _s(rs.get("why"), "See regime and sector mechanism."),
        },
        "winners_losers_mechanism": _s(src.get("winners_losers_mechanism")),
        "earnings_impact": _s(src.get("earnings_impact")),
        "valuation_impact": _s(src.get("valuation_impact")),
        "positioning": _s(src.get("positioning")),
        "risk_flags": flags,
    }


def _macro_rule_fallback(sd, snap):
    """Deterministic rules fallback: sector map + beta/debtToEquity amplifiers. Never raises."""
    try:
        m = sd.get("key_metrics", {}) if isinstance(sd.get("key_metrics"), dict) else {}
    except Exception:
        m = {}
    try:
        ticker = str(sd.get("ticker") or m.get("symbol") or "UNKNOWN").upper()
    except Exception:
        ticker = "UNKNOWN"
    sector = m.get("sector") or "Unknown"
    industry = m.get("industry") or "Unknown"
    beta = m.get("beta")
    dte = m.get("debtToEquity")
    dcf = sd.get("dcf_data", {}) if isinstance(sd.get("dcf_data"), dict) else {}
    wacc = dcf.get("wacc") if isinstance(dcf, dict) else None

    base_level, base_why = _macro_base_sensitivity(sector)
    level, amp_notes = _macro_apply_amplifiers(base_level, beta, dte)
    why = base_why + (" " + " ".join(amp_notes) if amp_notes else "")

    snap = snap if isinstance(snap, dict) else {}
    regime = snap.get("regime") or snap.get("fed_stance") or snap.get("fedStance")
    yields = snap.get("yields")
    if regime or yields:
        regime_read = f"Snapshot regime: {regime or 'DATA UNAVAILABLE (regime/fed_stance)'}; yields: {yields if yields is not None else 'DATA UNAVAILABLE'}. Transmission to {ticker} via the duration/funding/demand channels below."
    else:
        regime_read = "DATA UNAVAILABLE: macro snapshot missing (need yields, gauges, fed_stance from app/macro_fetcher.py get_macro_snapshot()). Sector-mechanism read below is unconditional."

    # Mechanism text keys off the SECTOR bucket (base_level); amplifiers move only
    # rate_sensitivity.level, with the reason recorded in its `why`.
    if base_level == "HIGH":
        wl = f"{sector} ({industry}) loses under higher-for-longer: yield-proxy dividend competes with cash, funded capex/refi reprices higher; benefits when the cutting cycle resumes."
        earn = "Earnings path: interest expense up on refi/floating tranches, dividend/buyback capacity squeezed; revenue softens if rate-sensitive demand (housing, auto, SMB capex) defers. Confirm interest expense and maturity wall in filings."
    elif base_level == "LOW":
        wl = f"{sector} ({industry}) is mixed-to-beneficiary of higher rates: banks/insurers gain net interest margin, energy keeps commodity pricing power; pain arrives via credit losses or demand destruction if rates overshoot."
        earn = "Earnings path: net interest income / realized commodity prices support the top line; watch credit-loss provisions (financials) or volume decline (energy) as offsets. Confirm NIM and provision line items."
    else:
        wl = f"{sector} ({industry}) is MED-HIGH in practice: growth-multiple duration plus cyclical demand (capex, advertising, subscriptions) makes it a rates loser at the margin, with AI/cloud secular demand as partial offset."
        earn = "Earnings path: enterprise/SMB budget scrutiny slows revenue; margin via opex discipline; buybacks funded with dearer debt. Confirm segment growth and net interest expense."

    if wacc is not None:
        try:
            val = f"Discount-rate math vs DCF WACC {float(wacc):.2f}%: each +100bps regime lift on WACC compresses justified value; cuts do the reverse. Re-run DCF at WACC +/-100bps to size {ticker} multiple impact. No new price target set here."
        except (TypeError, ValueError):
            val = "DATA UNAVAILABLE: DCF WACC not numeric; directionally, higher-for-longer lifts WACC and compresses justified multiples, cuts reverse it."
    else:
        val = "DATA UNAVAILABLE: DCF WACC not in record; directionally, higher-for-longer lifts WACC and compresses justified multiples, cuts reverse it. Re-run DCF to size it."

    flags = [
        f"Curve risk: 10Y-2Y inversion/re-steepening reprices {ticker} duration before earnings adjust.",
        f"Refi wall: Debt/Equity {dte if dte is not None else 'DATA UNAVAILABLE'} rolling into higher coupons lifts interest expense.",
    ]
    if isinstance(beta, (int, float)) and beta >= 1.3:
        flags.append(f"High beta ({beta:.2f}): drawdown amplifies if CPI/FOMC surprises hawkish.")
    if not snap:
        flags.append("Snapshot risk: macro_fetcher offline; regime_read is unconditional until yields/gauges/fed_stance land.")

    return {
        "ticker": ticker,
        "source": "rules",
        "regime_read": regime_read,
        "rate_sensitivity": {"level": level, "why": why},
        "winners_losers_mechanism": wl,
        "earnings_impact": earn,
        "valuation_impact": val,
        "positioning": f"What to watch for {ticker}: next CPI prints, FOMC decision/statement, 10Y-2Y curve; invalidation metric: {industry} demand + net interest expense trend.",
        "risk_flags": flags,
    }


def get_macro_impact(stock_data, macro_snapshot=None):
    """Single-ticker macro impact. LLM first (~1500 tokens), deterministic rules fallback. Never raises."""
    sd = stock_data if isinstance(stock_data, dict) else {}
    try:
        m = sd.get("key_metrics", {}) if isinstance(sd.get("key_metrics"), dict) else {}
    except Exception:
        m = {}
    try:
        ticker = str(sd.get("ticker") or m.get("symbol") or "UNKNOWN").upper()
    except Exception:
        ticker = "UNKNOWN"

    snap = macro_snapshot
    if snap is None:
        try:
            try:
                from macro_fetcher import get_macro_snapshot
            except ImportError:
                from app.macro_fetcher import get_macro_snapshot
            snap = get_macro_snapshot()
        except Exception as exc:
            logger.info("  [!] macro snapshot unavailable: %s", exc)
            snap = {}
    if not isinstance(snap, dict):
        snap = {"value": snap}

    try:
        try:
            snap_text = json.dumps(snap, default=str)[:2000]
        except Exception:
            snap_text = "DATA UNAVAILABLE"
        dcf = sd.get("dcf_data", {}) if isinstance(sd.get("dcf_data"), dict) else {}
        user_content = (
            f"Produce the single-ticker MACRO IMPACT for '{ticker}'.\n\n"
            f"DATASET: sector={m.get('sector', 'DATA UNAVAILABLE')} | industry={m.get('industry', 'DATA UNAVAILABLE')} | "
            f"beta={m.get('beta', 'DATA UNAVAILABLE')} | debtToEquity={m.get('debtToEquity', 'DATA UNAVAILABLE')} | "
            f"current_price={m.get('current_price', 'DATA UNAVAILABLE')} | DCF WACC={dcf.get('wacc', 'DATA UNAVAILABLE')} | "
            f"DCF implied={dcf.get('implied_price', 'DATA UNAVAILABLE')}\n\n"
            f"MACRO SNAPSHOT (yields/gauges/fed_stance/regime; DATA UNAVAILABLE where absent):\n{snap_text}"
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_MACRO},
            {"role": "user", "content": user_content},
        ]
        res = _call_llm(messages, model=GROQ_MODEL, max_tokens=1500, system_prompt=SYSTEM_PROMPT_MACRO)
        if isinstance(res, dict) and res:
            return _normalize_macro_payload(res, ticker)
        return _macro_rule_fallback(sd, snap)
    except Exception as exc:
        logger.info("  [!] get_macro_impact failed, using rules fallback: %s", exc)
        try:
            return _macro_rule_fallback(sd, snap if isinstance(snap, dict) else {})
        except Exception:
            return _macro_rule_fallback({}, {})
