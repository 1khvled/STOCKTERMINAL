import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""
=============================================================================
  OpenCode FREE MODEL BENCHMARKER
  Tests all available free models on a real stock-analysis JSON prompt
  and produces a ranked leaderboard.
=============================================================================
"""

import os, sys, time, json, re, concurrent.futures, statistics
from pathlib import Path
from dotenv import load_dotenv

# -- Load env --------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent / ".env")
API_KEY  = os.getenv("OPENCODE_API_KEY", "")
BASE_URL = "https://opencode.ai/zen/v1/chat/completions"

if not API_KEY:
    print("[FAIL]  OPENCODE_API_KEY not found in .env"); sys.exit(1)

try:
    import httpx
except ImportError:
    import subprocess, sys as _sys
    subprocess.run([_sys.executable, "-m", "pip", "install", "httpx"], check=True)
    import httpx

# -- Models to benchmark ---------------------------------------------------
MODELS = [
    ("MiniMax M3 Free",        "minimax-m3-free"),
    ("MiMo V2.5 Free",         "mimo-v2.5-free"),
    ("Nemotron Ultra Free",     "nemotron-3-ultra-free"),
    ("North Mini Code Free",    "north-mini-code-free"),
    ("Qwen3.6 Plus Free",       "qwen3.6-plus-free"),
    ("DeepSeek V4 Flash Free",  "deepseek-v4-flash-free"),  # current baseline
]

# -- Benchmark prompt ------------------------------------------------------
SYSTEM_PROMPT = """You are a ruthless, highly quantitative hedge fund analyst.
Output ONLY valid JSON. No markdown code fences. No preamble. First char must be `{`.
You must be highly expansive, verbose, and detailed. Write extensively."""

USER_PROMPT = """Analyze Apple Inc (AAPL) with the following data:
Current Price: $195.50 | P/E: 32.1x | Forward P/E: 28.4x | P/S: 8.2x | Revenue Growth: +4.9% YoY
Net Margin: 24.3% | Free Cash Flow: $101B | Debt/Equity: 1.87 | Beta: 1.22
Analyst Target: $215 (avg) | Short Interest: 0.8% | Insider Sells: $3.2B last 90d

