import os
import json
from datetime import datetime
from config import MONGODB_URI, MONGODB_DB_NAME

# Fallback to local files if MONGODB_URI is not set
USE_DB = bool(MONGODB_URI)

if USE_DB:
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGODB_DB_NAME]
        stocks_collection = db["stocks"]
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        USE_DB = False

def get_stock(ticker):
    """Retrieve stock data from MongoDB or local JSON."""
    ticker = ticker.upper()
    if USE_DB:
        doc = stocks_collection.find_one({"ticker": ticker})
        if doc:
            doc.pop('_id', None)  # Remove mongo ID
            return doc
        return None
    else:
        # Local fallback
        from pathlib import Path
        import json
        path = Path(__file__).parent.parent / "output" / "database" / f"{ticker}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

def save_stock(ticker, data):
    """Save stock data to MongoDB or local JSON."""
    ticker = ticker.upper()
    if "ticker" not in data:
        data["ticker"] = ticker
        
    if USE_DB:
        stocks_collection.update_one(
            {"ticker": ticker},
            {"$set": data},
            upsert=True
        )
    else:
        from pathlib import Path
        import json
        out_dir = Path(__file__).parent.parent / "output" / "database"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / f"{ticker}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def get_recent_stocks_summary():
    """Returns a list of recent stocks with ticker, name, verdict."""
    stocks = []
    if USE_DB:
        cursor = stocks_collection.find({}, {"ticker": 1, "company_profile": 1, "ai_analysis": 1}).sort("_id", -1)
        for doc in cursor:
            ticker = doc.get("ticker", "UNKNOWN")
            
            company_name = f"{ticker} Corp"
            profile = doc.get("company_profile") or {}
            if isinstance(profile, dict) and profile.get("name"):
                company_name = profile.get("name")
                
            verdict = "HOLD"
            analysis = doc.get("ai_analysis") or {}
            if isinstance(analysis, dict) and analysis.get("verdict"):
                verdict = analysis.get("verdict")
                
            stocks.append({
                "ticker": ticker,
                "name": company_name,
                "verdict": verdict
            })
    else:
        # Local fallback using the old HTML scanning logic or JSON scanning
        from pathlib import Path
        import re
        output_dir = Path(__file__).parent.parent / "output"
        if output_dir.exists():
            for d in output_dir.iterdir():
                if d.is_dir() and d.name.upper() not in ["RAW"]:
                    ticker = d.name.upper()
                    html_file = d / f"{ticker}_dashboard.html"
                    if html_file.exists():
                        try:
                            with open(html_file, "r", encoding="utf-8") as f:
                                content = f.read(128000)
                            v_match = re.search(r'"verdict":\s*"([^"]+)"', content)
                            n_match = re.search(r'"company_name":\s*"([^"]+)"', content)
                            stocks.append({
                                "ticker": ticker,
                                "name": n_match.group(1) if n_match else f"{ticker} Corp",
                                "verdict": v_match.group(1) if v_match else "HOLD"
                            })
                        except Exception:
                            pass
    stocks.sort(key=lambda x: x["ticker"])
    return stocks
