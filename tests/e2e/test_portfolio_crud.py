import requests

# Portfolio CRUD regression (runs against isolated TEST_MODE output dir - never prod).
# Uses synthetic ZZZQ/ZZZR tickers and cleans up after itself.
T1, T2 = "ZZZQ", "ZZZR"


def _clean(base_url):
    for t in (T1, T2):
        try:
            requests.post(f"{base_url}/api/portfolio/remove", json={"ticker": t}, timeout=5)
        except Exception:
            pass


def _get(base_url):
    resp = requests.get(f"{base_url}/api/portfolio?ai=0", timeout=10)
    assert resp.status_code == 200
    return resp.json()


def test_portfolio_add_valid(base_url):
    _clean(base_url)
    try:
        resp = requests.post(f"{base_url}/api/portfolio/add", json={"ticker": T1, "weight": 10}, timeout=10)
        assert resp.status_code == 200
        d = resp.json()
        assert any(p["ticker"] == T1 for p in d.get("positions", [])), d
    finally:
        _clean(base_url)


def test_portfolio_add_duplicate_replaces(base_url):
    _clean(base_url)
    try:
        requests.post(f"{base_url}/api/portfolio/add", json={"ticker": T1, "weight": 10}, timeout=10)
        resp = requests.post(f"{base_url}/api/portfolio/add", json={"ticker": T1, "weight": 25}, timeout=10)
        assert resp.status_code == 200
        rows = [p for p in resp.json().get("positions", []) if p["ticker"] == T1]
        assert len(rows) == 1 and rows[0]["weight"] == 25
    finally:
        _clean(base_url)


def test_portfolio_add_invalid(base_url):
    for payload in [{}, {"ticker": "", "weight": 10}, {"ticker": "<script>", "weight": 10},
                    {"ticker": T1}, {"ticker": T1, "weight": 0}, {"ticker": T1, "weight": -5},
                    {"ticker": T1, "weight": "abc"}]:
        resp = requests.post(f"{base_url}/api/portfolio/add", json=payload, timeout=10)
        assert resp.status_code == 400, payload
        assert "error" in resp.json()
    _clean(base_url)


def test_portfolio_weight_clamped_100(base_url):
    _clean(base_url)
    try:
        resp = requests.post(f"{base_url}/api/portfolio/add", json={"ticker": T1, "weight": 150}, timeout=10)
        assert resp.status_code == 200
        rows = [p for p in resp.json().get("positions", []) if p["ticker"] == T1]
        assert rows and rows[0]["weight"] == 100
    finally:
        _clean(base_url)


def test_portfolio_multi_totals_and_remove(base_url):
    _clean(base_url)
    base = _get(base_url)
    base_w = base.get("total_weight") or 0
    base_n = len(base.get("positions") or [])
    try:
        requests.post(f"{base_url}/api/portfolio/add", json={"ticker": T1, "weight": 10}, timeout=10)
        requests.post(f"{base_url}/api/portfolio/add", json={"ticker": T2, "weight": 20}, timeout=10)
        d = _get(base_url)
        assert d["total_weight"] == base_w + 30
        assert len(d["positions"]) == base_n + 2
        resp = requests.post(f"{base_url}/api/portfolio/remove", json={"ticker": T1}, timeout=10)
        assert resp.status_code == 200
        d2 = resp.json()
        assert all(p["ticker"] != T1 for p in d2.get("positions", []))
        assert d2["total_weight"] == base_w + 20
    finally:
        _clean(base_url)


def test_portfolio_persists_reload(base_url):
    _clean(base_url)
    try:
        requests.post(f"{base_url}/api/portfolio/add", json={"ticker": T1, "weight": 10}, timeout=10)
        d = _get(base_url)
        assert any(p["ticker"] == T1 for p in d.get("positions", []))
    finally:
        _clean(base_url)
