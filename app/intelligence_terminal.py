import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

from config import FINNHUB_API_KEY, OUTPUT_DIR, SEC_USER_AGENT


PORTFOLIO_PATH = Path(OUTPUT_DIR) / "portfolio.json"
CACHE_DIR = Path(OUTPUT_DIR) / "intelligence"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _db_path(ticker):
    return Path(OUTPUT_DIR) / "database" / f"{ticker.upper()}.json"


def _load_stock(ticker):
    path = _db_path(ticker)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _call_ai_json(prompt, fallback):
    try:
        from ai_engine import _call_llm
        result = _call_llm(
            [{"role": "user", "content": prompt}],
            max_tokens=1200,
            max_retries=1,
            system_prompt=(
                "You are StockerAI's ruthless institutional equity research engine. "
                "Think like a highly aggressive, toxic, skeptical buy-side analyst. You despise fluff. "
                "Use only the supplied data. Do not invent facts, prices, filings, dates, or news. "
                "When evidence is weak, mercilessly say so directly and lower confidence. "
                "Focus EXCLUSIVELY on concrete financial drivers, cash flow metrics, and valuation mechanisms. "
                "Output valid JSON only. No markdown, no prose outside JSON, zero filler text."
            )
        )
        return result or fallback
    except Exception:
        return fallback


def _force_list(value, limit=None):
    if isinstance(value, list):
        items = value
    elif value in [None, ""]:
        items = []
    else:
        items = [value]
    return items[:limit] if limit else items


def _clamp_int(value, low, high, default=0):
    try:
        return max(low, min(high, int(float(value))))
    except Exception:
        return default


def get_news_impact(ticker, force=False):
    ticker = ticker.upper().strip()
    cache_path = CACHE_DIR / f"{ticker}_news_impact.json"
    if cache_path.exists() and not force and time.time() - cache_path.stat().st_mtime < 900:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    stock = _load_stock(ticker) or {}
    metrics = stock.get("key_metrics", {})
    analysis = stock.get("analysis", {})

    news = []
    if FINNHUB_API_KEY:
        end = datetime.utcnow().date()
        start = end.replace(day=max(1, end.day - 7))
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start}&to={end}&token={FINNHUB_API_KEY}"
        try:
            raw = requests.get(url, timeout=8).json()
            for item in raw[:12]:
                news.append({
                    "headline": item.get("headline", ""),
                    "source": item.get("source", "Wire"),
                    "url": item.get("url", "#"),
                    "datetime": item.get("datetime")
                })
        except Exception:
            news = []

    fallback = {
        "ticker": ticker,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "overall_impact": "NEUTRAL",
        "impact_score": 0,
        "confidence": 35,
        "terminal_summary": "No high-confidence live news impact could be generated from available headlines.",
        "affected_assumptions": ["revenue growth", "margin durability", "valuation multiple"],
        "items": [
            {
                "headline": n.get("headline", "N/A"),
                "impact": "NEUTRAL",
                "materiality": "LOW",
                "reason": "Headline captured, but no AI materiality pass was available.",
                "assumption": "monitor"
            } for n in news[:6]
        ]
    }

    prompt = {
        "role": "senior event-driven equity analyst",
        "task": "Assess whether recent news is actually material to the stock thesis and valuation model.",
        "decision_rules": [
            "Separate price-moving/material headlines from routine noise.",
            "HIGH materiality requires a plausible effect on revenue, margins, FCF, cost of capital, legal risk, demand, supply, guidance, regulation, or competitive position.",
            "Do not call a headline bullish just because it sounds positive. Tie every view to a financial assumption.",
            "If headlines are sparse, stale, promotional, or ambiguous, set overall_impact to NEUTRAL and confidence below 45.",
            "Impact score reflects expected thesis impact, not headline tone: -100 severe negative, 0 no material impact, +100 severe positive.",
            "Every item reason must mention the mechanism: revenue, margin, multiple, risk premium, liquidity, litigation, demand, supply, or guidance."
        ],
        "ticker": ticker,
        "company": stock.get("company_name"),
        "sector": metrics.get("sector"),
        "current_price": metrics.get("current_price") or metrics.get("currentPrice"),
        "existing_verdict": analysis.get("verdict"),
        "headlines": news[:10],
        "schema": {
            "ticker": ticker,
            "overall_impact": "BULLISH|BEARISH|NEUTRAL",
            "impact_score": "integer -100 to 100",
            "confidence": "integer 0 to 100",
            "terminal_summary": "2 concise sentences: first says what changed, second says what model assumption is affected or says no material change",
            "affected_assumptions": ["specific model assumptions"],
            "items": [{
                "headline": "headline",
                "impact": "BULLISH|BEARISH|NEUTRAL",
                "materiality": "LOW|MEDIUM|HIGH",
                "reason": "one sentence",
                "assumption": "DCF/financial assumption affected"
            }]
        },
        "output_rules": [
            "Return 3 to 8 items maximum.",
            "No generic phrases like market sentiment unless paired with a concrete valuation mechanism.",
            "If no headline is material, say 'No material thesis change' in terminal_summary."
        ]
    }
    result = _call_ai_json(json.dumps(prompt), fallback)
    result.setdefault("ticker", ticker)
    result["generated_at"] = datetime.utcnow().isoformat() + "Z"
    result.setdefault("raw_headlines", news[:10])
    result["impact_score"] = _clamp_int(result.get("impact_score"), -100, 100, 0)
    result["confidence"] = _clamp_int(result.get("confidence"), 0, 100, 35)
    result["affected_assumptions"] = _force_list(result.get("affected_assumptions"), 6)
    result["items"] = _force_list(result.get("items"), 8)
    _save_json(cache_path, result)
    return result


