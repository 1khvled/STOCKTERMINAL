import random
from cot_scraper import get_all_cot_data

def get_assets_data():
    """
    Implements the Exact 'Assets Data' scoring matrix.
    Splits output into Currencies (Macro) and Equities/Commodities (Stocks).
    """
    macro_assets = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD']
    stock_assets = ['GOLD', 'RUSSELL', 'NASDAQ', 'S&P500', 'DOW', 'SILVER', 'NIKKEI', 'XAGUSD', 'BTC', 'ETH', 'DAX', 'OILCash', 'FR40']
    
    # Exact indicators from Excel
    events = [
        {"indicator": "CPI YoY", "actual": 3.4, "forecast": 3.4, "unit": "%"},
        {"indicator": "PPI MoM", "actual": 0.2, "forecast": 0.2, "unit": "%"},
        {"indicator": "Retail Sales MoM", "actual": 0.7, "forecast": 0.4, "unit": "%"},
        {"indicator": "GDP Growth Rate YoY", "actual": 3.0, "forecast": 3.0, "unit": "%"},
        {"indicator": "Unemployment Rate", "actual": 3.9, "forecast": 3.8, "unit": "%"},
        {"indicator": "Non Farm Payrolls", "actual": 303, "forecast": 212, "unit": "K"},
        {"indicator": "Interest Rates", "actual": 5.5, "forecast": 5.5, "unit": "%"}
    ]
    
    matrix = []
    for event in events:
        # Mock beat/miss logic for demo
        diff = event["actual"] - event["forecast"]
        if diff == 0:
            is_beat = random.choice([True, False])
        else:
            is_beat = diff > 0
            
        row = {
            "indicator": event["indicator"],
            "actual": event["actual"],
            "forecast": event["forecast"],
            "macro_scores": {},
            "stock_scores": {}
        }
        
        # Scoring logic (+1/-1)
        for asset in macro_assets:
            score = 1 if is_beat else -1
            if asset in ["JPY", "CHF"]: score = -score # Havens react inversely
            row["macro_scores"][asset] = score
            
        for asset in stock_assets:
            # Equities hate inflation/hot jobs
            if event["indicator"] in ["CPI YoY", "PPI MoM", "Non Farm Payrolls"]:
                score = -1 if is_beat else 1
            else:
                score = 1 if is_beat else -1
            row["stock_scores"][asset] = score
            
        matrix.append(row)
        
    return matrix

def get_top_setups():
    """
    Implements the 'TOP SETUPS' algorithmic ranking.
    Pair Score = Base Currency Score - Quote Currency Score.
    """
    currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
    
    # Generate mock base scores based on pseudo-live macro logic
    # In production this would pull from the assets_data sum
    base_scores = {
        "USD": 4,
        "EUR": -2,
        "GBP": 1,
        "JPY": -5,
        "AUD": 2,
        "CAD": 0,
        "CHF": 3,
        "NZD": -1
    }
    
    pairs = [
        ("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY"), 
        ("USD", "CHF"), ("AUD", "USD"), ("NZD", "USD"), 
        ("EUR", "GBP"), ("EUR", "JPY"), ("GBP", "JPY"),
        ("AUD", "JPY"), ("EUR", "AUD")
    ]
    
    results = []
    for base, quote in pairs:
        b_score = base_scores[base]
        q_score = base_scores[quote]
        pair_score = b_score - q_score
        
        # Determine Bias
        if pair_score >= 3: bias = "Strong Bull (Sim)"
        elif pair_score >= 1: bias = "Bullish (Sim)"
        elif pair_score <= -3: bias = "Strong Bear (Sim)"
        elif pair_score <= -1: bias = "Bearish (Sim)"
        else: bias = "Neutral (Sim)"
        
        results.append({
            "pair": f"{base}/{quote}",
            "base": base,
            "quote": quote,
            "base_score": b_score,
            "quote_score": q_score,
            "pair_score": pair_score,
            "bias": bias,
            "trend": random.choice([-1, 0, 1]),
            "seasonality": random.choice([-1, 0, 1]),
            "retail_sentiment": random.choice([-1, 1])
        })
        
    # Sort by absolute pair score strength
    results.sort(key=lambda x: abs(x["pair_score"]), reverse=True)
    return results

def get_sentiment_all():
    """
    Implements the 'Retail Sentiment ALL' board.
    Loops through all pairs, getting Long vs Short %.
    """
    pairs = [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD",
        "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY", "EUR/AUD", "GOLD", "SP500"
    ]
    
    results = []
    for pair in pairs:
        # Use pseudo-random seeded by pair to simulate live FXSSI feed
        random.seed(pair)
        long_pct = random.randint(20, 80)
        short_pct = 100 - long_pct
        
        if long_pct > 65:
            signal = "Bearish" # Retail is too long
        elif short_pct > 65:
            signal = "Bullish" # Retail is too short
        else:
            signal = "Mixed"
            
        results.append({
            "asset": pair,
            "long_pct": long_pct,
            "short_pct": short_pct,
            "signal": signal
        })
        
    # Sort by most extreme sentiment
    results.sort(key=lambda x: abs(50 - x["long_pct"]), reverse=True)
    return results
