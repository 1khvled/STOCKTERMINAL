import urllib.parse

import pytest
import requests

# Macro regime feature — TEST_MODE contract tests (mock data, no external calls).
# Routes under test (wired after this file lands):
#   GET /api/macro/snapshot        -> 200 {"yields": {...}, "gauges": {...}, "regime": {...}}
#   GET /api/macro/yields          -> 200 {"yields": {...}}
#   GET /api/macro/regime          -> 200 {"regime": {...}}
#   GET /api/intel/macro/<ticker>  -> 200 {"ticker": ..., "regime_read": {...}, "rate_sensitivity": {...}}
#   GET /macro                     -> 200 text/html


def test_macro_snapshot_has_core_keys(base_url):
    resp = requests.get(f"{base_url}/api/macro/snapshot", timeout=5)
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j, dict)
    for key in ("yields", "gauges", "regime"):
        assert key in j, f"snapshot missing {key!r}: {sorted(j.keys())}"
    assert isinstance(j["yields"], dict) and len(j["yields"]) > 0
    assert isinstance(j["gauges"], dict) and len(j["gauges"]) > 0
    assert isinstance(j["regime"], dict) and len(j["regime"]) > 0


def test_macro_yields_contract(base_url):
    resp = requests.get(f"{base_url}/api/macro/yields", timeout=5)
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j, dict)
    assert "yields" in j, f"yields response missing 'yields': {sorted(j.keys())}"
    assert isinstance(j["yields"], dict) and len(j["yields"]) > 0


def test_macro_regime_contract(base_url):
    resp = requests.get(f"{base_url}/api/macro/regime", timeout=5)
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j, dict)
    assert "regime" in j, f"regime response missing 'regime': {sorted(j.keys())}"
    assert isinstance(j["regime"], dict) and len(j["regime"]) > 0


def test_intel_macro_aapl_contract(base_url):
    resp = requests.get(f"{base_url}/api/intel/macro/AAPL", timeout=5)
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j, dict)
    for key in ("regime_read", "rate_sensitivity"):
        assert key in j, f"intel macro missing {key!r}: {sorted(j.keys())}"
    assert isinstance(j["regime_read"], dict) and len(j["regime_read"]) > 0
    assert isinstance(j["rate_sensitivity"], dict) and len(j["rate_sensitivity"]) > 0


@pytest.mark.parametrize("bad_ticker", [
    "!!!",
    "../etc/passwd",
    "<script>alert(1)</script>",
    "A" * 50,
    "123$%^",
])
def test_intel_macro_invalid_ticker_rejected(base_url, bad_ticker):
    enc = urllib.parse.quote(bad_ticker, safe="")
    resp = requests.get(f"{base_url}/api/intel/macro/{enc}", timeout=5)
    # multi-segment payloads (../, <script>) normalize to no-route 404; all else 400 - never 200/500
    assert resp.status_code in (400, 404), f"bad ticker {bad_ticker!r} gave {resp.status_code}"
    if resp.status_code == 400:
        j = resp.json()
        assert "error" in j


def test_macro_page_html(base_url):
    resp = requests.get(f"{base_url}/macro", timeout=5)
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("Content-Type", "")
    assert "macro" in resp.text.lower()