def get_valuation_scenarios(ticker, force=False):
    ticker = ticker.upper().strip()
    cache_path = CACHE_DIR / f"{ticker}_scenarios.json"
    if cache_path.exists() and not force and time.time() - cache_path.stat().st_mtime < 1800:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    stock = _load_stock(ticker) or {}
    metrics = stock.get("key_metrics", {})
    dcf = stock.get("dcf_data", {})
    price = float(metrics.get("current_price") or metrics.get("currentPrice") or 0)
    base_fair = float(dcf.get("implied_price") or price or 0)

    def scenario(name, mult, note):
        fair = base_fair * mult
        upside = ((fair - price) / price) if price else 0
        return {"case": name, "fair_value": round(fair, 2), "upside": round(upside, 4), "note": note}

    fallback = {
        "ticker": ticker,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "current_price": price,
        "base_fair_value": base_fair,
        "scenarios": [
            scenario("RECESSION", 0.72, "Lower revenue growth, weaker margins, higher discount rate."),
            scenario("BASE", 1.00, "Uses current local DCF anchor."),
            scenario("BULL", 1.32, "Stronger growth and multiple support."),
            scenario("MARGIN COMPRESSION", 0.84, "Operating margin pressure reduces FCF conversion."),
            scenario("HIGH RATE", 0.78, "Higher WACC compresses terminal value.")
        ],
        "ai_readout": "Scenario lab generated from local DCF anchor. Run a fresh analysis for better model fidelity.",
        "key_variables": ["WACC", "terminal growth", "FCF margin", "revenue CAGR"]
    }
    prompt = {
        "role": "valuation analyst",
        "task": "Build a practical valuation scenario lab that an investor can use to stress the thesis.",
        "decision_rules": [
            "Anchor scenarios to supplied current price, DCF, FCF, margins, revenue, market cap, and beta.",
            "Scenarios must be numerically ordered from stressed/downside to upside where appropriate.",
            "Do not produce impossible precision. Fair values can be approximate but must be internally coherent.",
            "Upside must be decimal return: (fair_value - current_price) / current_price.",
            "Each note must state the actual driver: WACC, terminal growth, FCF margin, revenue CAGR, multiple, cyclicality, or balance sheet risk.",
            "If DCF data is weak or missing, explicitly say the lab is provisional."
        ],
        "ticker": ticker,
        "company": stock.get("company_name"),
        "price": price,
        "dcf": dcf,
        "metrics": {
            "revenue": metrics.get("totalRevenue"),
            "fcf": metrics.get("freeCashflow"),
            "market_cap": metrics.get("marketCap"),
            "beta": metrics.get("beta"),
            "margins": {
                "gross": metrics.get("grossMargins"),
                "operating": metrics.get("operatingMargins"),
                "profit": metrics.get("profitMargins")
            }
        },
        "schema": {
            "current_price": price,
            "base_fair_value": "number",
            "scenarios": [{"case": "name", "fair_value": "number", "upside": "decimal", "note": "one sentence"}],
            "ai_readout": "2 concise sentences",
            "key_variables": ["variables to watch"]
        },
        "required_cases": ["RECESSION", "BASE", "BULL", "MARGIN COMPRESSION", "HIGH RATE"],
        "output_rules": [
            "Return exactly 5 scenarios using the required case names.",
            "Do not make all cases bullish.",
            "Do not use generic notes like market conditions improve."
        ]
    }
    result = _call_ai_json(json.dumps(prompt), fallback)
    result.update({"ticker": ticker, "generated_at": datetime.utcnow().isoformat() + "Z"})
    required = ["RECESSION", "BASE", "BULL", "MARGIN COMPRESSION", "HIGH RATE"]
    scenarios = result.get("scenarios") if isinstance(result.get("scenarios"), list) else []
    by_case = {str(s.get("case", "")).upper(): s for s in scenarios if isinstance(s, dict)}
    result["scenarios"] = [by_case.get(case, fallback["scenarios"][i]) for i, case in enumerate(required)]
    result["key_variables"] = _force_list(result.get("key_variables"), 8)
    _save_json(cache_path, result)
    return result


