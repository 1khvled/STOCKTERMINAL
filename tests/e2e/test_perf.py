import math
import time

import requests

# Perf budget: TEST_MODE (mock data, no external calls). Plain asserts, no xfail.
BUDGET_S = 25.0


def test_perf_live_quotes_fast_and_numeric(base_url):
    t0 = time.monotonic()
    resp = requests.get(f"{base_url}/api/stocks/live-quotes", timeout=25)
    dt = time.monotonic() - t0
    assert resp.status_code == 200
    assert dt < BUDGET_S, f"live-quotes took {dt:.1f}s, budget {BUDGET_S}s"
    j = resp.json()
    assert isinstance(j, dict)
    assert "quotes" in j
    assert isinstance(j["quotes"], list)
    assert len(j["quotes"]) > 0
    for q in j["quotes"]:
        assert isinstance(q, dict)
        assert "price" in q
        price = q["price"]
        assert price is not None
        assert isinstance(price, (int, float)) and not isinstance(price, bool)
        assert math.isfinite(float(price)), f"non-finite price for {q.get('ticker')}: {price!r}"


def test_perf_movers_fast_and_shaped(base_url):
    t0 = time.monotonic()
    resp = requests.get(f"{base_url}/api/market/movers", timeout=25)
    dt = time.monotonic() - t0
    assert resp.status_code == 200
    assert dt < BUDGET_S, f"movers took {dt:.1f}s, budget {BUDGET_S}s"
    j = resp.json()
    assert isinstance(j, dict)
    for key in ("gainers", "losers", "actives"):
        assert key in j, f"movers missing {key!r}: {sorted(j.keys())}"
        assert isinstance(j[key], list), f"movers[{key!r}] not a list"


def test_perf_macro_snapshot_fast_and_shaped(base_url):
    t0 = time.monotonic()
    resp = requests.get(f"{base_url}/api/macro/snapshot", timeout=25)
    dt = time.monotonic() - t0
    assert resp.status_code == 200
    assert dt < BUDGET_S, f"macro snapshot took {dt:.1f}s, budget {BUDGET_S}s"
    j = resp.json()
    assert isinstance(j, dict)
    for key in ("yields", "gauges", "regime"):
        assert key in j, f"snapshot missing {key!r}: {sorted(j.keys())}"
        assert isinstance(j[key], dict), f"snapshot[{key!r}] not a dict"


def test_perf_macro_page(base_url):
    t0 = time.monotonic()
    resp = requests.get(f"{base_url}/macro", timeout=25)
    dt = time.monotonic() - t0
    assert resp.status_code == 200
    assert dt < BUDGET_S, f"/macro took {dt:.1f}s, budget {BUDGET_S}s"
    assert "macro" in resp.text.lower()
