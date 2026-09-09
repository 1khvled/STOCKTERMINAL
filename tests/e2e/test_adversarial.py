import pytest
import requests
import urllib.parse

# Tier 5: Adversarial hardening — malformed tickers, empty DB, rate-limit soak, injection
# Runs with STOCKER_TEST_MODE=1 (mock data, no external calls)

@pytest.mark.parametrize("bad_ticker", [
    "../etc/passwd", "..\\..\\windows", "AAPL; DROP TABLE",
    "<script>alert(1)</script>", "A" * 50, "!!!", "123$%^",
    "BRK.B; rm -rf /", "../../", "%2e%2e%2f", "AAPL|cat",
    "AAPL`whoami`", "AAPL$(id)", ""
])
def test_malformed_ticker_rejected(base_url, bad_ticker):
    # Stream and API routes must not crash — expect 400/404/422, never 500
    # Encode ticker for URL safety
    enc = urllib.parse.quote(bad_ticker, safe='')
    if enc == "":
        enc = "%20"  # empty becomes space
    for endpoint in [f"/api/stock/{enc}", f"/api/stock/{enc}/financials", f"/api/stock/{enc}/history"]:
        resp = requests.get(f"{base_url}{endpoint}", timeout=5)
        assert resp.status_code in (400, 404, 422), f"bad ticker {bad_ticker!r} on {endpoint} gave {resp.status_code}"
        # For API routes, if 200 it means ticker was normalized (e.g., lowercase) — ensure it's not 500 and returns JSON
        if resp.status_code == 200:
            j = resp.json()
            assert isinstance(j, dict)
        else:
            # Error case must return JSON with error field
            try:
                j = resp.json()
                assert "error" in j
            except Exception:
                if endpoint.startswith("/api/"):
                    pytest.fail(f"API {endpoint} with bad ticker {bad_ticker!r} did not return JSON, got {resp.text[:200]}")


def test_empty_ticker_query(base_url):
    resp = requests.get(f"{base_url}/api/stream", timeout=5)
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        body = resp.text
        assert "Error" in body or "error" in body.lower()

def test_api_stocks_always_returns_list(base_url):
    resp = requests.get(f"{base_url}/api/stocks", timeout=5)
    assert resp.status_code == 200
    j = resp.json()
    assert "stocks" in j
    assert isinstance(j["stocks"], list)

def test_screener_filter_no_crash(base_url):
    for params in [{}, {"sector": "' OR 1=1 --"}, {"verdict": "<svg onload=alert(1)>"}, {"min_pe": "not_a_number"}, {"min_upside": "999999"}]:
        resp = requests.get(f"{base_url}/api/screener/filter", params=params, timeout=5)
        assert resp.status_code in (200, 400)
        if resp.status_code == 200:
            j = resp.json()
            assert "stocks" in j
            assert "criteria" in j

def test_screener_ai_empty_query_rejected(base_url):
    resp = requests.post(f"{base_url}/api/screener/ai", json={"query": ""}, timeout=5)
    assert resp.status_code == 400
    assert "error" in resp.json()
    resp = requests.post(f"{base_url}/api/screener/ai", json={}, timeout=5)
    assert resp.status_code == 400

def test_query_search_handles_empty_and_injection(base_url):
    for q in ["", " ", "'; DROP TABLE", "<script>", "A" * 1000]:
        resp = requests.get(f"{base_url}/api/query/search", params={"q": q}, timeout=5)
        assert resp.status_code == 200
        j = resp.json()
        assert "results" in j
        assert isinstance(j["results"], list)

def test_portfolio_endpoints_validate_input(base_url):
    resp = requests.post(f"{base_url}/api/portfolio/add", json={}, timeout=5)
    assert resp.status_code == 400
    resp = requests.post(f"{base_url}/api/portfolio/add", json={"ticker": "<script>", "weight": -5}, timeout=5)
    assert resp.status_code in (400, 404, 422, 500)
    resp = requests.post(f"{base_url}/api/portfolio/remove", json={}, timeout=5)
    assert resp.status_code == 400

def test_terminal_execute_blocks_injection(base_url):
    for cmd in ["; rm -rf /", "&& cat /etc/passwd", "| ls", "`whoami`", "$(whoami)"]:
        resp = requests.post(f"{base_url}/api/terminal/execute", json={"command": cmd}, timeout=5)
        assert resp.status_code in (200, 400, 404)
        if resp.status_code == 200:
            j = resp.json()
            assert isinstance(j, dict)

def test_rate_limit_mock_ticker(base_url):
    resp = requests.get(f"{base_url}/api/stream?ticker=RATELIMIT", stream=True, timeout=10)
    assert resp.status_code == 200
    body = b"".join(resp.iter_lines()).decode(errors="ignore")
    assert "REDIRECT" in body or "429" in body or "rate" in body.lower() or "error" in body.lower()

def test_missing_ticker_graceful(base_url):
    resp = requests.get(f"{base_url}/api/stream?ticker=MISSING", stream=True, timeout=10)
    assert resp.status_code == 200
    body = b"".join(resp.iter_lines()).decode(errors="ignore")
    assert "MISSING" in body or "not found" in body.lower() or "REDIRECT" in body

def test_dashboard_404_for_unknown_ticker(base_url):
    # Unknown but valid tickers redirect to hub auto-analyze (no dead template/pages).
    resp = requests.get(f"{base_url}/dashboard/ZZZZQ", timeout=5, allow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert "ticker=ZZZZQ" in resp.headers.get("Location", "")
    resp = requests.get(f"{base_url}/dashboard/ZZZZNOTFOUND123", timeout=5)
    assert resp.status_code in (400, 404)

def test_peers_ai_contract(base_url):
    resp = requests.get(f"{base_url}/api/peers/ai/MU", timeout=20)
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j.get("focus_metrics"), list) and j["focus_metrics"]
    assert isinstance(j.get("ranked_peers"), list) and j["ranked_peers"]
    assert isinstance(j.get("readout"), str) and j["readout"]
    resp = requests.get(f"{base_url}/api/peers/ai/ZZZZQ", timeout=5)
    assert resp.status_code == 404
    resp = requests.get(f"{base_url}/api/peers/ai/!!!INVALID", timeout=5)
    assert resp.status_code == 400


def test_research_pages(base_url):
    resp = requests.get(f"{base_url}/research/CRM/briefing", timeout=5)
    assert resp.status_code == 200
    assert "briefing" in resp.text.lower()
    for pg in ["earnings", "overview"]:
        r = requests.get(f"{base_url}/research/CRM/{pg}", timeout=5)
        assert r.status_code == 200
    r = requests.get(f"{base_url}/research/CRM/nonexistent", timeout=5)
    assert r.status_code == 404
    r = requests.get(f"{base_url}/research/ZZZZQ/briefing", timeout=5, allow_redirects=False)
    assert r.status_code in (302, 303, 307)
    r = requests.get(f"{base_url}/research/!!!INVALID/briefing", timeout=5)
    assert r.status_code == 400


def test_api_health(base_url):
    resp = requests.get(f"{base_url}/api/system/health", timeout=5)
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j, dict)

def test_live_quote_invalid_ticker(base_url):
    resp = requests.get(f"{base_url}/api/stock/!!!INVALID/live-quote", timeout=5)
    assert resp.status_code in (400, 404, 200)
    if resp.status_code == 200:
        j = resp.json()
        assert isinstance(j, dict)