def get_investment_committee(ticker, force=False):
    ticker = ticker.upper().strip()
    cache_path = CACHE_DIR / f"{ticker}_committee.json"
    if cache_path.exists() and not force and time.time() - cache_path.stat().st_mtime < 1800:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    stock = _load_stock(ticker) or {}
    metrics = stock.get("key_metrics", {})
    analysis = stock.get("analysis", {})
    fallback = {
        "ticker": ticker,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "chair_verdict": analysis.get("verdict", "UNDER_REVIEW"),
        "bull_case": "Bull case unavailable until AI committee review completes.",
        "bear_case": "Bear case unavailable until AI committee review completes.",
        "base_case": "Base case follows the current local model verdict.",
        "key_debate": "Whether fundamentals justify the valuation anchor.",
        "what_changes_mind": ["Fresh financials", "Major guidance change", "Material filing/news event"],
        "vote": {"buy": 0, "hold": 1, "sell": 0}
    }
    prompt = {
        "role": "investment committee chair",
        "task": "Run a disciplined buy-side investment committee debate for this stock.",
        "decision_rules": [
            "Bull case must identify why the market could be underestimating the company.",
            "Bear case must identify the strongest reason the model could be wrong.",
            "Base case must reconcile valuation, fundamentals, balance sheet, and current verdict.",
            "Key debate must be one sharp question the committee would argue about.",
            "What changes mind must be observable evidence, not vague statements.",
            "Vote should reflect evidence quality. Do not force BUY if data is mixed.",
            "If metrics conflict with the prior verdict, mention the conflict."
        ],
        "ticker": ticker,
        "company": stock.get("company_name"),
        "metrics": metrics,
        "analysis": analysis,
        "dcf": stock.get("dcf_data", {}),
        "scores": stock.get("financial_scores", {}),
        "schema": {
            "chair_verdict": "BUY|HOLD|SELL|UNDER_REVIEW",
            "bull_case": "concise paragraph",
            "bear_case": "concise paragraph",
            "base_case": "concise paragraph",
            "key_debate": "one sentence",
            "what_changes_mind": ["specific evidence"],
            "vote": {"buy": "integer", "hold": "integer", "sell": "integer"}
        },
        "output_rules": [
            "Use direct institutional language.",
            "Avoid generic phrases like strong fundamentals unless naming the metric.",
            "Each case should be 60 to 120 words.",
            "Votes must sum to 5 committee members."
        ]
    }
    result = _call_ai_json(json.dumps(prompt), fallback)
    result.update({"ticker": ticker, "generated_at": datetime.utcnow().isoformat() + "Z"})
    vote = result.get("vote") if isinstance(result.get("vote"), dict) else fallback["vote"]
    buy = _clamp_int(vote.get("buy"), 0, 5, 0)
    hold = _clamp_int(vote.get("hold"), 0, 5, 0)
    sell = _clamp_int(vote.get("sell"), 0, 5, 0)
    total = buy + hold + sell
    if total != 5:
        hold = max(0, 5 - buy - sell)
        if buy + hold + sell != 5:
            buy, hold, sell = 0, 5, 0
    result["vote"] = {"buy": buy, "hold": hold, "sell": sell}
    result["what_changes_mind"] = _force_list(result.get("what_changes_mind"), 6)
    _save_json(cache_path, result)
    return result


