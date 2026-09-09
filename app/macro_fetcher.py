"""
MACRO DATA ENGINE — personal single-user Flask stock terminal.

Zero API keys: Yahoo Finance (yfinance) only. Vetted symbols:
  ^IRX (13-week T-bill), ^FVX (5Y note), ^TNX (10Y note), ^TYX (30Y bond),
  ^VIX, DX-Y.NYB (US dollar index), GC=F (gold), CL=F (oil),
  HYG + TLT + LQD (credit/rates), ^GSPC (S&P 500 equities).

Every yfinance call is wrapped in try/except with sensible fallbacks
(10Y 4.2%, VIX 20, ...) so nothing ever crashes. Personal project:
no auth, no premium, no billing concepts anywhere.
"""
import logging
import math
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from config import OUTPUT_DIR
except ImportError:
    from .config import OUTPUT_DIR

CACHE_TTL_SECONDS = 3600
CACHE_SUBDIR = "cache"
CACHE_FILENAME = "macro_snapshot.json"

# Sensible fallbacks (percent units for yields, index units otherwise).
FALLBACK_SHORT_YIELD = 4.0    # ^IRX 13W, percent
FALLBACK_BELLY_YIELD = 4.1    # ^FVX 5Y, percent
FALLBACK_TEN_YIELD = 4.2      # ^TNX 10Y, percent
FALLBACK_THIRTY_YIELD = 4.6   # ^TYX 30Y, percent
FALLBACK_VIX = 20.0           # ^VIX
FALLBACK_DOLLAR = 100.0       # DX-Y.NYB
FALLBACK_GOLD = 2300.0        # GC=F
FALLBACK_OIL = 75.0           # CL=F
FALLBACK_HYG = 78.0           # HYG
FALLBACK_TLT = 92.0           # TLT
FALLBACK_LQD = 110.0          # LQD
FALLBACK_SPX = 5200.0         # ^GSPC

YIELD_SYMBOLS = {"short": "^IRX", "belly": "^FVX", "ten": "^TNX", "thirty": "^TYX"}


def _is_test_mode():
    """STOCKER_TEST_MODE==1 -> deterministic mocks, no network."""
    return os.environ.get("STOCKER_TEST_MODE") == "1"


def _utcnow_iso():
    try:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def _cache_file():
    try:
        return Path(OUTPUT_DIR) / CACHE_SUBDIR / CACHE_FILENAME
    except Exception:
        return Path(__file__).resolve().parent.parent / "output" / CACHE_SUBDIR / CACHE_FILENAME


def _fetch_last_close(symbol, fallback):
    """Last close for a Yahoo symbol via history(5d), info fallback. Never raises."""
    try:
        import yfinance as yf
        try:
            try:
                hist = yf.Ticker(symbol).history(period="5d", auto_adjust=False)
            except TypeError:
                hist = yf.Ticker(symbol).history(period="5d")
        except Exception as e:
            logger.info(f"[macro] history failed for {symbol}: {e}")
            hist = None
        try:
            if hist is not None and not hist.empty:
                col = "Close" if "Close" in hist.columns else hist.columns[-1]
                vals = hist[col].dropna()
                if len(vals):
                    v = float(vals.iloc[-1])
                    if math.isfinite(v) and v > 0:
                        return v
        except Exception as e:
            logger.info(f"[macro] parse history failed for {symbol}: {e}")
        try:
            info = yf.Ticker(symbol).info or {}
            for key in ("previousClose", "regularMarketPrice", "currentPrice", "open"):
                raw = info.get(key)
                if raw is None:
                    continue
                try:
                    f = float(raw)
                except Exception:
                    continue
                if math.isfinite(f) and f > 0:
                    return f
        except Exception as e:
            logger.info(f"[macro] info fallback failed for {symbol}: {e}")
    except Exception as e:
        logger.info(f"[macro] fetch failed for {symbol}: {e}")
    return fallback


def _fetch_pct_change(symbol, lookback_bars=21, fallback=0.0):
    """Trailing pct change over ~lookback_bars trading days. Never raises."""
    try:
        import yfinance as yf
        try:
            try:
                hist = yf.Ticker(symbol).history(period="3mo", auto_adjust=False)
            except TypeError:
                hist = yf.Ticker(symbol).history(period="3mo")
        except Exception as e:
            logger.info(f"[macro] momentum history failed for {symbol}: {e}")
            return fallback
        try:
            if hist is not None and not hist.empty:
                col = "Close" if "Close" in hist.columns else hist.columns[-1]
                vals = hist[col].dropna()
                if len(vals) >= lookback_bars + 1:
                    last = float(vals.iloc[-1])
                    base = float(vals.iloc[-(lookback_bars + 1)])
                    if math.isfinite(last) and math.isfinite(base) and base:
                        return (last - base) / base
        except Exception as e:
            logger.info(f"[macro] momentum parse failed for {symbol}: {e}")
    except Exception as e:
        logger.info(f"[macro] momentum fetch failed for {symbol}: {e}")
    return fallback


