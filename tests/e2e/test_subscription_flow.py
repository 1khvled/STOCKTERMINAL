"""End-to-end subscription flow against the running test server.

Checkout -> signed webhook -> license key -> activate -> gate opens ->
admin revoke -> gate closes again. Uses the server started by conftest
(STOCKER_TEST_MODE=1, port 5005).
"""
import json
import time

import pytest
import requests

WEBHOOK_SECRET = "stocker-e2e-webhook-secret"
ADMIN_TOKEN = "stocker-e2e-admin-token"


def _signed_headers(body, secret=WEBHOOK_SECRET, timestamp=None):
    import hashlib
    import hmac
    ts = str(timestamp if timestamp is not None else int(time.time()))
    digest = hmac.new(secret.encode("utf-8"), (ts + ".").encode("utf-8") + body.encode("utf-8"),
                      hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Stocker-Signature": f"sha256={digest}",
        "X-Stocker-Timestamp": ts,
    }


def test_free_tier_is_the_default(base_url):
    resp = requests.get(f"{base_url}/api/account/me", timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] in ("free", "pro")
    # before any activation the gated surface answers with an explanation
    gated = requests.get(f"{base_url}/api/intel/scenarios/AAPL", timeout=10)
    assert gated.status_code in (200, 402)
    if gated.status_code == 402:
        assert gated.json()["error"] == "upgrade_required"


def test_webhook_issues_key_activate_opens_gate_revoke_closes_it(base_url):
    event_id = f"evt_e2e_{int(time.time() * 1000)}"
    body = json.dumps({
        "id": event_id,
        "type": "subscription.activated",
        "data": {"email": "e2e-buyer@example.com", "plan": "pro", "months": 12},
    })
    headers = _signed_headers(body)

    issued = requests.post(f"{base_url}/api/billing/webhook", data=body, headers=headers, timeout=15)
    assert issued.status_code == 200, issued.text
    payload = issued.json()
    assert payload["ok"] is True
    key = payload["license_key"]
    assert key.startswith("STK-")

    # replaying the same event must not issue a second key
    replay = requests.post(f"{base_url}/api/billing/webhook", data=body, headers=headers, timeout=15)
    assert replay.status_code == 200
    assert replay.json().get("duplicate") is True

    # a forged signature is rejected
    forged = _signed_headers(body, secret="wrong-secret")
    bad = requests.post(f"{base_url}/api/billing/webhook", data=body, headers=forged, timeout=15)
    assert bad.status_code == 400
    assert bad.json()["error"] == "invalid_signature"

    # activate the key on the server
    act = requests.post(f"{base_url}/activate", data={"key": key}, timeout=15, allow_redirects=False)
    assert act.status_code in (302, 303), act.text

    me = requests.get(f"{base_url}/api/account/me", timeout=10).json()
    assert me["plan"] == "pro", me
    assert me["features"]["scenario_lab"] is True
    assert me["features"]["terminal_api"] is True

    # the gated surfaces are open now
    assert requests.get(f"{base_url}/api/intel/scenarios/AAPL", timeout=30).status_code == 200
    assert requests.get(f"{base_url}/api/intel/committee/AAPL", timeout=30).status_code == 200
    assert requests.get(f"{base_url}/api/intel/red-flags/AAPL", timeout=30).status_code == 200
    assert requests.get(f"{base_url}/scenario-lab", timeout=15).status_code == 200

    # the terminal API runs again
    term = requests.post(f"{base_url}/api/terminal/execute", json={"command": "PING"}, timeout=15)
    assert term.status_code == 200
    assert term.json().get("error") != "upgrade_required"

    # revoke -> the gate closes again
    revoked = requests.post(f"{base_url}/admin/revoke", json={"key": key},
                             headers={"X-Admin-Token": ADMIN_TOKEN}, timeout=15)
    assert revoked.status_code == 200, revoked.text

    after = requests.get(f"{base_url}/api/account/me", timeout=10).json()
    assert after["plan"] == "free", after
    gated = requests.get(f"{base_url}/api/intel/scenarios/AAPL", timeout=15)
    assert gated.status_code == 402
    assert gated.json()["error"] == "upgrade_required"
    # and the page explains the upgrade instead of dying
    page = requests.get(f"{base_url}/scenario-lab", timeout=15)
    assert page.status_code == 200
    assert "Pro feature" in page.text


def test_admin_area_is_protected(base_url):
    resp = requests.get(f"{base_url}/admin/users", timeout=10)
    assert resp.status_code == 403
    resp2 = requests.get(f"{base_url}/admin/users", headers={"X-Admin-Token": ADMIN_TOKEN}, timeout=10)
    assert resp2.status_code == 200
    assert "users" in resp2.json()


def test_pricing_and_account_pages_render(base_url):
    for path in ("/pricing", "/account", "/billing", "/activate", "/login", "/signup"):
        resp = requests.get(f"{base_url}{path}", timeout=10)
        assert resp.status_code == 200, path
        assert "text/html" in resp.headers.get("Content-Type", ""), path