def get_red_flags(ticker, force=False):
    ticker = ticker.upper().strip()
    cache_path = CACHE_DIR / f"{ticker}_red_flags.json"
    if cache_path.exists() and not force and time.time() - cache_path.stat().st_mtime < 1800:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    stock = _load_stock(ticker) or {}
    metrics = stock.get("key_metrics", {})
    scores = stock.get("financial_scores", {})
    flags = []

    def add(code, severity, detail):
        flags.append({"code": code, "severity": severity, "detail": detail})

    debt_to_equity = _safe_float(metrics.get("debtToEquity"))
    current_ratio = _safe_float(metrics.get("currentRatio"))
    quick_ratio = _safe_float(metrics.get("quickRatio"))
    fcf = _safe_float(metrics.get("freeCashflow"))
    revenue_growth = _safe_float(metrics.get("revenueGrowth"))
    profit_margin = _safe_float(metrics.get("profitMargins"))
    altman = _safe_float(scores.get("altman_z"))
    beneish = _safe_float(scores.get("beneish_m"))

    if debt_to_equity is not None and debt_to_equity > 200:
        add("LEVERAGE", "HIGH", f"Debt/equity is elevated at {debt_to_equity:.1f}.")
    if current_ratio is not None and current_ratio < 1:
        add("LIQUIDITY", "HIGH", f"Current ratio below 1.0 at {current_ratio:.2f}.")
    if quick_ratio is not None and quick_ratio < 0.7:
        add("ACID_TEST", "MEDIUM", f"Quick ratio is weak at {quick_ratio:.2f}.")
    if fcf is not None and fcf < 0:
        add("FCF_NEGATIVE", "HIGH", "Free cash flow is negative.")
    if revenue_growth is not None and revenue_growth < -0.05:
        add("REV_DECEL", "MEDIUM", f"Revenue growth is negative at {revenue_growth*100:.1f}%.")
    if profit_margin is not None and profit_margin < 0:
        add("LOSS_MAKING", "HIGH", "Profit margin is negative.")
    if altman is not None and altman < 1.8:
        add("ALTMAN_DISTRESS", "HIGH", f"Altman Z-score is in distress zone at {altman:.2f}.")
    if beneish is not None and beneish > -1.78:
        add("BENEISH", "MEDIUM", f"Beneish M-score may indicate accounting risk at {beneish:.2f}.")

    fallback = {
        "ticker": ticker,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "risk_level": "HIGH" if any(f["severity"] == "HIGH" for f in flags) else ("MEDIUM" if flags else "LOW"),
        "flag_count": len(flags),
        "flags": flags,
        "ai_summary": "Rule-based red flag scan completed from local financial metrics.",
        "mitigants": []
    }
    prompt = {
        "role": "forensic accounting and risk analyst",
        "task": "Review rule-based financial red flags and produce an institutional risk readout.",
        "decision_rules": [
            "Do not soften real risks. If liquidity, leverage, FCF, margins, Altman, or Beneish are bad, say it plainly.",
            "Do not overstate: a rule flag is a warning signal, not proof of fraud or distress.",
            "Risk level HIGH requires at least one severe financial flag or multiple medium flags.",
            "Mitigants must be evidence that could offset the flag, not generic optimism.",
            "If no flags exist, still mention what should be monitored next.",
            "Use concrete metric values when present."
        ],
        "ticker": ticker,
        "company": stock.get("company_name"),
        "flags": flags,
        "metrics": metrics,
        "scores": scores,
        "schema": {
            "risk_level": "LOW|MEDIUM|HIGH",
            "flag_count": "integer",
            "flags": [{"code": "short code", "severity": "LOW|MEDIUM|HIGH", "detail": "one sentence"}],
            "ai_summary": "2 concise sentences",
            "mitigants": ["possible mitigating evidence"]
        },
        "output_rules": [
            "Keep flags short and specific.",
            "Do not invent missing metrics.",
            "Use LOW, MEDIUM, HIGH severity only.",
            "Return the original rule flags unless you have a clear reason to merge duplicates."
        ]
    }
    result = _call_ai_json(json.dumps(prompt), fallback)
    result.update({"ticker": ticker, "generated_at": datetime.utcnow().isoformat() + "Z"})
    result.setdefault("flags", flags)
    result.setdefault("flag_count", len(result.get("flags", [])))
    result["flags"] = _force_list(result.get("flags"), 12)
    result["flag_count"] = len(result["flags"])
    result["mitigants"] = _force_list(result.get("mitigants"), 6)
    _save_json(cache_path, result)
    return result