def _mock_yield_curve():
    short, belly, ten, thirty = 4.0, 4.1, 4.2, 4.6
    return {
        "points": [
            {"label": "13W", "yield": short, "symbol": "^IRX", "maturity": "13-week T-bill"},
            {"label": "5Y", "yield": belly, "symbol": "^FVX", "maturity": "5-year T-note"},
            {"label": "10Y", "yield": ten, "symbol": "^TNX", "maturity": "10-year T-note"},
            {"label": "30Y", "yield": thirty, "symbol": "^TYX", "maturity": "30-year T-bond"},
        ],
        "short_yield": short,
        "belly_yield": belly,
        "ten_yield": ten,
        "thirty_yield": thirty,
        "spread_10y_short": round(ten - short, 3),
        "spread_10y_2y": round(ten - short, 3),
        "spread_10y_2y_proxy": round(ten - short, 3),
        "spread_10y_5y": round(ten - belly, 3),
        "spread_30y_10y": round(thirty - ten, 3),
        "inverted": bool(short > ten),
        "note_2y": "No clean Yahoo symbol for 2Y; short end is ^IRX (13W), honestly labeled.",
        "source": "mock_test",
        "asof": _utcnow_iso(),
    }


def _mock_risk_gauges():
    hyg, tlt, lqd = 78.0, 92.0, 110.0
    return {
        "vix": 18.5,
        "dollar": 100.0,
        "gold": 2300.0,
        "oil": 75.0,
        "hyg": hyg,
        "tlt": tlt,
        "lqd": lqd,
        "spx": 5200.0,
        "hyg_tlt_ratio": round(hyg / tlt, 4),
        "hyg_lqd_ratio": round(hyg / lqd, 4),
        "credit_spread_proxy": round(lqd / hyg, 4),
        "note": "credit_spread_proxy = LQD/HYG (rises when high-yield lags investment-grade).",
        "source": "mock_test",
        "asof": _utcnow_iso(),
    }


def get_yield_curve():
    """Yield curve from ^IRX/^FVX/^TNX/^TYX (percent units). Never raises."""
    if _is_test_mode():
        return _mock_yield_curve()
    try:
        short = _fetch_last_close(YIELD_SYMBOLS["short"], FALLBACK_SHORT_YIELD)
        belly = _fetch_last_close(YIELD_SYMBOLS["belly"], FALLBACK_BELLY_YIELD)
        ten = _fetch_last_close(YIELD_SYMBOLS["ten"], FALLBACK_TEN_YIELD)
        thirty = _fetch_last_close(YIELD_SYMBOLS["thirty"], FALLBACK_THIRTY_YIELD)
        try:
            short, belly, ten, thirty = (round(float(short), 3), round(float(belly), 3),
                                         round(float(ten), 3), round(float(thirty), 3))
        except Exception:
            short, belly, ten, thirty = (FALLBACK_SHORT_YIELD, FALLBACK_BELLY_YIELD,
                                         FALLBACK_TEN_YIELD, FALLBACK_THIRTY_YIELD)
        spread_short = round(ten - short, 3)
        return {
            "points": [
                {"label": "13W", "yield": short, "symbol": "^IRX", "maturity": "13-week T-bill"},
                {"label": "5Y", "yield": belly, "symbol": "^FVX", "maturity": "5-year T-note"},
                {"label": "10Y", "yield": ten, "symbol": "^TNX", "maturity": "10-year T-note"},
                {"label": "30Y", "yield": thirty, "symbol": "^TYX", "maturity": "30-year T-bond"},
            ],
            "short_yield": short,
            "belly_yield": belly,
            "ten_yield": ten,
            "thirty_yield": thirty,
            "spread_10y_short": spread_short,
            "spread_10y_2y": spread_short,
            "spread_10y_2y_proxy": spread_short,
            "spread_10y_5y": round(ten - belly, 3),
            "spread_30y_10y": round(thirty - ten, 3),
            "inverted": bool(short > ten),
            "note_2y": "No clean Yahoo symbol for 2Y; short end is ^IRX (13W), honestly labeled.",
            "source": "yfinance",
            "asof": _utcnow_iso(),
        }
    except Exception as e:
        logger.info(f"[macro] get_yield_curve failed: {e}")
        fallback = _mock_yield_curve()
        fallback["source"] = "fallback"
        fallback["error"] = str(e)[:200]
        return fallback


