import os
import json
import logging
import requests
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Load config
try:
    from config import SUPABASE_URL, SUPABASE_KEY, OUTPUT_DIR
except ImportError:
    from .config import SUPABASE_URL, SUPABASE_KEY, OUTPUT_DIR

IS_TEST_MODE = os.environ.get("STOCKER_TEST_MODE") == "1"

# Local file fallbacks for test mode
DB_DIR = Path(OUTPUT_DIR) / "database"
PORTFOLIO_PATH = Path(OUTPUT_DIR) / "portfolio.json"

def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def save_stock_record(ticker, data):
    ticker = ticker.upper().strip()
    
    # Always write to local file cache as well for legacy tool compatibility
    try:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        path = DB_DIR / f"{ticker}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"[Local DB Cache] Saved {ticker} to disk.")
    except Exception as e:
        logger.error(f"[Local DB Cache] Failed to write local cache: {e}")

    if IS_TEST_MODE or not SUPABASE_URL or not SUPABASE_KEY:
        return True

    url = f"{SUPABASE_URL}/rest/v1/stock_analyses"
    metrics = data.get("key_metrics", {})
    analysis = data.get("analysis", {})
    comp_name = data.get("company_name", ticker)
    verdict = analysis.get("verdict", "HOLD")
    confidence = analysis.get("verdict_confidence", 60)
    
    payload = {
        "ticker": ticker,
        "company_name": comp_name,
        "verdict": verdict,
        "verdict_confidence": int(confidence) if confidence is not None else 60,
        "generated_at": data.get("generated_at") or datetime.utcnow().isoformat() + "Z",
        "raw_data": data
    }
    
    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"[Supabase] Upserted analysis for {ticker}")
        return True
    except Exception as e:
        logger.error(f"[Supabase] Failed to save {ticker} to Supabase: {e}")
        return False

def load_stock_record(ticker):
    ticker = ticker.upper().strip()
    if IS_TEST_MODE or not SUPABASE_URL or not SUPABASE_KEY:
        path = DB_DIR / f"{ticker}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # Load from Supabase
    url = f"{SUPABASE_URL}/rest/v1/stock_analyses?ticker=eq.{ticker}&select=raw_data"
    data = None
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            data = rows[0].get("raw_data")
    except Exception as e:
        logger.error(f"[Supabase] Failed to load {ticker}: {e}")
        
    if data:
        # Update local file cache if it's missing or different
        try:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            path = DB_DIR / f"{ticker}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return data

    # Local fallback read
    path = DB_DIR / f"{ticker}.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def _safe_float(value, default=0.0):
    try:
        if value in [None, "", "N/A", "NA", "null"]:
            return default
        return float(value)
    except Exception:
        return default

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
        "generated_at": data.get("generated_at", "")
    }

def catalog_rows():
    if IS_TEST_MODE or not SUPABASE_URL or not SUPABASE_KEY:
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

    url = f"{SUPABASE_URL}/rest/v1/stock_analyses?select=raw_data"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        rows = []
        for item in resp.json():
            data = item.get("raw_data")
            if data:
                row = _catalog_row(data)
                if row["ticker"]:
                    rows.append(row)
        rows.sort(key=lambda x: x["ticker"])
        return rows
    except Exception as e:
        logger.error(f"[Supabase] Failed to fetch catalog: {e}")
        # fallback to local cache
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
    if IS_TEST_MODE or not SUPABASE_URL or not SUPABASE_KEY:
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

    url = f"{SUPABASE_URL}/rest/v1/portfolio?select=ticker,weight,updated_at"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        rows = resp.json()
        positions = [{"ticker": r["ticker"], "weight": float(r["weight"])} for r in rows]
        last_updated = max((r["updated_at"] for r in rows), default=None)
        return {"positions": positions, "updated_at": last_updated}
    except Exception as e:
        logger.error(f"[Supabase] Failed to load portfolio: {e}")
        # local read fallback
        if PORTFOLIO_PATH.exists():
            try:
                with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"positions": [], "updated_at": None}

def save_portfolio(positions):
    if IS_TEST_MODE or not SUPABASE_URL or not SUPABASE_KEY:
        data = {"positions": positions, "updated_at": datetime.utcnow().isoformat() + "Z"}
        PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    headers = _headers()
    # 1. Clear existing portfolio
    delete_url = f"{SUPABASE_URL}/rest/v1/portfolio?select=*"
    try:
        resp = requests.delete(delete_url, headers={**headers, "Prefer": "return=minimal"}, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"[Supabase] Failed to clear portfolio: {e}")

    # 2. Insert new positions
    if not positions:
        return {"positions": [], "updated_at": datetime.utcnow().isoformat() + "Z"}

    insert_url = f"{SUPABASE_URL}/rest/v1/portfolio"
    payload = []
    now_str = datetime.utcnow().isoformat() + "Z"
    for pos in positions:
        payload.append({
            "ticker": pos["ticker"].upper().strip(),
            "weight": float(pos["weight"]),
            "updated_at": now_str
        })
        
    try:
        resp = requests.post(insert_url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"[Supabase] Saved {len(positions)} portfolio items.")
    except Exception as e:
        logger.error(f"[Supabase] Failed to insert portfolio: {e}")
        
    # Write to local file as backup anyway
    data = {"positions": positions, "updated_at": now_str}
    try:
        with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
        
    return data