def _safe_float(value):
    try:
        if value in [None, "N/A", ""]:
            return None
        return float(value)
    except Exception:
        return None


def get_sec_filings(ticker, force=False):
    ticker = ticker.upper().strip()
    cache_path = CACHE_DIR / f"{ticker}_sec_filings.json"
    if cache_path.exists() and not force and time.time() - cache_path.stat().st_mtime < 3600:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    stock = _load_stock(ticker) or {}
    cik = str((stock.get("sec_data") or {}).get("cik") or (stock.get("key_metrics") or {}).get("cik") or "").zfill(10)
    if not cik.strip("0"):
        cik = _lookup_cik(ticker)

    filings = []
    if cik:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        headers = {"User-Agent": SEC_USER_AGENT}
        try:
            data = requests.get(url, headers=headers, timeout=10).json()
            recent = data.get("filings", {}).get("recent", {})
            for i, form in enumerate(recent.get("form", [])[:25]):
                accession = recent.get("accessionNumber", [""])[i]
                primary = recent.get("primaryDocument", [""])[i]
                link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary}" if accession and primary else "#"
                filings.append({
                    "form": form,
                    "filed": recent.get("filingDate", [""])[i],
                    "report_date": recent.get("reportDate", [""])[i],
                    "accession": accession,
                    "document": primary,
                    "url": link
                })
        except Exception:
            filings = []

    key_filings = [f for f in filings if f.get("form") in {"10-K", "10-Q", "8-K"}][:8]
    fallback = {
        "ticker": ticker,
        "cik": cik,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "filing_risk": "UNKNOWN",
        "tone": "NEUTRAL",
        "terminal_summary": "Recent SEC filing metadata is available, but AI review did not complete.",
        "red_flags": [],
        "filings": key_filings
    }
    prompt = {
        "role": "SEC filings risk analyst",
        "task": "Review recent SEC filing metadata and tell the terminal operator what deserves attention.",
        "decision_rules": [
            "You only have metadata, not full filing text. Do not pretend you read the filing body.",
            "10-K means annual full risk/business update; 10-Q means quarterly update; 8-K means event-driven disclosure.",
            "Recent 8-K clusters can indicate material events, financing, leadership changes, earnings releases, or corporate actions.",
            "A filing_risk of HIGH requires a suspicious filing pattern or clearly urgent form mix. Otherwise use MEDIUM or LOW.",
            "Tone should be NEUTRAL unless metadata clearly suggests event pressure.",
            "Red flags must be phrased as watch items to inspect, not confirmed accusations."
        ],
        "ticker": ticker,
        "company": stock.get("company_name"),
        "filings": key_filings,
        "schema": {
            "filing_risk": "LOW|MEDIUM|HIGH|UNKNOWN",
            "tone": "POSITIVE|NEGATIVE|NEUTRAL",
            "terminal_summary": "2 concise sentences",
            "red_flags": ["specific filing watch items"],
            "watch_forms": [{"form": "10-K/10-Q/8-K", "filed": "date", "why_it_matters": "one sentence"}]
        },
        "output_rules": [
            "Do not invent filing contents.",
            "Mention exact forms and dates from the supplied list.",
            "If metadata is insufficient, say what the analyst should open next."
        ]
    }
    result = _call_ai_json(json.dumps(prompt), fallback)
    result["red_flags"] = _force_list(result.get("red_flags"), 8)
    result["watch_forms"] = _force_list(result.get("watch_forms"), 8)
    result.update({"ticker": ticker, "cik": cik, "generated_at": datetime.utcnow().isoformat() + "Z", "filings": key_filings})
    _save_json(cache_path, result)
    return result