def get_risk_gauges():
    """VIX / dollar / gold / oil / credit-risk ETFs. Never raises."""
    if _is_test_mode():
        return _mock_risk_gauges()
    try:
        vix = _fetch_last_close("^VIX", FALLBACK_VIX)
        dollar = _fetch_last_close("DX-Y.NYB", FALLBACK_DOLLAR)
        gold = _fetch_last_close("GC=F", FALLBACK_GOLD)
        oil = _fetch_last_close("CL=F", FALLBACK_OIL)
        hyg = _fetch_last_close("HYG", FALLBACK_HYG)
        tlt = _fetch_last_close("TLT", FALLBACK_TLT)
        lqd = _fetch_last_close("LQD", FALLBACK_LQD)
        spx = _fetch_last_close("^GSPC", FALLBACK_SPX)
        try:
            hyg_tlt = round(float(hyg) / float(tlt), 4) if tlt else round(FALLBACK_HYG / FALLBACK_TLT, 4)
        except Exception:
            hyg_tlt = round(FALLBACK_HYG / FALLBACK_TLT, 4)
        try:
            hyg_lqd = round(float(hyg) / float(lqd), 4) if lqd else round(FALLBACK_HYG / FALLBACK_LQD, 4)
        except Exception:
            hyg_lqd = round(FALLBACK_HYG / FALLBACK_LQD, 4)
        try:
            spread_proxy = round(float(lqd) / float(hyg), 4) if hyg else round(FALLBACK_LQD / FALLBACK_HYG, 4)
        except Exception:
            spread_proxy = round(FALLBACK_LQD / FALLBACK_HYG, 4)
        return {
            "vix": round(float(vix), 2),
            "dollar": round(float(dollar), 2),
            "gold": round(float(gold), 2),
            "oil": round(float(oil), 2),
            "hyg": round(float(hyg), 2),
            "tlt": round(float(tlt), 2),
            "lqd": round(float(lqd), 2),
            "spx": round(float(spx), 2),
            "hyg_tlt_ratio": hyg_tlt,
            "hyg_lqd_ratio": hyg_lqd,
            "credit_spread_proxy": spread_proxy,
            "note": "credit_spread_proxy = LQD/HYG (rises when high-yield lags investment-grade).",
            "source": "yfinance",
            "asof": _utcnow_iso(),
        }
    except Exception as e:
        logger.info(f"[macro] get_risk_gauges failed: {e}")
        fallback = _mock_risk_gauges()
        fallback["source"] = "fallback"
        fallback["error"] = str(e)[:200]
        return fallback


