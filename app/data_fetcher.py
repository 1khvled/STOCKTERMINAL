"""
Data Fetcher — Pulls all stock data from Yahoo Finance
"""
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from config import (
    HISTORY_PERIOD_SHORT, HISTORY_PERIOD_LONG,
    SMA_WINDOWS, RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    ALPHA_VANTAGE_API_KEY, GROQ_API_KEY, GROQ_BASE_URL,
    SEC_USER_AGENT
)

import logging
logger = logging.getLogger(__name__)

SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def _json_default(obj):
    if hasattr(obj, "strftime"):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, (dict, list, tuple, set)):
        return list(obj) if not isinstance(obj, dict) else obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj):
            return None
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return str(obj)


def _write_raw_snapshot(raw_dir, filename, payload):
    if not raw_dir:
        return None
    try:
        raw_dir = Path(raw_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, default=_json_default, indent=2)
        return str(path)
    except Exception as e:
        logger.info(f"  [!] Failed to write raw snapshot {filename}: {e}")
        return None


def _df_snapshot(df, max_rows=None):
    if df is None or df.empty:
        return {"columns": [], "rows": []}
    out = df.copy()
    if max_rows:
        out = out.tail(max_rows)
    out = out.reset_index()
    out.columns = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in out.columns]
    return {
        "columns": [str(c) for c in out.columns],
        "rows": out.to_dict(orient="records")
    }


def _confidence(source, status="reported", detail=""):
    return {"source": source, "status": status, "detail": detail}


def _latest_index_date(df):
    if df is None or df.empty:
        return None
    idx = df.index[-1]
    return idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)


def _statement_dates(df):
    if df is None or df.empty:
        return []
    dates = []
    for col in df.columns:
        dates.append(col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col))
    return dates


def _latest_fact_value(companyfacts, taxonomy, concepts, unit="USD"):
    facts = companyfacts.get("facts", {}).get(taxonomy, {})
    candidates = []
    for concept in concepts:
        node = facts.get(concept, {})
        units = node.get("units", {})
        for row in units.get(unit, []):
            if row.get("val") is None:
                continue
            candidates.append({
                "concept": concept,
                "value": row.get("val"),
                "fy": row.get("fy"),
                "fp": row.get("fp"),
                "form": row.get("form"),
                "filed": row.get("filed"),
                "end": row.get("end"),
                "frame": row.get("frame"),
                "accn": row.get("accn")
            })
    candidates.sort(key=lambda r: (str(r.get("filed") or ""), str(r.get("end") or "")), reverse=True)
    return candidates[0] if candidates else None