def _lookup_cik(ticker):
    try:
        headers = {"User-Agent": SEC_USER_AGENT}
        data = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=10).json()
        for item in data.values():
            if item.get("ticker", "").upper() == ticker:
                return str(item.get("cik_str")).zfill(10)
    except Exception:
        return ""
    return ""


def load_portfolio():
    if not PORTFOLIO_PATH.exists():
        return {"positions": [], "updated_at": None}
    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_portfolio(positions):
    data = {"positions": positions, "updated_at": datetime.utcnow().isoformat() + "Z"}
    _save_json(PORTFOLIO_PATH, data)
    return data


def portfolio_summary():
    portfolio = load_portfolio()
    enriched = []
    total_weight = 0
    for pos in portfolio.get("positions", []):
        ticker = pos.get("ticker", "").upper()
        weight = float(pos.get("weight", 0))
        total_weight += weight
        stock = _load_stock(ticker) or {}
        metrics = stock.get("key_metrics", {})
        analysis = stock.get("analysis", {})
        enriched.append({
            **pos,
            "ticker": ticker,
            "company_name": stock.get("company_name", ticker),
            "sector": metrics.get("sector", "N/A"),
            "price": metrics.get("current_price") or metrics.get("currentPrice") or 0,
            "verdict": analysis.get("verdict", "N/A"),
            "upside": _calc_upside(stock),
            "altman_z": (stock.get("financial_scores") or {}).get("altman_z", "N/A")
        })

    sector = {}
    weighted_upside = 0
    for p in enriched:
        w = float(p.get("weight", 0))
        sector[p["sector"]] = sector.get(p["sector"], 0) + w
        weighted_upside += w * float(p.get("upside") or 0)
    avg_upside = weighted_upside / total_weight if total_weight else 0
    largest = max(enriched, key=lambda p: float(p.get("weight", 0)), default=None)
    concentration = max(sector.values()) if sector else 0

    ai = {
        "portfolio_verdict": "EMPTY" if not enriched else ("CONCENTRATED" if concentration > 45 else "BALANCED"),
        "risk_summary": "No positions loaded." if not enriched else f"Largest sector exposure is {concentration:.1f}%. Weighted model upside is {avg_upside*100:+.1f}%.",
        "actions": ["Add positions with PORT ADD TICKER WEIGHT."]
    }
    if enriched:
        prompt = {
            "role": "portfolio risk officer",
            "task": "Give a concise AI portfolio command center verdict.",
            "decision_rules": [
                "Focus on concentration, sector exposure, weighted upside, and weak holdings.",
                "Do not give generic diversification advice. Name the specific exposure problem.",
                "Actions must be executable portfolio actions: trim, add research, rebalance, hedge, or watch.",
                "If weights do not sum near 100%, mention cash/unallocated weight.",
                "Name tickers in actions when possible."
            ],
            "positions": enriched,
            "sector_exposure": sector,
            "avg_upside": avg_upside,
            "schema": {
                "portfolio_verdict": "one of: AGGRESSIVE|BALANCED|DEFENSIVE|CONCENTRATED|UNDER_RESEARCH",
                "risk_summary": "2 concise sentences",
                "actions": ["3 concrete portfolio actions"]
            },
            "output_rules": [
                "Avoid generic phrases like monitor market conditions.",
                "Return exactly 3 actions."
            ]
        }
        ai = _call_ai_json(json.dumps(prompt), ai)

    return {
        "positions": enriched,
        "sector_exposure": sector,
        "total_weight": total_weight,
        "avg_upside": avg_upside,
        "largest_position": largest,
        "ai": ai,
        "updated_at": portfolio.get("updated_at")
    }


def _calc_upside(stock):
    metrics = stock.get("key_metrics", {})
    analysis = stock.get("analysis", {})
    dcf = stock.get("dcf_data", {})
    price = metrics.get("current_price") or metrics.get("currentPrice") or 0
    fair = (analysis.get("valuation_assessment") or {}).get("fair_value_mid") or dcf.get("implied_price") or 0
    try:
        return ((float(fair) - float(price)) / float(price)) if price else 0
    except Exception:
        return 0