def get_fed_stance():
    """Market-implied rate-policy heuristic from curve shape + VIX.

    Market-implied heuristic ONLY — NOT FOMC data, NOT a forecast of Fed action.
    Never raises.
    """
    if _is_test_mode():
        return {
            "label": "NEUTRAL",
            "reasons": ["TEST_MODE deterministic mock: curve normal, VIX calm."],
            "method": "Market-implied heuristic from yield-curve shape + VIX; NOT FOMC data.",
            "inputs": {"ten_yield": 4.2, "short_yield": 4.0, "inverted": False, "vix": 18.5},
            "source": "mock_test",
            "asof": _utcnow_iso(),
        }
    try:
        curve = get_yield_curve() or {}
        risk = get_risk_gauges() or {}
        try:
            ten = float(curve.get("ten_yield", FALLBACK_TEN_YIELD))
        except Exception:
            ten = FALLBACK_TEN_YIELD
        try:
            short = float(curve.get("short_yield", FALLBACK_SHORT_YIELD))
        except Exception:
            short = FALLBACK_SHORT_YIELD
        try:
            vix = float(risk.get("vix", FALLBACK_VIX))
        except Exception:
            vix = FALLBACK_VIX
        inverted = bool(curve.get("inverted", short > ten))
        spread = round(ten - short, 3)

        ease_votes, tight_votes = 0, 0
        reasons = []
        if inverted:
            ease_votes += 2
            reasons.append(f"Curve inverted (13W {short}% > 10Y {ten}%): market pricing future easing, not current Fed action.")
        else:
            reasons.append(f"Curve not inverted (10Y-13W spread {spread}pp).")
        if vix >= 30:
            ease_votes += 1
            reasons.append(f"VIX {vix} elevated stress: market-implied pressure toward easing expectations.")
        elif vix <= 18 and ten >= 4.5:
            tight_votes += 1
            reasons.append(f"10Y {ten}% firm with calm VIX {vix}: market tolerating a tighter stance.")
        if ten >= 5.0:
            tight_votes += 1
            reasons.append(f"10Y {ten}% very high: market-implied TIGHTENING backdrop.")
        elif ten <= 3.0:
            ease_votes += 1
            reasons.append(f"10Y {ten}% low: market-implied EASING backdrop.")
        if spread >= 1.0:
            tight_votes += 1
            reasons.append(f"Steep positive curve (spread {spread}pp): no market stress signal.")
        if ease_votes >= 2:
            label = "EASING"
        elif tight_votes >= 2:
            label = "TIGHTENING"
        elif ease_votes == 1 and tight_votes == 0:
            label = "EASING"
        elif tight_votes == 1 and ease_votes == 0:
            label = "TIGHTENING"
        else:
            label = "NEUTRAL"
            reasons.append("Mixed/neutral market-implied signals.")
        return {
            "label": label,
            "reasons": reasons,
            "method": "Market-implied heuristic from yield-curve shape + VIX; NOT FOMC data.",
            "inputs": {"ten_yield": ten, "short_yield": short, "inverted": inverted,
                       "spread_10y_short": spread, "vix": vix},
            "source": "yfinance_heuristic",
            "asof": _utcnow_iso(),
        }
    except Exception as e:
        logger.info(f"[macro] get_fed_stance failed: {e}")
        return {
            "label": "NEUTRAL",
            "reasons": [f"Heuristic fallback after error: {str(e)[:120]}"],
            "method": "Market-implied heuristic from yield-curve shape + VIX; NOT FOMC data.",
            "inputs": {},
            "source": "fallback",
            "asof": _utcnow_iso(),
        }


def get_regime():
    """Market regime from VIX + credit ratio + curve + equity momentum + oil. Never raises."""
    if _is_test_mode():
        return {
            "label": "NEUTRAL",
            "score": 0,
            "reasons": ["TEST_MODE deterministic mock."],
            "inputs": {"vix": 18.5, "hyg_tlt_ratio": 0.8478, "inverted": False,
                       "spx_1mo_pct": 0.0, "oil": 75.0},
            "source": "mock_test",
            "asof": _utcnow_iso(),
        }
    try:
        curve = get_yield_curve() or {}
        risk = get_risk_gauges() or {}
        try:
            vix = float(risk.get("vix", FALLBACK_VIX))
        except Exception:
            vix = FALLBACK_VIX
        try:
            ratio = float(risk.get("hyg_tlt_ratio", FALLBACK_HYG / FALLBACK_TLT))
        except Exception:
            ratio = FALLBACK_HYG / FALLBACK_TLT
        try:
            oil = float(risk.get("oil", FALLBACK_OIL))
        except Exception:
            oil = FALLBACK_OIL
        inverted = bool(curve.get("inverted", False))
        spx_mom = _fetch_pct_change("^GSPC", lookback_bars=21, fallback=0.0)
        try:
            spx_mom = float(spx_mom)
            if not math.isfinite(spx_mom):
                spx_mom = 0.0
        except Exception:
            spx_mom = 0.0

        score = 0
        reasons = []
        if vix < 20:
            score += 1
            reasons.append(f"VIX {vix} calm supports risk appetite (+1).")
        elif vix <= 25:
            reasons.append(f"VIX {vix} middling, no regime vote.")
        elif vix <= 30:
            score -= 1
            reasons.append(f"VIX {vix} elevated, defensive tilt (-1).")
        else:
            score -= 2
            reasons.append(f"VIX {vix} stressed, risk-off pressure (-2).")
        if ratio >= 0.87:
            score += 1
            reasons.append(f"HYG/TLT {ratio} firm: credit risk appetite (+1).")
        elif ratio <= 0.82:
            score -= 1
            reasons.append(f"HYG/TLT {ratio} soft: credit stress (-1).")
        else:
            reasons.append(f"HYG/TLT {ratio} neutral.")
        if spx_mom >= 0.03:
            score += 1
            reasons.append(f"S&P 500 1-mo {spx_mom:.1%} strong (+1).")
        elif spx_mom <= -0.05:
            score -= 1
            reasons.append(f"S&P 500 1-mo {spx_mom:.1%} weak (-1).")
        else:
            reasons.append(f"S&P 500 1-mo {spx_mom:.1%} trendless.")
        if inverted:
            score -= 1
            reasons.append("Inverted curve (13W > 10Y): late-cycle caution (-1).")

        if oil >= 90 and (inverted or vix >= 25):
            label = "STAGFLATION_WATCH"
            reasons.append(f"Oil {oil} high with stress (inverted={inverted}, VIX {vix}): stagflation watch.")
        elif score >= 2:
            label = "RISK_ON"
        elif score <= -2:
            label = "RISK_OFF"
        else:
            label = "NEUTRAL"
        return {
            "label": label,
            "score": int(score),
            "reasons": reasons,
            "inputs": {"vix": round(vix, 2), "hyg_tlt_ratio": round(ratio, 4),
                       "inverted": inverted, "spx_1mo_pct": round(spx_mom, 4),
                       "oil": round(oil, 2)},
            "source": "yfinance_heuristic",
            "asof": _utcnow_iso(),
        }
    except Exception as e:
        logger.info(f"[macro] get_regime failed: {e}")
        return {
            "label": "NEUTRAL",
            "score": 0,
            "reasons": [f"Regime fallback after error: {str(e)[:120]}"],
            "inputs": {},
            "source": "fallback",
            "asof": _utcnow_iso(),
        }