def _sec_request_with_retry(url, headers, timeout, retries=3, backoff=2.0):
    """Fetch URL with retries and exponential backoff, handling 429 and timeouts."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                sleep_time = float(resp.headers.get("Retry-After", backoff * (attempt + 1)))
                logger.info(f"  [!] SEC rate limited (429). Sleeping for {sleep_time}s before retry...")
                time.sleep(sleep_time)
                continue
            resp.raise_for_status()
            return resp
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt == retries - 1:
                raise e
            sleep_time = backoff * (2 ** attempt)
            logger.info(f"  [!] SEC Request failed: {e}. Retrying in {sleep_time}s...")
            time.sleep(sleep_time)
    raise requests.exceptions.RequestException("Request failed after retries")


def fetch_treasury_yield():
    """Fetch the 10-Year US Treasury yield dynamically from yfinance (^TNX)."""
    try:
        tnx = yf.Ticker("^TNX")
        # Try a few options to get the most recent price
        yield_val = tnx.info.get("previousClose") or tnx.info.get("regularMarketPrice") or tnx.info.get("open")
        if yield_val is not None:
            # yfinance returns it as a percentage (e.g. 4.23 for 4.23%)
            return float(yield_val) / 100.0
    except Exception as e:
        logger.info(f"  [!] Failed to fetch Treasury yield: {e}")
    # Fallback to a sensible long-term average (e.g. 4.2%)
    return 0.042


def fetch_vix():
    """Fetch current VIX index to scale Equity Risk Premium."""
    try:
        vix = yf.Ticker("^VIX")
        val = vix.info.get("previousClose") or vix.info.get("regularMarketPrice") or vix.info.get("open")
        if val is not None:
            return float(val)
    except Exception:
        pass
    return 15.0  # Safe historical baseline

def fetch_hyg_yield():
    """Fetch HYG (High Yield Bond ETF) yield to proxy macroeconomic cost of debt."""
    try:
        hyg = yf.Ticker("HYG")
        # yfinance dividend yield is usually decimal, e.g. 0.055 for 5.5%
        yield_val = hyg.info.get("dividendYield") or hyg.info.get("trailingAnnualDividendYield")
        if yield_val is not None:
            return float(yield_val)
    except Exception:
        pass
    return 0.065  # Safe historical high-yield average

def calculate_capm_wacc(info, financials, balance_sheet, tnx_yield=None):
    """
    Calculate the Weighted Average Cost of Capital (WACC) using CAPM for Cost of Equity.
    """
    if tnx_yield is None:
        tnx_yield = fetch_treasury_yield()
        
    rf = tnx_yield
    
    # Base ERP is 5.5%. Scale up if VIX > 20 (fear). Cap ERP at 10%.
    vix = fetch_vix()
    erp = 0.055
    if vix > 20:
        erp = min(0.10, 0.055 + (vix - 20) * 0.001)
    
    # 1. Cost of Equity
    try:
        beta = float(info.get("beta", 1.0))
        if pd.isna(beta) or beta <= 0:
            beta = 1.0
    except (ValueError, TypeError):
        beta = 1.0
    cost_of_equity = rf + beta * erp
    
    # 2. Cost of Debt & Tax Rate
    macro_debt_yield = fetch_hyg_yield()
    cost_of_debt = max(rf + 0.015, macro_debt_yield)  # Dynamic macro corporate debt proxy
    tax_rate = 0.21  # Default corporate tax rate
    
    # Helper to retrieve index value case-insensitively
    def val_fin(df, keys, col=0):
        if df is None or df.empty or len(df.columns) <= col: return None
        for k in keys:
            for idx in df.index:
                if k.lower() == str(idx).strip().lower():
                    v = df.loc[idx].iloc[col]
                    return None if pd.isna(v) else float(v)
        return None

    # Estimate Tax Rate from financials
    try:
        pretax_income = val_fin(financials, ["Pretax Income", "Income Before Tax"])
        tax_expense = val_fin(financials, ["Tax Provision", "Income Tax Expense"])
        if pretax_income and tax_expense and pretax_income > 0:
            computed_tax_rate = abs(tax_expense) / pretax_income
            if 0 <= computed_tax_rate < 0.50:
                tax_rate = computed_tax_rate
    except Exception:
        pass

    # Estimate Cost of Debt from financials (Interest Expense / Total Debt)
    total_debt = info.get("totalDebt", 0) or 0
    try:
        interest_expense = val_fin(financials, ["Interest Expense", "Interest Expense Debt"])
        if interest_expense and total_debt and total_debt > 0:
            computed_cost_of_debt = abs(interest_expense) / total_debt
            if rf <= computed_cost_of_debt < 0.20:
                cost_of_debt = computed_cost_of_debt
    except Exception:
        pass

    # 3. Capital Structure Weights
    market_cap = info.get("marketCap", 0) or 0
    equity_val = market_cap
    debt_val = total_debt
    
    total_val = equity_val + debt_val
    if total_val > 0:
        w_e = equity_val / total_val
        w_d = debt_val / total_val
    else:
        w_e = 1.0
        w_d = 0.0

    wacc = w_e * cost_of_equity + w_d * cost_of_debt * (1.0 - tax_rate)
    wacc = max(0.06, min(0.15, wacc))
    
    return {
        "wacc": wacc,
        "cost_of_equity": cost_of_equity,
        "cost_of_debt": cost_of_debt,
        "tax_rate": tax_rate,
        "weight_equity": w_e,
        "weight_debt": w_d,
        "risk_free_rate": rf,
        "beta": beta
    }


def fetch_sec_edgar_data(ticker_symbol):
    """Fetch SEC company submissions and XBRL companyfacts for direct 10-K/10-Q sourcing."""
    headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"}
    lookup_headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    ticker_upper = ticker_symbol.upper().strip()
    try:
        logger.info("   Fetching SEC EDGAR companyfacts...")
        lookup_resp = _sec_request_with_retry(SEC_TICKER_URL, headers=lookup_headers, timeout=15)
        lookup = lookup_resp.json()

        match = None
        for row in lookup.values():
            if str(row.get("ticker", "")).upper() == ticker_upper:
                match = row
                break
        if not match:
            return {"available": False, "error": f"No SEC ticker match for {ticker_upper}"}

        cik = str(match.get("cik_str")).zfill(10)
        submissions_resp = _sec_request_with_retry(SEC_SUBMISSIONS_URL.format(cik=cik), headers=headers, timeout=20)
        submissions = submissions_resp.json()

        facts_resp = _sec_request_with_retry(SEC_COMPANYFACTS_URL.format(cik=cik), headers=headers, timeout=25)
        companyfacts = facts_resp.json()

        recent = submissions.get("filings", {}).get("recent", {})
        recent_filings = []
        forms = recent.get("form", [])
        for idx, form in enumerate(forms):
            if form not in ["10-K", "10-Q"]:
                continue
            recent_filings.append({
                "form": form,
                "filing_date": recent.get("filingDate", [None])[idx],
                "report_date": recent.get("reportDate", [None])[idx],
                "accession_number": recent.get("accessionNumber", [None])[idx],
                "primary_document": recent.get("primaryDocument", [None])[idx],
            })
            if len(recent_filings) >= 8:
                break

        facts_summary = {
            "revenue": _latest_fact_value(companyfacts, "us-gaap", [
                "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet", 
                "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", 
                "RevenuesNetOfInterestExpense", "RegulatedAndUnregulatedOperatingRevenue"
            ]),
            "net_income": _latest_fact_value(companyfacts, "us-gaap", [
                "NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "IncomeLossFromContinuingOperations"
            ]),
            "assets": _latest_fact_value(companyfacts, "us-gaap", ["Assets"]),
            "liabilities": _latest_fact_value(companyfacts, "us-gaap", ["Liabilities"]),
            "stockholders_equity": _latest_fact_value(companyfacts, "us-gaap", [
                "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "PartnersCapital"
            ]),
            "operating_cash_flow": _latest_fact_value(companyfacts, "us-gaap", [
                "NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"
            ]),
            "capex": _latest_fact_value(companyfacts, "us-gaap", [
                "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets", "PaymentsToAcquireBusinessesGross", "PaymentsForCapitalImprovements"
            ]),
            "eps_diluted": _latest_fact_value(companyfacts, "us-gaap", [
                "EarningsPerShareDiluted", "NetIncomeLossPerOutstandingUnrestrictedShareDiluted", "IncomeLossFromContinuingOperationsPerDilutedShare"
            ]),
            "shares_outstanding": _latest_fact_value(companyfacts, "us-gaap", [
                "CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"
            ]),
        }

        return {
            "available": True,
            "cik": cik,
            "company_name": match.get("title"),
            "source_urls": {
                "ticker_lookup": SEC_TICKER_URL,
                "submissions": SEC_SUBMISSIONS_URL.format(cik=cik),
                "companyfacts": SEC_COMPANYFACTS_URL.format(cik=cik),
            },
            "recent_filings": recent_filings,
            "facts_summary": facts_summary,
            "raw": {
                "submissions": submissions,
                "companyfacts": companyfacts,
            }
        }
    except Exception as e:
        logger.info(f"  [!] SEC EDGAR fetch failed: {e}")
        return {"available": False, "error": str(e)}


def build_source_metadata(
    ticker_symbol, history_1y, history_5y, financials, balance_sheet,
    cashflow, quarterly_financials, quarterly_balance_sheet, quarterly_cashflow,
    earnings_dates, earnings_history, recommendations, news_sentiment, peers_data,
    sec_data=None, raw_snapshot_paths=None
):
    """Describe data provenance so reports can show what was fetched and from where."""
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ticker": ticker_symbol.upper(),
        "providers": {
            "market_data": "Yahoo Finance via yfinance",
            "financial_statements": "Yahoo Finance via yfinance",
            "sec_filings": "SEC EDGAR submissions and companyfacts APIs",
            "analyst_estimates": "Yahoo Finance via yfinance",
            "news_sentiment": "Alpha Vantage NEWS_SENTIMENT API",
            "ai_analysis": "Groq OpenAI-compatible chat completions",
            "local_models": "Local Python valuation and technical models"
        },
        "freshness": {
            "price_history_1y_last_date": _latest_index_date(history_1y),
            "price_history_5y_last_date": _latest_index_date(history_5y),
            "annual_financial_statement_dates": _statement_dates(financials),
            "quarterly_income_statement_dates": _statement_dates(quarterly_financials),
            "quarterly_balance_sheet_dates": _statement_dates(quarterly_balance_sheet),
            "quarterly_cashflow_dates": _statement_dates(quarterly_cashflow),
            "sec_recent_filings": [
                f"{f.get('form')} {f.get('filing_date')}" for f in (sec_data or {}).get("recent_filings", [])[:4]
            ],
        },
        "availability": {
            "history_1y_rows": int(len(history_1y)) if history_1y is not None else 0,
            "history_5y_rows": int(len(history_5y)) if history_5y is not None else 0,
            "annual_financials": bool(financials is not None and not financials.empty),
            "annual_balance_sheet": bool(balance_sheet is not None and not balance_sheet.empty),
            "annual_cashflow": bool(cashflow is not None and not cashflow.empty),
            "quarterly_financials": bool(quarterly_financials is not None and not quarterly_financials.empty),
            "quarterly_balance_sheet": bool(quarterly_balance_sheet is not None and not quarterly_balance_sheet.empty),
            "quarterly_cashflow": bool(quarterly_cashflow is not None and not quarterly_cashflow.empty),
            "earnings_dates": bool(earnings_dates is not None and not earnings_dates.empty),
            "earnings_history": bool(earnings_history is not None and not earnings_history.empty),
            "recommendations": bool(recommendations is not None and not recommendations.empty),
            "news_items": len(news_sentiment) if isinstance(news_sentiment, list) else 0,
            "peer_count": len(peers_data) if isinstance(peers_data, list) else 0,
            "sec_edgar": bool(sec_data and sec_data.get("available")),
            "raw_snapshots": raw_snapshot_paths or {},
        },
        "limitations": [
            "Yahoo Finance/yfinance fields can be revised, delayed, missing, or restated.",
            "SEC companyfacts is direct filing data but concept mappings can differ across issuers and periods.",
            "Alpha Vantage news sentiment may omit articles or classify sentiment differently from market consensus.",
            "Local valuation models are scenario tools, not audited fair-value opinions.",
            "AI analysis must be treated as commentary over the sourced dataset, not as an independent source of facts."
        ]
    }


def compute_rsi(series, period=14):
    """Compute Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    # If both avg_gain and avg_loss are exactly 0, rs is NaN. Default to 50.
    rsi = rsi.fillna(50)
    return rsi