Return this JSON exactly:
{
  "executive_summary": "3+ paragraph comprehensive thesis",
  "fundamental_analysis": {
    "revenue_quality": "detailed assessment",
    "margin_analysis": "detailed assessment",
    "balance_sheet": "detailed assessment",
    "fcf_analysis": "detailed assessment"
  },
  "valuation": {
    "valuation_grade": "OVERVALUED|FAIRLY VALUED|UNDERVALUED",
    "fair_value_low": 0.0,
    "fair_value_mid": 0.0,
    "fair_value_high": 0.0,
    "verdict": "STRONG BUY|BUY|HOLD|SELL|STRONG SELL",
    "verdict_confidence": 0,
    "valuation_narrative": "detailed explanation"
  },
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "catalysts": ["catalyst 1", "catalyst 2", "catalyst 3"]
}"""

# -- Scorer ----------------------------------------------------------------
REQUIRED_KEYS = [
    "executive_summary", "fundamental_analysis", "valuation", "key_risks", "catalysts"
]
NESTED_KEYS = {
    "fundamental_analysis": ["revenue_quality", "margin_analysis", "balance_sheet", "fcf_analysis"],
    "valuation": ["valuation_grade", "fair_value_low", "fair_value_mid", "fair_value_high",
                  "verdict", "verdict_confidence", "valuation_narrative"],
}
VALID_VERDICTS   = {"STRONG BUY","BUY","HOLD","SELL","STRONG SELL"}
VALID_GRADES     = {"OVERVALUED","FAIRLY VALUED","UNDERVALUED","DEEPLY OVERVALUED","DEEPLY UNDERVALUED"}

def score_response(raw: str, latency_ms: float) -> dict:
    """Return a scored breakdown dictionary."""
    scores = {
        "json_valid":         0,   # 25 pts
        "schema_complete":    0,   # 25 pts
        "content_quality":    0,   # 25 pts
        "speed":              0,   # 15 pts
        "verbosity":          0,   # 10 pts
        "total":              0,
        "notes":              [],
        "parsed":             None,
    }

    # Strip markdown fences if model disobeyed
    clean = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", clean)
    if m:
        clean = m.group(1).strip()
        scores["notes"].append("[WARN]  Wrapped in markdown fence (minor penalty)")
        scores["json_valid"] -= 3

    try:
        parsed = json.loads(clean)
        scores["json_valid"] += 25
        scores["parsed"] = parsed
    except Exception as e:
        scores["notes"].append(f"[FAIL]  JSON parse failed: {e}")
        scores["total"] = 0
        return scores

    # Schema completeness (25 pts)
    schema_pts = 0
    for k in REQUIRED_KEYS:
        if k in parsed:
            schema_pts += 3
        else:
            scores["notes"].append(f"[FAIL]  Missing top-level key: {k}")
    for parent, children in NESTED_KEYS.items():
        parent_obj = parsed.get(parent, {})
        if isinstance(parent_obj, dict):
            for ck in children:
                if ck in parent_obj:
                    schema_pts += 1
                else:
                    scores["notes"].append(f"[WARN]  Missing nested key: {parent}.{ck}")
    scores["schema_complete"] = min(schema_pts, 25)

    # Content quality (25 pts)
    quality_pts = 0
    val = parsed.get("valuation", {})
    verdict = str(val.get("verdict","")).upper().strip()
    grade   = str(val.get("valuation_grade","")).upper().strip()
    conf    = val.get("verdict_confidence", -1)

    if verdict in VALID_VERDICTS:   quality_pts += 5
    else: scores["notes"].append(f"[WARN]  Invalid verdict: '{verdict}'")

    if grade in VALID_GRADES:       quality_pts += 5
    else: scores["notes"].append(f"[WARN]  Invalid grade: '{grade}'")

    try:
        fv_low  = float(val.get("fair_value_low",  0))
        fv_mid  = float(val.get("fair_value_mid",  0))
        fv_high = float(val.get("fair_value_high", 0))
        if 50 < fv_low < fv_mid < fv_high < 1000:
            quality_pts += 5
        else:
            scores["notes"].append("[WARN]  Fair values out of sensible range or ordering wrong")
    except: scores["notes"].append("[FAIL]  Fair values not numeric")

    try:
        c = int(conf)
        if 0 <= c <= 100: quality_pts += 5
        else: scores["notes"].append("[WARN]  Confidence out of 0-100 range")
    except: scores["notes"].append("[FAIL]  Confidence not an integer")

    risks     = parsed.get("key_risks",    [])
    catalysts = parsed.get("catalysts",    [])
    if isinstance(risks, list) and len(risks) >= 3:     quality_pts += 2
    if isinstance(catalysts, list) and len(catalysts) >= 3: quality_pts += 3

    scores["content_quality"] = min(quality_pts, 25)

    # Speed scoring (15 pts) – under 8s = full marks, degrades linearly to 60s
    lat_s = latency_ms / 1000
    if lat_s <= 8:
        speed_pts = 15
    elif lat_s <= 60:
        speed_pts = max(0, int(15 - (lat_s - 8) * 15 / 52))
    else:
        speed_pts = 0
    scores["speed"] = speed_pts

    # Verbosity (10 pts) – count total chars of text fields
    def count_chars(obj):
        if isinstance(obj, str):  return len(obj)
        if isinstance(obj, list): return sum(count_chars(i) for i in obj)
        if isinstance(obj, dict): return sum(count_chars(v) for v in obj.values())
        return 0
    total_chars = count_chars(parsed)
    verbosity_pts = min(10, total_chars // 200)  # 10 pts per 2000 chars
    scores["verbosity"] = verbosity_pts

    scores["total"] = (
        scores["json_valid"] +
        scores["schema_complete"] +
        scores["content_quality"] +
        scores["speed"] +
        scores["verbosity"]
    )
    return scores

# -- API caller ------------------------------------------------------------
def call_model(name: str, model_id: str) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
    }
    body = {
        "model": model_id,
        "max_tokens": 3000,
        "temperature": 0.25,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_PROMPT},
        ],
    }
    t0 = time.time()
    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(BASE_URL, headers=headers, json=body)
        latency_ms = (time.time() - t0) * 1000

        if resp.status_code != 200:
            return {
                "name": name, "model_id": model_id,
                "status": "ERROR", "http_code": resp.status_code,
                "error": resp.text[:300], "latency_ms": latency_ms,
                "scores": None
            }

        data  = resp.json()
        raw   = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        scores = score_response(raw, latency_ms)

        return {
            "name": name, "model_id": model_id,
            "status": "OK", "http_code": 200,
            "latency_ms": latency_ms,
            "prompt_tokens":     usage.get("prompt_tokens", "?"),
            "completion_tokens": usage.get("completion_tokens", "?"),
            "raw_length": len(raw),
            "scores": scores,
        }
    except Exception as e:
        latency_ms = (time.time() - t0) * 1000
        return {
            "name": name, "model_id": model_id,
            "status": "EXCEPTION", "error": str(e),
            "latency_ms": latency_ms, "scores": None
        }

# -- Main ------------------------------------------------------------------
def main():
    print("\n" + "="*72)
    print("  OPENCODE FREE MODEL BENCHMARK  --  AAPL Stock Analysis Task")
    print("="*72)
    print(f"  Testing {len(MODELS)} models concurrently…\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(MODELS)) as pool:
        futures = {pool.submit(call_model, n, m): (n, m) for n, m in MODELS}
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            status = "[OK]" if r["status"] == "OK" else "[FAIL]"
            lat = f"{r['latency_ms']/1000:.1f}s"
            score = r["scores"]["total"] if r["scores"] else "--"
            print(f"  {status} [{lat:>6}]  {r['name']:<26}  score={score}/100")

    # Sort by total score descending
    ok  = [r for r in results if r["status"] == "OK" and r["scores"]]
    err = [r for r in results if r["status"] != "OK" or not r["scores"]]
    ok.sort(key=lambda r: r["scores"]["total"], reverse=True)

    # -- Leaderboard --------------------------------------------------------
    print("\n" + "="*72)
    print("  LEADERBOARD")
    print("="*72)
    print(f"  {'RANK':<5} {'MODEL':<28} {'JSON':>5} {'SCHEMA':>7} {'QUALITY':>8} {'SPEED':>6} {'VERBOSE':>8} {'TOTAL':>6}  {'LATENCY':>8}")
    print("  " + "-"*70)

    medals = ["[1]","[2]","[3]","  4","  5","  6"]
    for i, r in enumerate(ok):
        s = r["scores"]
        medal = medals[i] if i < len(medals) else f"  {i+1}"
        lat = f"{r['latency_ms']/1000:.1f}s"
        print(f"  {medal} {r['name']:<28} {s['json_valid']:>5} {s['schema_complete']:>7} {s['content_quality']:>8} {s['speed']:>6} {s['verbosity']:>8} {s['total']:>6}  {lat:>8}")

    if err:
        print(f"\n  FAILED MODELS:")
        for r in err:
            print(f"    [FAIL]  {r['name']:<28}  {r.get('error','unknown error')[:80]}")

    # -- Detailed breakdown -------------------------------------------------
    print("\n" + "="*72)
    print("  DETAILED ANALYSIS")
    print("="*72)
    for r in ok:
        s = r["scores"]
        print(f"\n  -- {r['name']} ({r['model_id']}) --")
        print(f"     Latency: {r['latency_ms']/1000:.2f}s  |  Response length: {r['raw_length']} chars  |  Completion tokens: {r.get('completion_tokens','?')}")
        print(f"     Total Score: {s['total']}/100")
        if s["notes"]:
            for note in s["notes"]:
                print(f"       {note}")
        parsed = s.get("parsed")
        if parsed:
            val = parsed.get("valuation", {})
            print(f"     Verdict: {val.get('verdict','?')}  |  Grade: {val.get('valuation_grade','?')}  |  Confidence: {val.get('verdict_confidence','?')}%")
            print(f"     Fair Value: ${val.get('fair_value_low','?')} – ${val.get('fair_value_mid','?')} – ${val.get('fair_value_high','?')}")
            summary = parsed.get("executive_summary","")
            if summary:
                print(f"     Summary (first 200 chars): {str(summary)[:200]}…")

    # -- Verdict ------------------------------------------------------------
    if ok:
        winner = ok[0]
        print("\n" + "="*72)
        print("  WINNER")
        print("="*72)
        print(f"\n  [WINNER]  {winner['name']}  ({winner['model_id']})")
        print(f"      Score: {winner['scores']['total']}/100  |  Latency: {winner['latency_ms']/1000:.2f}s")
        print(f"\n  ➜  RECOMMENDATION: Set OPENCODE_MODEL = \"{winner['model_id']}\" in config.py\n")

if __name__ == "__main__":
    main()
