import pickle
import json
import glob
from pathlib import Path

# Paths
cache_dir = Path("output/cache")
db_dir = Path("output/database")

if not cache_dir.exists() or not db_dir.exists():
    print("Cache or database directory does not exist.")
    exit(1)

cache_files = list(cache_dir.glob("*_raw_cache.pkl"))
print(f"Found {len(cache_files)} cache files.")

for cache_path in cache_files:
    ticker = cache_path.name.replace("_raw_cache.pkl", "").upper()
    db_path = db_dir / f"{ticker}.json"
    
    if db_path.exists():
        print(f"Syncing peers_data for {ticker}...")
        try:
            # Load raw data from pickle
            with open(cache_path, "rb") as f:
                raw_data = pickle.load(f)
            
            peers_data = raw_data.get("peers_data", [])
            print(f"  Found {len(peers_data)} peers in cache.")
            
            # Load database JSON
            with open(db_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)
            
            # Inject peers_data
            db_data["peers_data"] = peers_data
            
            # Save database JSON
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(db_data, f, indent=2, ensure_ascii=False)
                
            print(f"  Successfully synced peers_data for {ticker}.")
        except Exception as e:
            print(f"  Error syncing {ticker}: {e}")
    else:
        print(f"No JSON database found for {ticker} at {db_path}")