def compute_macd(series, fast=12, slow=26, signal=9):
    """Compute MACD, Signal line, and Histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_technical_indicators(df):
    """Add technical indicators to a price DataFrame."""
    close = df["Close"]

    # Simple Moving Averages
    for window in SMA_WINDOWS:
        df[f"SMA_{window}"] = close.rolling(window=window).mean()

    # RSI
    df["RSI"] = compute_rsi(close, RSI_PERIOD)

    # MACD
    df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = compute_macd(
        close, MACD_FAST, MACD_SLOW, MACD_SIGNAL
    )

    # Bollinger Bands (20-day)
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    df["BB_Upper"] = sma20 + (std20 * 2)
    df["BB_Lower"] = sma20 - (std20 * 2)

    # EMA 20
    df["EMA_20"] = close.ewm(span=20, adjust=False).mean()

    # Daily returns
    df["Daily_Return"] = close.pct_change()

    # Cumulative returns
    df["Cumulative_Return"] = (1 + df["Daily_Return"]).cumprod() - 1

    return df


def compute_key_metrics(info, history, quarterly_financials=None):
    """Compute additional key metrics from raw data."""
    metrics = {}
    confidence = {}

    # Price metrics
    close = history["Close"]
    metrics["current_price"] = float(close.iloc[-1]) if len(close) > 0 else 0
    metrics["price_change_1d"] = float(close.pct_change().iloc[-1] * 100) if len(close) > 1 else 0
    metrics["high_52w"] = float(close.tail(252).max()) if len(close) >= 252 else float(close.max())
    metrics["low_52w"] = float(close.tail(252).min()) if len(close) >= 252 else float(close.min())
    for key in ["current_price", "price_change_1d", "high_52w", "low_52w"]:
        confidence[key] = _confidence("Yahoo Finance price history via yfinance", "reported")

    # Volatility
    daily_returns = close.pct_change().dropna()
    vol = daily_returns.std() * np.sqrt(252) * 100 if len(daily_returns) > 1 else 0.0
    metrics["volatility_annual"] = float(vol) if pd.notna(vol) else 0.0
    confidence["volatility_annual"] = _confidence("Yahoo Finance price history via yfinance", "derived", "Annualized from daily returns")

    # Advanced Options-Implied Volatility
    implied_vol = info.get("impliedVolatility")
    if implied_vol and not pd.isna(implied_vol):
        metrics["implied_volatility"] = float(implied_vol)
        confidence["implied_volatility"] = _confidence("Yahoo Finance options chain", "reported", "Market forward-looking implied volatility")

    # Performance
    if len(close) >= 5:
        metrics["return_1w"] = float((close.iloc[-1] / close.iloc[-5] - 1) * 100)
        confidence["return_1w"] = _confidence("Yahoo Finance price history via yfinance", "derived")
    if len(close) >= 21:
        metrics["return_1m"] = float((close.iloc[-1] / close.iloc[-21] - 1) * 100)
        confidence["return_1m"] = _confidence("Yahoo Finance price history via yfinance", "derived")
    if len(close) >= 63:
        metrics["return_3m"] = float((close.iloc[-1] / close.iloc[-63] - 1) * 100)
        confidence["return_3m"] = _confidence("Yahoo Finance price history via yfinance", "derived")
    if len(close) >= 126:
        metrics["return_6m"] = float((close.iloc[-1] / close.iloc[-126] - 1) * 100)
        confidence["return_6m"] = _confidence("Yahoo Finance price history via yfinance", "derived")
    if len(close) >= 252:
        metrics["return_1y"] = float((close.iloc[-1] / close.iloc[-252] - 1) * 100)
        confidence["return_1y"] = _confidence("Yahoo Finance price history via yfinance", "derived")

    # From Yahoo info
    safe_keys = [
        "marketCap", "enterpriseValue", "trailingPE", "forwardPE", "priceToBook",
        "currentPrice", "regularMarketPrice", "previousClose", "priceToSalesTrailing12Months",
        "enterpriseToEbitda", "enterpriseToRevenue", "pegRatio",
        "dividendYield", "dividendRate", "payoutRatio", "fiveYearAvgDividendYield",
        "beta", "trailingEps", "forwardEps", "bookValue",
        "revenueGrowth", "earningsGrowth", "earningsQuarterlyGrowth",
        "revenuePerShare", "grossMargins", "ebitdaMargins",
        "profitMargins", "operatingMargins",
        "returnOnEquity", "returnOnAssets",
        "debtToEquity", "currentRatio", "quickRatio",
        "totalRevenue", "totalDebt", "totalCash", "totalCashPerShare",
        "ebitda", "freeCashflow", "operatingCashflow",
        "sector", "industry", "fullTimeEmployees", "country", "city",
        "longBusinessSummary", "shortName", "longName",
        "targetMeanPrice", "targetHighPrice", "targetLowPrice", "targetMedianPrice",
        "recommendationKey", "recommendationMean",
        "numberOfAnalystOpinions",
        "heldPercentInsiders", "heldPercentInstitutions",
        "shortRatio", "shortPercentOfFloat",
        "overallRisk", "auditRisk", "boardRisk", "compensationRisk", "shareHolderRightsRisk",
        "sharesOutstanding", "impliedVolatility"
    ]
    for key in safe_keys:
        metrics[key] = info.get(key, None)
        confidence[key] = _confidence("Yahoo Finance ticker.info via yfinance", "reported")

    div_rate = metrics.get("dividendRate")
    curr_price = metrics.get("current_price") or metrics.get("currentPrice") or metrics.get("regularMarketPrice")
    if div_rate and curr_price:
        computed_yield = div_rate / curr_price
        yahoo_yield = metrics.get("dividendYield")
        try:
            yahoo_yield_num = float(yahoo_yield) if yahoo_yield is not None else None
        except (TypeError, ValueError):
            yahoo_yield_num = None
        if yahoo_yield_num is None or abs(yahoo_yield_num - computed_yield) > 0.01:
            metrics["dividendYield_raw_yahoo"] = yahoo_yield
            metrics["dividendYield"] = computed_yield
            confidence["dividendYield"] = _confidence(
                "Yahoo dividendRate divided by current price",
                "derived",
                f"Yahoo raw dividendYield={yahoo_yield}; recomputed to avoid stale/mis-scaled yield"
            )

    # Yahoo Finance stores percentage-like fields as decimals (1.963 = 196.3%).
    # Keep the raw values for calculations, but also expose explicit percentage
    # fields so AI prompts and dashboards cannot misread the scale.
    percent_keys = [
        "revenueGrowth", "earningsGrowth", "earningsQuarterlyGrowth",
        "grossMargins", "ebitdaMargins", "profitMargins", "operatingMargins",
        "returnOnEquity", "returnOnAssets", "dividendYield", "payoutRatio",
        "heldPercentInsiders", "heldPercentInstitutions", "shortPercentOfFloat",
    ]
    for key in percent_keys:
        val = metrics.get(key)
        metrics[f"{key}_pct"] = float(val) * 100 if isinstance(val, (int, float)) and not pd.isna(val) else None
        confidence[f"{key}_pct"] = _confidence(
            confidence.get(key, {}).get("source", "Yahoo Finance via yfinance"),
            "derived",
            "Converted Yahoo decimal field into percentage points"
        )

    # Compute true TTM operating margin from quarterly statements to catch
    # cases where Yahoo's info['operatingMargins'] reports a single peak quarter.
    if quarterly_financials is not None and not quarterly_financials.empty:
        try:
            cols = quarterly_financials.columns[:4]  # Last 4 quarters
            _lookup = lambda name: sum(
                float(quarterly_financials.loc[idx, c])
                for c in cols
                for idx in quarterly_financials.index
                if str(idx).strip().lower() == name.lower()
                and not pd.isna(quarterly_financials.loc[idx, c])
            )
            ttm_revenue = _lookup("Total Revenue")
            ttm_op_income = _lookup("Operating Income")
            if ttm_revenue > 0 and ttm_op_income != 0:
                ttm_op_margin = ttm_op_income / ttm_revenue
                yahoo_op_margin = metrics.get("operatingMargins")
                if yahoo_op_margin is not None and abs(yahoo_op_margin - ttm_op_margin) > 0.01:
                    metrics["operatingMargins_yahoo_raw"] = yahoo_op_margin
                    metrics["operatingMargins"] = ttm_op_margin
                    metrics["operatingMargins_pct"] = ttm_op_margin * 100
                    confidence["operatingMargins"] = _confidence(
                        "Computed from quarterly financials (TTM sum of last 4 quarters)",
                        "derived",
                        f"Overrode Yahoo info operatingMargins={yahoo_op_margin:.4f} with TTM={ttm_op_margin:.4f}"
                    )
                    confidence["operatingMargins_pct"] = confidence["operatingMargins"]
        except Exception:
            pass  # Silently fall back to Yahoo's reported value

    # Fallback for sharesOutstanding (crucial for reverse DCF solver)
    shares_out = info.get("sharesOutstanding")
    if not shares_out:
        mc = info.get("marketCap")
        cp = metrics.get("current_price") or info.get("currentPrice")
        if mc and cp:
            shares_out = int(mc / cp)
            confidence["sharesOutstanding"] = _confidence("marketCap/current_price fallback", "fallback")
            info["sharesOutstanding"] = shares_out  # Inject for DCF and other models
    metrics["sharesOutstanding"] = shares_out
    confidence.setdefault("sharesOutstanding", _confidence("Yahoo Finance ticker.info via yfinance", "reported"))
    metrics["_confidence"] = confidence

    return metrics


def fetch_alpha_vantage_news(ticker_symbol):
    """Fetch news sentiment from Alpha Vantage."""
    if not ALPHA_VANTAGE_API_KEY:
        return []
    logger.info("  [+] Fetching Alpha Vantage news sentiment...")
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker_symbol}&apikey={ALPHA_VANTAGE_API_KEY}&limit=50"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if "feed" in data:
            return data["feed"]
    except Exception as e:
        logger.info(f"  [!] Failed to fetch Alpha Vantage news: {e}")
    return []

def get_starting_fcf(info, cashflow):
    """Determine the starting Free Cash Flow directly."""
    fcf = info.get("freeCashflow")
    if not fcf or pd.isna(fcf) or fcf <= 0:
        if not cashflow.empty and "Free Cash Flow" in cashflow.index:
            try:
                fcf = float(cashflow.loc["Free Cash Flow"].iloc[0])
            except Exception:
                fcf = 0
        else:
            fcf = 0
            
    # Forward EPS Cash Conversion Fallback:
    # Trailing FCF can be transiently negative/depressed for cyclical/growth companies.
    # We fallback to Forward EPS * SharesOutstanding (representing projected normalized Net Income)
    # to yield a sensible, forward-looking DCF base.
    if not fcf or fcf <= 0:
        forward_eps = info.get("forwardEps")
        shares = info.get("sharesOutstanding")
        if forward_eps and shares and forward_eps > 0 and shares > 0:
            fcf = float(forward_eps * shares)
            logger.info(f"   [!] Trailing FCF is negative/missing. Sourced forward EPS cash conversion fallback: ${fcf/1e9:.2f}B")
            
    return fcf


def calculate_dcf(info, cashflow, financials=None, balance_sheet=None):
    """Calculate a basic mathematical Discounted Cash Flow (DCF)."""
    try:
        logger.info("   Calculating DCF Valuation...")
        shares_out = info.get("sharesOutstanding")
        if not shares_out: return None
        
        fcf = get_starting_fcf(info, cashflow)
        if not fcf or fcf <= 0: return None
        
        wacc_info = calculate_capm_wacc(info, financials, balance_sheet)
        wacc = wacc_info["wacc"]
        
        # Check if we are starting from forward FCF
        forward_eps = info.get("forwardEps")
        is_forward_base = (forward_eps and fcf == (forward_eps * shares_out))
        
        if is_forward_base:
            # If starting from forward (already peak/high), project a sustainable conservative growth rate
            growth_rate_1_5 = 0.05
            growth_rate_6_10 = 0.03
        else:
            # Dynamically resolve from yfinance info to match Monte Carlo logic
            rev_growth_raw = info.get("revenueGrowth")
            if rev_growth_raw is None or pd.isna(rev_growth_raw):
                rev_growth_raw = 0.10
            # Cap growth rate between 5% and 20% for stable long-term baseline DCF models
            growth_rate_1_5 = max(0.05, min(0.20, rev_growth_raw))
            growth_rate_6_10 = max(0.02, growth_rate_1_5 * 0.70)
            
        terminal_growth = 0.025
        # Stage 2 Linear Decay setup
        decay_step = (growth_rate_1_5 - terminal_growth) / 6 if growth_rate_1_5 > terminal_growth else 0
        
        projected_fcf = []
        current_fcf = fcf
        npv = 0
        for i in range(1, 11):
            if i <= 5:
                gr = growth_rate_1_5
            else:
                # Stage 2: Linear interpolation (decay) from Year 5 growth down to Year 10 terminal growth
                gr = max(terminal_growth, growth_rate_1_5 - (decay_step * (i - 5)))
                
            current_fcf *= (1 + gr)
            pv = current_fcf / ((1 + wacc) ** (i - 0.5))  # Mid-year convention
            npv += pv
            
        terminal_value = (current_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
        terminal_pv = terminal_value / ((1 + wacc) ** 10)
        
        enterprise_value = npv + terminal_pv
        net_debt = (info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0)
        equity_value = enterprise_value - net_debt
        raw_fair_value_per_share = equity_value / shares_out
        fair_value_per_share = raw_fair_value_per_share

        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        forward_pe = info.get("forwardPE")
        earnings_growth = info.get("earningsGrowth") or 0
        valuation_basis = "FCF DCF"

        # Sanity-check the DCF against forward EPS. For cyclical companies, trailing
        # FCF can be stale exactly when forward EPS is most informative.
        if forward_eps and current_price and forward_pe and forward_eps > 0 and fair_value_per_share < current_price * 0.55:
            # Anchor to consensus forward PE rather than current spot multiple to preserve variance
            target_forward_multiple = forward_pe * 1.15 if earnings_growth > 0.15 else forward_pe
            target_forward_multiple = max(10.0, min(target_forward_multiple, 50.0))
            
            eps_implied_price = forward_eps * target_forward_multiple
            if eps_implied_price > fair_value_per_share:
                fair_value_per_share = eps_implied_price
                valuation_basis = "Forward EPS sanity-adjusted DCF"
        
        return {
            "implied_price": round(fair_value_per_share, 2),
            "raw_dcf_price": round(raw_fair_value_per_share, 2),
            "growth_rate": round(growth_rate_1_5 * 100, 1),
            "wacc_used": round(wacc*100, 1),
            "fcf_base": fcf,
            "terminal_growth": round(terminal_growth*100, 1),
            "valuation_basis": valuation_basis,
            "_confidence": {
                "implied_price": _confidence("Local Python DCF model", "estimated", valuation_basis),
                "raw_dcf_price": _confidence("Local Python DCF model", "estimated", "Unadjusted DCF output"),
                "fcf_base": _confidence("Yahoo Finance cashflow/forward EPS", "derived", "Uses forward EPS fallback when trailing FCF is stale")
            }
        }
    except Exception as e:
        logger.info(f"  [!] DCF Calculation Failed: {e}")
        return None


def calculate_monte_carlo_dcf(info, cashflow, iterations=500, financials=None, balance_sheet=None):
    """Run a Monte Carlo simulation of DCF prices."""
    import random
    try:
        shares_out = info.get("sharesOutstanding")
        if not shares_out: return None
        
        fcf = get_starting_fcf(info, cashflow)
        if not fcf or fcf <= 0: return None

        wacc_info = calculate_capm_wacc(info, financials, balance_sheet)
        wacc_base = wacc_info["wacc"]
        
        # Check if we are starting from forward FCF
        forward_eps = info.get("forwardEps")
        is_forward_base = (forward_eps and fcf == (forward_eps * shares_out))
        
        if is_forward_base:
            rev_growth_base = 0.05
        else:
            # Cap the revenue growth rate between 5% and 20% for stable simulation projections
            rev_growth_raw = info.get("revenueGrowth") or 0.10
            if pd.isna(rev_growth_raw) or rev_growth_raw is None:
                rev_growth_raw = 0.10
            rev_growth_base = max(0.05, min(0.20, rev_growth_raw))

        prices = []
        net_debt = (info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0)

        for _ in range(iterations):
            sim_wacc = max(0.06, random.normalvariate(wacc_base, 0.015))
            if is_forward_base:
                sim_growth_1_5 = max(0.01, random.normalvariate(rev_growth_base, 0.02))
                sim_growth_6_10 = max(0.01, sim_growth_1_5 * 0.7)
            else:
                sim_growth_1_5 = max(0.01, random.normalvariate(rev_growth_base, 0.04))
                sim_growth_6_10 = max(0.01, sim_growth_1_5 * 0.7)
                
            sim_term_growth = max(0.01, min(sim_wacc - 0.01, random.normalvariate(0.025, 0.005)))
            
            # Stage 2 Linear Decay setup
            decay_step = (sim_growth_1_5 - sim_term_growth) / 6 if sim_growth_1_5 > sim_term_growth else 0

            current_fcf = fcf
            npv = 0
            for i in range(1, 11):
                if i <= 5:
                    gr = sim_growth_1_5
                else:
                    gr = max(sim_term_growth, sim_growth_1_5 - (decay_step * (i - 5)))
                    
                current_fcf *= (1 + gr)
                pv = current_fcf / ((1 + sim_wacc) ** (i - 0.5))  # Mid-year convention
                npv += pv

            terminal_value = (current_fcf * (1 + sim_term_growth)) / (sim_wacc - sim_term_growth)
            terminal_pv = terminal_value / ((1 + sim_wacc) ** 10)

            enterprise_value = npv + terminal_pv
            equity_value = enterprise_value - net_debt
            sim_price = equity_value / shares_out
            if sim_price > 0:
                prices.append(sim_price)

        if not prices:
            return None

        prices.sort()
        
        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        forward_pe = info.get("forwardPE")
        earnings_growth = info.get("earningsGrowth") or 0
        forward_eps = info.get("forwardEps")
        valuation_basis = "FCF Monte Carlo"
        adjustment_applied = False

        p50_raw = prices[int(len(prices) * 0.5)]
        
        if forward_eps and current_price and forward_pe and forward_eps > 0 and 0 < p50_raw < current_price * 0.55:
            target_forward_multiple = forward_pe * 1.15 if earnings_growth > 0.15 else forward_pe
            target_forward_multiple = max(10.0, min(target_forward_multiple, 50.0))
            
            eps_implied_price = forward_eps * target_forward_multiple
            if eps_implied_price > p50_raw:
                scale_factor = eps_implied_price / p50_raw
                prices = [p * scale_factor for p in prices]
                valuation_basis = "Forward EPS sanity-adjusted Monte Carlo"
                adjustment_applied = True

        p10 = round(prices[int(len(prices) * 0.1)], 2)
        p50 = round(prices[int(len(prices) * 0.5)], 2)
        p90 = round(prices[int(len(prices) * 0.9)], 2)

        # Generate histogram bins
        p_low = prices[int(len(prices) * 0.02)]
        p_high = prices[int(len(prices) * 0.98)]
        bin_width = (p_high - p_low) / 12 if p_high > p_low else 1.0
        bins = []
        counts = []
        for b in range(12):
            b_start = p_low + b * bin_width
            b_end = b_start + bin_width
            cnt = sum(1 for p in prices if b_start <= p < b_end)
            bins.append(round((b_start + b_end) / 2, 2))
            counts.append(cnt)

        return {
            "p10": p10,
            "p50": p50,
            "p90": p90,
            "bins": bins,
            "counts": counts,
            "valuation_basis": valuation_basis,
            "adjustment_applied": adjustment_applied,
            "note": "Scaled to Forward EPS sanity check value" if adjustment_applied else "Based on Trailing FCF"
        }
    except Exception as e:
        logger.info(f"  [!] Monte Carlo Calculation Failed: {e}")
        return None


def calculate_cca(info, peers_data):
    """Calculate valuation implied by peer multiples."""
    try:
        shares = info.get("sharesOutstanding")
        eps = info.get("trailingEps")
        fwd_eps = info.get("forwardEps")
        rev = info.get("totalRevenue")
        bv = info.get("bookValue")
        
        curr_price = info.get("currentPrice") or info.get("previousClose") or 1.0

        if not shares: return None
        rev_per_share = rev / shares if rev else None

        pes = []
        pss = []
        pbs = []
        fwd_pes = []
        for p in peers_data:
            # P/E
            pe = p.get("pe")
            if isinstance(pe, (int, float)) and pe > 0:
                pes.append(pe)
            # P/S
            ps = p.get("ps")
            if isinstance(ps, (int, float)) and ps > 0:
                pss.append(ps)
            # P/B
            pb = p.get("pb")
            if isinstance(pb, (int, float)) and pb > 0:
                pbs.append(pb)
            # Forward P/E
            fwd_pe = p.get("fwd_pe")
            if isinstance(fwd_pe, (int, float)) and fwd_pe > 0:
                fwd_pes.append(fwd_pe)

        med_pe = float(np.median(pes)) if pes else None
        med_ps = float(np.median(pss)) if pss else None
        med_pb = float(np.median(pbs)) if pbs else None
        med_fwd_pe = float(np.median(fwd_pes)) if fwd_pes else None

        implied_pe = round(med_pe * eps, 2) if (med_pe and eps and eps > 0) else None
        implied_ps = round(med_ps * rev_per_share, 2) if (med_ps and rev_per_share and rev_per_share > 0) else None
        implied_pb = round(med_pb * bv, 2) if (med_pb and bv and bv > 1.0) else None
        implied_fwd_pe = round(med_fwd_pe * fwd_eps, 2) if (med_fwd_pe and fwd_eps and fwd_eps > 0) else None

        return {
            "peer_median_pe": round(med_pe, 2) if med_pe else None,
            "peer_median_ps": round(med_ps, 2) if med_ps else None,
            "peer_median_pb": round(med_pb, 2) if med_pb else None,
            "peer_median_fwd_pe": round(med_fwd_pe, 2) if med_fwd_pe else None,
            "implied_pe_price": implied_pe,
            "implied_ps_price": implied_ps,
            "implied_pb_price": implied_pb,
            "implied_fwd_pe_price": implied_fwd_pe,
            "target_pe": info.get("trailingPE"),
            "target_ps": info.get("priceToSalesTrailing12Months"),
            "target_pb": info.get("priceToBook"),
            "target_fwd_pe": info.get("forwardPE"),
        }
    except Exception as e:
        logger.info(f"  [!] CCA Calculation Failed: {e}")
        return None


def calculate_ddm(info):
    """Calculate Gordon Growth DDM value."""
    try:
        div_rate = info.get("dividendRate", 0) or 0
        try:
            beta = float(info.get("beta", 1.0))
            if pd.isna(beta) or beta <= 0:
                beta = 1.0
        except (ValueError, TypeError):
            beta = 1.0
        risk_free = 0.043 # 10Y US Treasury
        equity_risk_premium = 0.055 # ERP
        cost_of_equity = risk_free + beta * equity_risk_premium
        
        if div_rate > 0:
            payout = info.get("payoutRatio", 0.3) or 0.3
            roe = info.get("returnOnEquity", 0.15) or 0.15
            # Growth rate = ROE * (1 - Payout Ratio)
            g = min(cost_of_equity - 0.015, max(0.01, roe * (1 - payout)))
            ddm_price = (div_rate * (1 + g)) / (cost_of_equity - g)
            # Restrict applicability: DDM is meaningful only for mature
            # dividend payers, not growth stocks with token payouts.
            curr_price_ddm = info.get("currentPrice") or info.get("previousClose") or 1.0
            div_yield = div_rate / curr_price_ddm if curr_price_ddm else 0
            is_applicable = div_yield >= 0.005 or payout >= 0.10
            msg = None if is_applicable else (
                f"DDM computed but not weighted: dividend yield ({div_yield*100:.2f}%) and "
                f"payout ratio ({payout*100:.1f}%) are below the thresholds for a meaningful "
                "income-based valuation. This is a growth stock with a token dividend."
            )
            result = {
                "dividend_rate": div_rate,
                "cost_of_equity": round(cost_of_equity * 100, 2),
                "growth_rate": round(g * 100, 2),
                "implied_price": round(ddm_price, 2),
                "payout_ratio": round(payout * 100, 1),
                "is_applicable": is_applicable
            }
            if msg:
                result["message"] = msg
            return result
        else:
            return {
                "dividend_rate": 0.0,
                "cost_of_equity": round(cost_of_equity * 100, 2),
                "growth_rate": 0.0,
                "implied_price": None,
                "is_applicable": False,
                "message": "Company does not pay dividends. DDM model is not applicable."
            }
    except Exception as e:
        logger.info(f"  [!] DDM Calculation Failed: {e}")
        return None


def calculate_log_regression_trend(history_5y):
    """Calculate 5-year log-linear regression trend and channel bounds."""
    import math
    try:
        if history_5y.empty or len(history_5y) < 50:
            return None
        
        # Take weekly subsample (every 5th day)
        df = history_5y.iloc[::5].copy()
        
        prices = df["Close"].values
        valid_idx = prices > 0
        prices = prices[valid_idx]
        if len(prices) < 20: return None
        
        y = np.log(prices)
        x = np.arange(len(prices))
        
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        
        num = np.sum((x - x_mean) * (y - y_mean))
        den = np.sum((x - x_mean) ** 2)
        
        if den == 0: return None
        
        beta = num / den
        alpha = y_mean - beta * x_mean
        
        y_pred = alpha + beta * x
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        std_error = np.sqrt(ss_res / (len(prices) - 2)) if len(prices) > 2 else 0
        
        current_x = len(prices) - 1
        curr_pred_log = alpha + beta * current_x
        curr_actual = prices[-1]
        
        fair_price = math.exp(curr_pred_log)
        upper_price = math.exp(curr_pred_log + 1.5 * std_error)
        lower_price = math.exp(curr_pred_log - 1.5 * std_error)
        
        cagr = math.exp(beta * 52) - 1
        deviation_pct = ((curr_actual - fair_price) / fair_price) * 100
        
        if deviation_pct > 15:
            status = "OVERBOUGHT / ABOVE TREND"
        elif deviation_pct < -15:
            status = "UNDERVALUED / BELOW TREND"
        else:
            status = "FAIRLY VALUED / ON TREND"
            
        return {
            "cagr": round(cagr * 100, 2),
            "r_squared": round(r_squared, 3),
            "fair_price": round(fair_price, 2),
            "upper_channel": round(upper_price, 2),
            "lower_channel": round(lower_price, 2),
            "deviation_pct": round(deviation_pct, 2),
            "status": status,
            "current_price": round(curr_actual, 2)
        }
    except Exception as e:
        logger.info(f"  [!] Historical Regression Failed: {e}")
        return None


def fetch_peers_data(ticker_symbol, company_name):
    """Use AI to dynamically find competitors, then fetch their basic multiples."""
    logger.info("   Finding and analyzing peer group...")

    try:
        ticker_upper = ticker_symbol.upper().strip()
        PEER_OVERRIDES = {
            "MU": ["AVGO", "MRVL", "INTC", "NXPI", "ON"],
            "AAPL": ["MSFT", "GOOGL", "META", "AVGO"],
            "MSFT": ["AAPL", "GOOGL", "ORCL", "AMZN"],
            "NVDA": ["AMD", "INTC", "AVGO", "QCOM"],
            "AMD": ["NVDA", "INTC", "AVGO", "QCOM"],
            "INTC": ["AMD", "NVDA", "TXN", "ON"],
            "TSLA": ["F", "GM", "LCID", "RIVN"],
            "AMZN": ["WMT", "EBAY", "BABA", "TGT"],
            "GOOGL": ["MSFT", "META", "AMZN", "NFLX"],
            "META": ["GOOGL", "SNAP", "MSFT", "PINS"],
            "NFLX": ["DIS", "WBD", "PARA"]
        }

        peers = []
        if ticker_upper in PEER_OVERRIDES:
            peers = PEER_OVERRIDES[ticker_upper]
        elif GROQ_API_KEY:
            try:
                headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": f"Return a JSON object containing exactly 3 stock ticker symbols that are the closest direct public competitors to {ticker_symbol} ({company_name}). Format: {{\"peers\": [\"TICKER1\", \"TICKER2\", \"TICKER3\"]}}"}],
                    "response_format": {"type": "json_object"}
                }
                resp = requests.post(GROQ_BASE_URL, headers=headers, json=payload, timeout=10)
                data = resp.json()["choices"][0]["message"]["content"]
                peers = json.loads(data).get("peers", [])
            except Exception as e:
                logger.info(f"  [!] Failed to dynamically fetch peers via AI: {e}")
                peers = []
        else:
            return []

        peer_data = []
        for p in peers:
            t = yf.Ticker(p)
            try:
                i = t.info
            except Exception:
                i = {}
            peer_data.append({
                "ticker": p,
                "name": i.get("shortName", p),
                "pe": i.get("trailingPE", "N/A"),
                "fwd_pe": i.get("forwardPE", "N/A"),
                "ps": i.get("priceToSalesTrailing12Months", "N/A"),
                "pb": i.get("priceToBook", "N/A"),
                "margins": i.get("profitMargins", "N/A"),
                "rev_growth": i.get("revenueGrowth", "N/A"),
                "rev_growth_pct": (i.get("revenueGrowth") * 100) if isinstance(i.get("revenueGrowth"), (int, float)) else "N/A"
            })
        return peer_data
    except Exception as e:
        logger.info(f"  [!] Failed to fetch peers: {e}")
        return []

def get_insider_trades(ticker):
    """Extract top 10 most recent insider transactions."""
    try:
        logger.info("   Fetching Insider Transactions...")
        insiders = ticker.insider_transactions
        if insiders is None or insiders.empty:
            return []
        # Convert top 10 rows to dicts
        top_10 = insiders.head(10).copy()
        # Clean datetime types to strings for JSON
        for col in top_10.columns:
            if pd.api.types.is_datetime64_any_dtype(top_10[col]):
                top_10[col] = top_10[col].dt.strftime("%Y-%m-%d")
            
        records = []
        for _, row in top_10.iterrows():
            # handle NaN floats
            rec = {}
            for k, v in row.items():
                rec[str(k)] = None if pd.isna(v) else v
            records.append(rec)
        return records
    except Exception as e:
        logger.info(f"  [!] Failed to fetch insiders: {e}")
        return []

def calculate_financial_scores(info, financials, balance_sheet, cashflow):
    """
    Calculate Altman Z-Score and Piotroski F-Score dynamically from annual statements.
    """
    scores = {
        "altman_z": None,
        "altman_z_label": "N/A",
        "altman_z_color": "var(--text-muted)",
        "piotroski_f": None,
        "piotroski_f_label": "N/A",
        "piotroski_f_color": "var(--text-muted)",
        "beneish_m": None,
        "beneish_m_label": "N/A",
        "beneish_m_color": "var(--text-muted)"
    }
    
    try:
        def val(df, keys, col=0):
            if df.empty or len(df.columns) <= col: return 0
            for k in keys:
                for idx in df.index:
                    if k.lower() == str(idx).strip().lower():
                        v = df.loc[idx].iloc[col]
                        return 0 if pd.isna(v) else float(v)
            return 0

        # Altman Z-Score
        ta = val(balance_sheet, ["Total Assets", "TotalAssets"])
        tl = val(balance_sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities", "TotalLiabilities"])
        ca = val(balance_sheet, ["Total Current Assets", "Current Assets", "CurrentAssets", "TotalCurrentAssets"])
        cl = val(balance_sheet, ["Total Current Liabilities", "Current Liabilities", "CurrentLiabilities", "TotalCurrentLiabilities"])
        re = val(balance_sheet, ["Retained Earnings", "RetainedEarnings", "Accumulated Deficit"])
        ebit = val(financials, ["EBIT", "Operating Income", "OperatingIncome", "Ebit"])
        rev = val(financials, ["Total Revenue", "Revenue", "TotalRevenue"])
        mcap = info.get("marketCap", 0) or 0
        
        if ta > 0:
            a = (ca - cl) / ta
            b = re / ta
            c = ebit / ta
            d = mcap / tl if tl > 0 else 1.0
            e = rev / ta
            
            z = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 0.999 * e
            scores["altman_z"] = round(z, 2)
            scores["altman_x1"] = round(1.2 * a, 3)
            scores["altman_x2"] = round(1.4 * b, 3)
            scores["altman_x3"] = round(3.3 * c, 3)
            scores["altman_x4"] = round(0.6 * d, 3)
            scores["altman_x5"] = round(0.999 * e, 3)
            
            if z > 2.99:
                scores["altman_z_label"] = f"Safe ({z:.2f})"
                scores["altman_z_color"] = "var(--green)"
            elif z >= 1.81:
                scores["altman_z_label"] = f"Grey Zone ({z:.2f})"
                scores["altman_z_color"] = "var(--amber)"
            else:
                scores["altman_z_label"] = f"Distress ({z:.2f})"
                scores["altman_z_color"] = "var(--red)"
    except Exception as e:
        logger.info(f"  [!] Failed to calculate Altman Z-Score: {e}")
        
    try:
        if not financials.empty and len(financials.columns) >= 2 and not balance_sheet.empty and len(balance_sheet.columns) >= 2:
            f_score = 0
            
            ni_0 = val(financials, ["Net Income", "NetIncome"], 0)
            ni_1 = val(financials, ["Net Income", "NetIncome"], 1)
            if ni_0 > 0: f_score += 1
            
            ta_0 = val(balance_sheet, ["Total Assets", "TotalAssets"], 0)
            ta_1 = val(balance_sheet, ["Total Assets", "TotalAssets"], 1)
            roa_0 = ni_0 / ta_0 if ta_0 > 0 else 0
            roa_1 = ni_1 / ta_1 if ta_1 > 0 else 0
            if roa_0 > 0: f_score += 1
            
            cfo_0 = val(cashflow, ["Operating Cash Flow", "Cash Flow From Operations", "Net Income From Continuing Operations"], 0)
            cfo_1 = val(cashflow, ["Operating Cash Flow", "Cash Flow From Operations", "Net Income From Continuing Operations"], 1)
            if cfo_0 > 0: f_score += 1
            
            if cfo_0 > ni_0: f_score += 1
            
            ltd_0 = val(balance_sheet, ["Long Term Debt", "LongTermDebt"], 0)
            ltd_1 = val(balance_sheet, ["Long Term Debt", "LongTermDebt"], 1)
            lev_0 = ltd_0 / ta_0 if ta_0 > 0 else 0
            lev_1 = ltd_1 / ta_1 if ta_1 > 0 else 0
            if lev_0 < lev_1 or (ltd_0 == 0 and ltd_1 == 0): f_score += 1
            
            ca_0 = val(balance_sheet, ["Total Current Assets", "Current Assets", "CurrentAssets"], 0)
            cl_0 = val(balance_sheet, ["Total Current Liabilities", "Current Liabilities", "CurrentLiabilities"], 0)
            ca_1 = val(balance_sheet, ["Total Current Assets", "Current Assets", "CurrentAssets"], 1)
            cl_1 = val(balance_sheet, ["Total Current Liabilities", "Current Liabilities", "CurrentLiabilities"], 1)
            cr_0 = ca_0 / cl_0 if cl_0 > 0 else 0
            cr_1 = ca_1 / cl_1 if cl_1 > 0 else 0
            if cr_0 > cr_1: f_score += 1
            
            cs_0 = val(balance_sheet, ["Ordinary Shares Number", "Share Issued", "Common Stock", "CommonStock"], 0)
            cs_1 = val(balance_sheet, ["Ordinary Shares Number", "Share Issued", "Common Stock", "CommonStock"], 1)
            if cs_0 <= cs_1 and cs_0 > 0: f_score += 1
            
            rev_0 = val(financials, ["Total Revenue", "Revenue"], 0)
            rev_1 = val(financials, ["Total Revenue", "Revenue"], 1)
            cogs_0 = val(financials, ["Cost Of Revenue", "CostOfRevenue"], 0)
            cogs_1 = val(financials, ["Cost Of Revenue", "CostOfRevenue"], 1)
            gp_0 = val(financials, ["Gross Profit", "GrossProfit"], 0)
            gp_1 = val(financials, ["Gross Profit", "GrossProfit"], 1)
            
            gm_0 = gp_0 / rev_0 if rev_0 > 0 and gp_0 != 0 else ((rev_0 - cogs_0) / rev_0 if rev_0 > 0 else 0)
            gm_1 = gp_1 / rev_1 if rev_1 > 0 and gp_1 != 0 else ((rev_1 - cogs_1) / rev_1 if rev_1 > 0 else 0)
            
            if gm_0 > gm_1: f_score += 1
            
            at_0 = rev_0 / ta_0 if ta_0 > 0 else 0
            at_1 = rev_1 / ta_1 if ta_1 > 0 else 0
            if at_0 > at_1: f_score += 1
            
            scores["piotroski_f"] = f_score
            scores["piotroski_f_label"] = f"{f_score}/9"
            if f_score >= 8:
                scores["piotroski_f_color"] = "var(--green)"
            elif f_score >= 4:
                scores["piotroski_f_color"] = "var(--amber)"
            else:
                scores["piotroski_f_color"] = "var(--red)"
    except Exception as e:
        logger.info(f"  [!] Failed to calculate Piotroski F-Score: {e}")

    try:
        if not financials.empty and len(financials.columns) >= 2 and not balance_sheet.empty and len(balance_sheet.columns) >= 2:
            # Year 0 (current) and Year 1 (prior) values
            rec_0 = val(balance_sheet, ["Net Receivables", "Receivables", "Accounts Receivable", "AccountsReceivable"], 0)
            rec_1 = val(balance_sheet, ["Net Receivables", "Receivables", "Accounts Receivable", "AccountsReceivable"], 1)
            
            sales_0 = val(financials, ["Total Revenue", "Revenue", "TotalRevenue", "Operating Revenue"], 0)
            sales_1 = val(financials, ["Total Revenue", "Revenue", "TotalRevenue", "Operating Revenue"], 1)
            
            cogs_0 = val(financials, ["Cost Of Revenue", "CostOfRevenue", "Cost of Goods Sold"], 0)
            cogs_1 = val(financials, ["Cost Of Revenue", "CostOfRevenue", "Cost of Goods Sold"], 1)
            
            ca_0 = val(balance_sheet, ["Total Current Assets", "Current Assets", "CurrentAssets", "TotalCurrentAssets"], 0)
            ca_1 = val(balance_sheet, ["Total Current Assets", "Current Assets", "CurrentAssets", "TotalCurrentAssets"], 1)
            
            ppe_0 = val(balance_sheet, ["Net PPE", "Properties", "Property Plant and Equipment", "PropertyPlantEquipment", "Property Plant Equipment Net", "NetPropertyPlantEquipment"], 0)
            ppe_1 = val(balance_sheet, ["Net PPE", "Properties", "Property Plant and Equipment", "PropertyPlantEquipment", "Property Plant Equipment Net", "NetPropertyPlantEquipment"], 1)
            
            ta_0 = val(balance_sheet, ["Total Assets", "TotalAssets"], 0)
            ta_1 = val(balance_sheet, ["Total Assets", "TotalAssets"], 1)
            
            depr_0 = val(financials, ["Depreciation And Amortization", "Depreciation", "DepreciationAmortization", "Depreciation & Amortization", "Depreciation Amortization Depletion"], 0)
            depr_1 = val(financials, ["Depreciation And Amortization", "Depreciation", "DepreciationAmortization", "Depreciation & Amortization", "Depreciation Amortization Depletion"], 1)
            
            sga_0 = val(financials, ["Selling General and Administrative", "Selling General & Administrative", "SGA", "SellingGeneralAdministrative", "Selling General And Administration"], 0)
            sga_1 = val(financials, ["Selling General and Administrative", "Selling General & Administrative", "SGA", "SellingGeneralAdministrative", "Selling General And Administration"], 1)
            
            tl_0 = val(balance_sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities", "TotalLiabilities"], 0)
            tl_1 = val(balance_sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities", "TotalLiabilities"], 1)
            
            ni_0 = val(financials, ["Net Income", "NetIncome"], 0)
            cfo_0 = val(cashflow, ["Operating Cash Flow", "Cash Flow From Operations", "Net Income From Continuing Operations", "OperatingCashFlow", "Cash Flow From Continuing Operating Activities"], 0)

            # DSRI (Days Sales in Receivables Index)
            ratio_rec_0 = (rec_0 / sales_0) if sales_0 > 0 else 0
            ratio_rec_1 = (rec_1 / sales_1) if sales_1 > 0 else 0
            dsri = (ratio_rec_0 / ratio_rec_1) if ratio_rec_1 > 0 else 1.0

            # GMI (Gross Margin Index)
            margin_0 = ((sales_0 - cogs_0) / sales_0) if sales_0 > 0 else 0
            margin_1 = ((sales_1 - cogs_1) / sales_1) if sales_1 > 0 else 0
            gmi = (margin_1 / margin_0) if margin_0 > 0 else 1.0

            # AQI (Asset Quality Index)
            aq_0 = 1.0 - ((ca_0 + ppe_0) / ta_0) if ta_0 > 0 else 0
            aq_1 = 1.0 - ((ca_1 + ppe_1) / ta_1) if ta_1 > 0 else 0
            aqi = (aq_0 / aq_1) if aq_1 > 0 else 1.0

            # SGI (Sales Growth Index)
            sgi = (sales_0 / sales_1) if sales_1 > 0 else 1.0

            # DEPI (Depreciation Index)
            depr_rate_0 = (depr_0 / (depr_0 + ppe_0)) if (depr_0 + ppe_0) > 0 else 0
            depr_rate_1 = (depr_1 / (depr_1 + ppe_1)) if (depr_1 + ppe_1) > 0 else 0
            depi = (depr_rate_1 / depr_rate_0) if depr_rate_0 > 0 else 1.0

            # SGAI (SG&A Expenses Index)
            sga_ratio_0 = (sga_0 / sales_0) if sales_0 > 0 else 0
            sga_ratio_1 = (sga_1 / sales_1) if sales_1 > 0 else 0
            sgai = (sga_ratio_0 / sga_ratio_1) if sga_ratio_1 > 0 else 1.0

            # LVGI (Leverage Index)
            lev_0 = (tl_0 / ta_0) if ta_0 > 0 else 0
            lev_1 = (tl_1 / ta_1) if ta_1 > 0 else 0
            lvgi = (lev_0 / lev_1) if lev_1 > 0 else 1.0

            # TATA (Total Accruals to Total Assets)
            tata = ((ni_0 - cfo_0) / ta_0) if ta_0 > 0 else 0.0

            m_score = -4.84 + (0.92 * dsri) + (0.528 * gmi) + (0.404 * aqi) + (0.892 * sgi) + (0.115 * depi) - (0.172 * sgai) - (0.327 * lvgi) + (4.679 * tata)

            scores["beneish_m"] = round(m_score, 2)
            if m_score > -1.78:
                scores["beneish_m_label"] = f"High Risk ({m_score:.2f})"
                scores["beneish_m_color"] = "var(--red)"
            else:
                scores["beneish_m_label"] = f"Low Risk ({m_score:.2f})"
                scores["beneish_m_color"] = "var(--green)"
    except Exception as e:
        logger.info(f"  [!] Failed to calculate Beneish M-Score: {e}")

    try:
        # DuPont Analysis
        equity = val(balance_sheet, ["Stockholders Equity", "Total Stockholders Equity", "Total Equity", "StockholdersEquity"])
        if rev > 0 and ta > 0 and equity != 0:
            ni_0 = val(financials, ["Net Income", "NetIncome"], 0)
            # Use strictly annual profit margin for DuPont math exactness
            net_margin = ni_0 / rev if ni_0 else 0
            asset_turnover = rev / ta
            equity_multiplier = ta / equity
            roe_dupont = net_margin * asset_turnover * equity_multiplier
            
            reported_roe_raw = info.get("returnOnEquity")
            reported_roe_val = round(reported_roe_raw * 100, 2) if reported_roe_raw is not None else None
            computed_roe_val = round(roe_dupont * 100, 2)
            
            note = "DuPont ROE is calculated strictly from annual statements (FY); Yahoo reported ROE may use trailing twelve months (TTM) or recent quarter data."
            if equity < 0:
                note += " ⚠️ WARNING: Stockholders' Equity is negative, which inverts the Equity Multiplier and makes computed ROE negative. This typically occurs when a highly profitable company returns massive capital via buybacks and dividends, reducing book equity below zero."
            elif reported_roe_val is not None and abs(computed_roe_val - reported_roe_val) > 5.0:
                note = f"DuPont ROE of {computed_roe_val:.2f}% is calculated strictly from annual statements (FY). Yahoo's reported ROE of {reported_roe_val:.2f}% is based on Trailing Twelve Months (TTM) which captures recent quarters' earnings momentum."
                
            scores["dupont"] = {
                "net_margin": round(net_margin * 100, 2),
                "asset_turnover": round(asset_turnover, 2),
                "equity_multiplier": round(equity_multiplier, 2),
                "roe_computed": computed_roe_val,
                "reported_roe": reported_roe_val,
                "basis": "latest annual statement components",
                "note": note
            }
        else:
            scores["dupont"] = None
    except Exception as e:
        logger.info(f"  [!] Failed to calculate DuPont ROE: {e}")
        
    return scores


def fetch_stock_data(ticker_symbol, raw_output_dir=None):
    """
    Fetch all stock data for a given ticker.
    Returns a dict with all data needed for analysis.
    """
    logger.info(f"  > Downloading data for {ticker_symbol}...")

    ticker = yf.Ticker(ticker_symbol)
    raw_snapshot_paths = {}

    # Basic info
    try:
        info = ticker.info
    except Exception:
        info = {}

    # Price history
    logger.info("   Fetching price history...")
    history_1y = ticker.history(period=HISTORY_PERIOD_SHORT)
    history_5y = ticker.history(period=HISTORY_PERIOD_LONG)

    # Add technical indicators
    if not history_1y.empty:
        history_1y = compute_technical_indicators(history_1y.copy())
    if not history_5y.empty:
        history_5y = compute_technical_indicators(history_5y.copy())

    # Financial statements
    logger.info("   Fetching financial statements...")
    try:
        financials = ticker.financials
    except Exception:
        financials = pd.DataFrame()

    try:
        balance_sheet = ticker.balance_sheet
    except Exception:
        balance_sheet = pd.DataFrame()

    try:
        cashflow = ticker.cashflow
    except Exception:
        cashflow = pd.DataFrame()

    # Quarterly statements
    logger.info("   Fetching quarterly data...")
    try:
        quarterly_financials = ticker.quarterly_financials
    except Exception:
        quarterly_financials = pd.DataFrame()

    try:
        quarterly_balance_sheet = ticker.quarterly_balance_sheet
    except Exception:
        quarterly_balance_sheet = pd.DataFrame()

    try:
        quarterly_cashflow = ticker.quarterly_cashflow
    except Exception:
        quarterly_cashflow = pd.DataFrame()

    # Earnings data
    try:
        earnings_dates = ticker.earnings_dates
    except Exception:
        earnings_dates = pd.DataFrame()

    if earnings_dates.empty:
        try:
            cal = ticker.calendar
            if isinstance(cal, dict) and "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                est = cal.get("Earnings Average")
                if isinstance(dates, list):
                    rows = []
                    for dt in dates:
                        dt_str = dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt)
                        rows.append({"Date": dt_str, "EPS Estimate": est, "EPS Actual": None, "EPS Surprise %": None})
                    df = pd.DataFrame(rows)
                    if not df.empty:
                        df.set_index("Date", inplace=True)
                        earnings_dates = df
                        logger.info("   (Used ticker.calendar fallback for upcoming earnings dates)")
        except Exception as e:
            logger.info(f"   ⚠️ Fallback to ticker.calendar failed: {e}")

    try:
        earnings_history = ticker.earnings_history
    except Exception:
        earnings_history = pd.DataFrame()

    # Analyst recommendations
    logger.info("   Fetching analyst data...")
    try:
        recommendations = ticker.recommendations
    except Exception:
        recommendations = pd.DataFrame()

    # Fetch News from Alpha Vantage
    news_sentiment = fetch_alpha_vantage_news(ticker_symbol)

    # SEC EDGAR direct filing source
    sec_data = fetch_sec_edgar_data(ticker_symbol)

    # Compute key metrics
    key_metrics = compute_key_metrics(info, history_1y, quarterly_financials)

    # Company name
    company_name = info.get("longName") or info.get("shortName") or ticker_symbol
    
    # Premium Data (DCF, Peers, Insiders)
    dcf_data = calculate_dcf(info, cashflow, financials=financials, balance_sheet=balance_sheet)
    peers_data = fetch_peers_data(ticker_symbol, company_name)
    insider_trades = get_insider_trades(ticker)
    financial_scores = calculate_financial_scores(info, financials, balance_sheet, cashflow)

    # Advanced local quantitative models (zero AI tokens)
    logger.info("   Running local quantitative valuation models (zero AI tokens)...")
    mc_data = calculate_monte_carlo_dcf(info, cashflow, financials=financials, balance_sheet=balance_sheet)
    cca_data = calculate_cca(info, peers_data)
    ddm_data = calculate_ddm(info)
    regression_data = calculate_log_regression_trend(history_5y)
    
    advanced_models = {
        "monte_carlo": mc_data,
        "cca": cca_data,
        "ddm": ddm_data,
        "historical_regression": regression_data
    }

    source_metadata = build_source_metadata(
        ticker_symbol, history_1y, history_5y, financials, balance_sheet,
        cashflow, quarterly_financials, quarterly_balance_sheet, quarterly_cashflow,
        earnings_dates, earnings_history, recommendations, news_sentiment, peers_data,
        sec_data=sec_data, raw_snapshot_paths=raw_snapshot_paths
    )

    if raw_output_dir:
        sec_raw = sec_data.get("raw") if isinstance(sec_data, dict) else None
        raw_snapshot_paths["yahoo_info"] = _write_raw_snapshot(raw_output_dir, "yahoo_info.json", info)
        raw_snapshot_paths["price_history_1y"] = _write_raw_snapshot(raw_output_dir, "yahoo_history_1y.json", _df_snapshot(history_1y))
        raw_snapshot_paths["price_history_5y"] = _write_raw_snapshot(raw_output_dir, "yahoo_history_5y.json", _df_snapshot(history_5y))
        raw_snapshot_paths["quarterly_financials"] = _write_raw_snapshot(raw_output_dir, "yahoo_quarterly_financials.json", _df_snapshot(quarterly_financials))
        raw_snapshot_paths["quarterly_balance_sheet"] = _write_raw_snapshot(raw_output_dir, "yahoo_quarterly_balance_sheet.json", _df_snapshot(quarterly_balance_sheet))
        raw_snapshot_paths["quarterly_cashflow"] = _write_raw_snapshot(raw_output_dir, "yahoo_quarterly_cashflow.json", _df_snapshot(quarterly_cashflow))
        raw_snapshot_paths["earnings_dates"] = _write_raw_snapshot(raw_output_dir, "yahoo_earnings_dates.json", _df_snapshot(earnings_dates))
        raw_snapshot_paths["alpha_vantage_news"] = _write_raw_snapshot(raw_output_dir, "alpha_vantage_news.json", news_sentiment)
        raw_snapshot_paths["sec_submissions"] = _write_raw_snapshot(raw_output_dir, "sec_submissions.json", sec_raw.get("submissions", {}) if sec_raw else {})
        raw_snapshot_paths["sec_companyfacts"] = _write_raw_snapshot(raw_output_dir, "sec_companyfacts.json", sec_raw.get("companyfacts", {}) if sec_raw else {})
        source_metadata["availability"]["raw_snapshots"] = raw_snapshot_paths
        raw_snapshot_paths["source_metadata"] = _write_raw_snapshot(raw_output_dir, "source_metadata.json", source_metadata)
        source_metadata["availability"]["raw_snapshots"] = raw_snapshot_paths
        _write_raw_snapshot(raw_output_dir, "source_metadata.json", source_metadata)

    stock_data = {
        "ticker": ticker_symbol.upper(),
        "company_name": company_name,
        "source_metadata": source_metadata,
        "sec_data": {k: v for k, v in sec_data.items() if k != "raw"} if isinstance(sec_data, dict) else {},
        "info": info,
        "history_1y": history_1y,
        "history_5y": history_5y,
        "financials": financials,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "quarterly_financials": quarterly_financials,
        "quarterly_balance_sheet": quarterly_balance_sheet,
        "quarterly_cashflow": quarterly_cashflow,
        "earnings_dates": earnings_dates,
        "earnings_history": earnings_history,
        "recommendations": recommendations,
        "key_metrics": key_metrics,
        "news_sentiment": news_sentiment,
        "dcf_data": dcf_data,
        "peers_data": peers_data,
        "insider_trades": insider_trades,
        "financial_scores": financial_scores,
        "advanced_models": advanced_models,
    }

    logger.info(f"   Data loaded for {company_name}")
    return stock_data