def _read_snapshot_cache():
    try:
        path = _cache_file()
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > CACHE_TTL_SECONDS:
            return None
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        payload["cached"] = True
        payload["cache_age_seconds"] = int(age)
        return payload
    except Exception as e:
        logger.info(f"[macro] cache read failed: {e}")
        return None


def _write_snapshot_cache(payload):
    try:
        path = _cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)  # atomic on same fs
    except Exception as e:
        logger.info(f"[macro] cache write failed: {e}")


def get_macro_snapshot(force=False):
    """Everything combined; cached 1 hour to OUTPUT_DIR/cache/macro_snapshot.json. Never raises."""
    if _is_test_mode():
        return {
            "asof": _utcnow_iso(),
            "yields": _mock_yield_curve(),
            "risk": _mock_risk_gauges(),
            "fed": {
                "label": "NEUTRAL",
                "reasons": ["TEST_MODE deterministic mock: curve normal, VIX calm."],
                "method": "Market-implied heuristic from yield-curve shape + VIX; NOT FOMC data.",
                "inputs": {"ten_yield": 4.2, "short_yield": 4.0, "inverted": False, "vix": 18.5},
                "source": "mock_test",
                "asof": _utcnow_iso(),
            },
            "regime": {
                "label": "NEUTRAL",
                "score": 0,
                "reasons": ["TEST_MODE deterministic mock."],
                "inputs": {"vix": 18.5, "hyg_tlt_ratio": 0.8478, "inverted": False,
                           "spx_1mo_pct": 0.0, "oil": 75.0},
                "source": "mock_test",
                "asof": _utcnow_iso(),
            },
            "source": "mock_test",
            "cached": False,
            "ttl_seconds": CACHE_TTL_SECONDS,
        }
    try:
        if not force:
            cached = _read_snapshot_cache()
            if cached is not None:
                return cached
        yields = get_yield_curve()
        risk = get_risk_gauges()
        fed = get_fed_stance()
        regime = get_regime()
        snapshot = {
            "asof": _utcnow_iso(),
            "yields": yields,
            "risk": risk,
            "fed": fed,
            "regime": regime,
            "source": "yfinance",
            "cached": False,
            "ttl_seconds": CACHE_TTL_SECONDS,
        }
        try:
            _write_snapshot_cache(snapshot)
        except Exception as e:
            logger.info(f"[macro] snapshot cache write failed: {e}")
        return snapshot
    except Exception as e:
        logger.info(f"[macro] get_macro_snapshot failed: {e}")
        return {
            "asof": _utcnow_iso(),
            "yields": _mock_yield_curve(),
            "risk": _mock_risk_gauges(),
            "fed": {"label": "NEUTRAL", "reasons": ["snapshot fallback"],
                     "method": "Market-implied heuristic from yield-curve shape + VIX; NOT FOMC data.",
                     "inputs": {}, "source": "fallback", "asof": _utcnow_iso()},
            "regime": {"label": "NEUTRAL", "score": 0, "reasons": ["snapshot fallback"],
                       "inputs": {}, "source": "fallback", "asof": _utcnow_iso()},
            "source": "fallback",
            "cached": False,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "error": str(e)[:200],
        }
