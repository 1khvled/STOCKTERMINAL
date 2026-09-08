"""Local JSON file database for the personal stock terminal.

Single-user, fully offline-friendly storage. Stock records live in
``output/database/<TICKER>.json`` and the portfolio in
``output/portfolio.json``. No cloud, no keys, no network.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from config import OUTPUT_DIR
except ImportError:
    from .config import OUTPUT_DIR

DB_DIR = Path(OUTPUT_DIR) / "database"
PORTFOLIO_PATH = Path(OUTPUT_DIR) / "portfolio.json"


def _safe_float(value, default=0.0):
    try:
        if value in [None, "", "N/A", "NA", "null"]:
            return default
        return float(value)
    except Exception:
        return default


def save_stock_record(ticker, data):
    ticker = ticker.upper().strip()
    try:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        path = DB_DIR / f"{ticker}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"[Local DB] Saved {ticker} to disk.")
        return True
    except Exception as e:
        logger.error(f"[Local DB] Failed to save {ticker}: {e}")
        return False


def load_stock_record(ticker):
    ticker = ticker.upper().strip()
    path = DB_DIR / f"{ticker}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[Local DB] Failed to load {ticker}: {e}")
        return None


def _catalog_row(data):
    metrics = data.get("key_metrics", {})
    dcf_data = data.get("dcf_data", {})
    scores = data.get("financial_scores", {})
    analysis = data.get("analysis", {})
    curr_price = _safe_float(metrics.get("current_price") or metrics.get("currentPrice"), 0.0)
    fair_mid = _safe_float((analysis.get("valuation_assessment") or {}).get("fair_value_mid") or dcf_data.get("implied_price"), 0.0)
    return {
        "ticker": (data.get("ticker") or "").upper(),
        "company_name": data.get("company_name", "N/A"),
        "sector": metrics.get("sector") or "N/A",
        "industry": metrics.get("industry") or "N/A",
        "verdict": analysis.get("verdict", "HOLD"),
        "current_price": curr_price,
        "fair_value_mid": fair_mid,
        "upside": ((fair_mid - curr_price) / curr_price) if curr_price else 0.0,
        "pe_ratio": _safe_float(metrics.get("trailingPE") or metrics.get("forwardPE"), 0.0),
        "altman_z": scores.get("altman_z", "N/A"),
        "altman_z_label": scores.get("altman_z_label", "Safe"),
        "piotroski_f": _safe_float(scores.get("piotroski_f"), None),
        "beneish_m": scores.get("beneish_m", "N/A"),
        "totalCash": _safe_float(metrics.get("totalCash"), 0.0),
        "totalDebt": _safe_float(metrics.get("totalDebt"), 0.0),
        "bookValue": _safe_float(metrics.get("bookValue"), 0.0),
        "debtToEquity": _safe_float(metrics.get("debtToEquity"), None),
        "currentRatio": _safe_float(metrics.get("currentRatio"), None),
        "quickRatio": _safe_float(metrics.get("quickRatio"), None),
        "marketCap": _safe_float(metrics.get("marketCap"), 0.0),
        "freeCashflow": _safe_float(metrics.get("freeCashflow"), 0.0),
        "totalRevenue": _safe_float(metrics.get("totalRevenue"), 0.0),
        "returnOnEquity": _safe_float(metrics.get("returnOnEquity"), None),
        "returnOnAssets": _safe_float(metrics.get("returnOnAssets"), None),
        "revenueGrowth": _safe_float(metrics.get("revenueGrowth"), None),
        "operatingMargins": _safe_float(metrics.get("operatingMargins"), None),
        "profitMargins": _safe_float(metrics.get("profitMargins"), None),
        "confidence": analysis.get("verdict_confidence", "N/A"),
        "generated_at": data.get("generated_at", ""),
    }


def catalog_rows():
    if not DB_DIR.exists():
        return []
    rows = []
    for path in DB_DIR.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                row = _catalog_row(data)
                if row["ticker"]:
                    rows.append(row)
        except Exception:
            pass
    rows.sort(key=lambda x: x["ticker"])
    return rows


def load_portfolio():
    if not PORTFOLIO_PATH.exists():
        return {"positions": [], "updated_at": None}
    try:
        with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("positions", []), list):
            raise ValueError("Invalid portfolio schema")
        return data
    except Exception:
        return {"positions": [], "updated_at": None}


def save_portfolio(positions):
    data = {"positions": positions, "updated_at": datetime.now(timezone.utc).isoformat()}
    PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data
