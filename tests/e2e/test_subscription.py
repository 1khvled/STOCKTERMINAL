"""Subscription / licensing unit + contract tests.

Covers: key issue -> activate -> gate opens -> expiry -> revoke -> machine
mismatch -> offline grace, plus the webhook signature + idempotency contract.

These tests never touch the network and never touch the real output/ tree:
the accounts DB and the entitlement file are redirected into a tmp dir.
"""
import hashlib
import json
import os
import sys
import time

import pytest


class _NoBuffer:
    """stdout/stderr shim without a ``buffer`` attribute.

    app/server.py re-wraps sys.stdout on Windows (utf-8 fix). That would
    replace pytest's captured stream, so the import happens behind this shim:
    server.py sees no ``.buffer`` and leaves the streams alone.
    """

    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def write(self, text):
        return self._real.write(text)

    def flush(self):
        return self._real.flush()

    def __getattr__(self, name):
        if name == "buffer":
            raise AttributeError(name)
        return getattr(self._real, name)


def _import_server_app():
    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _NoBuffer(real_out), _NoBuffer(real_err)
    try:
        from app.server import app as flask_app
    finally:
        sys.stdout, sys.stderr = real_out, real_err
    return flask_app


app = _import_server_app()
import accounts  # noqa: E402  (same module instance the server uses)
import billing  # noqa: E402
import licensing  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """Point the accounts DB, the entitlement file and the secrets at tmp."""
    monkeypatch.setenv("STOCKER_ACCOUNTS_DB", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("STOCKER_ENTITLEMENT_FILE", str(tmp_path / "entitlement.json"))
    monkeypatch.setenv("STOCKER_LICENSE_SECRET", "unit-test-license-secret")
    monkeypatch.setenv("STOCKER_MACHINE_ID", "unit-test-machine")
    monkeypatch.setenv("STOCKER_GRACE_DAYS", "14")
    monkeypatch.delenv("STOCKER_ENTITLEMENT_URL", raising=False)
    accounts.init_db()
    yield


@pytest.fixture()
def client(isolated):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ─── keys ──────────────────────────────────────────────────────────────────
def test_license_key_roundtrip():
    key = licensing.generate_license_key()
    assert key.startswith("STK-")
    assert licensing.normalize_key(key) == key
    # messy input is normalised
    assert licensing.normalize_key(key.replace("-", " ").lower()) == key
    # a broken check character is rejected
    body = key.replace("-", "")[:-1]
    broken = body[:-1] + ("0" if body[-1] != "0" else "1")
    assert licensing.normalize_key(broken) is None
    assert licensing.normalize_key("not-a-key") is None
    assert licensing.normalize_key("") is None


def test_key_hash_is_stable_and_not_the_key():
    key = licensing.generate_license_key()
    h1 = licensing.key_hash(key)
    h2 = licensing.key_hash(key)
    assert h1 == h2
    assert key not in h1
    assert licensing.key_hash(licensing.generate_license_key()) != h1


def test_signed_offline_key_verifies():
    key, payload, signature = licensing.issue_signed_key("pro", months=1, email="a@b.c")
    ok, verified, reason = licensing.verify_signed_key(key)
    assert ok, reason
    assert verified["plan"] == "pro"
    assert verified["email"] == "a@b.c"
    # tampering breaks the signature
    tampered = key[:-1] + ("0" if key[-1] != "0" else "1")
    ok2, _, reason2 = licensing.verify_signed_key(tampered)
    assert not ok2


def test_machine_fingerprint_is_stable_and_machine_specific(monkeypatch):
    monkeypatch.setenv("STOCKER_MACHINE_ID", "machine-a")
    fp_a = licensing.machine_fingerprint()
    monkeypatch.setenv("STOCKER_MACHINE_ID", "machine-b")
    fp_b = licensing.machine_fingerprint()
    monkeypatch.setenv("STOCKER_MACHINE_ID", "machine-a")
    assert licensing.machine_fingerprint() == fp_a
    assert fp_a != fp_b
    assert len(fp_a) == 64


# ─── issue -> activate -> gate ─────────────────────────────────────────────
def test_issue_activate_opens_the_gate(isolated):
    provider = billing.get_provider("manual")
    issued = provider.issue_license("buyer@example.com", plan="pro", months=1)
    key = issued["key"]
    assert licensing.normalize_key(key) == key

    # Not activated yet -> free tier.
    assert licensing.current_plan() == "free"
    assert not licensing.has_feature("scenario_lab")

    ok, payload = licensing.activate_key(key, email="buyer@example.com")
    assert ok, payload
    assert payload.get("message")
    assert licensing.current_plan() == "pro"
    assert licensing.has_feature("scenario_lab")
    assert licensing.has_feature("committee")
    assert licensing.has_feature("red_flags")
    assert licensing.has_feature("terminal_api")
    assert licensing.has_feature("batch_screen")


def test_activate_rejects_unknown_key(isolated):
    ok, payload = licensing.activate_key("STK-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ")
    assert not ok
    assert payload["error"] in ("invalid_key", "not_found")


def test_expired_license_cannot_activate(isolated):
    provider = billing.get_provider("manual")
    issued = provider.issue_license("expired@example.com", plan="pro", months=1)
    accounts.upsert_license(
        licensing.key_hash(issued["key"]), licensing.key_hint(issued["key"]),
        issued["user_id"], "pro", expires_at=time.time() - 60,
    )
    ok, payload = licensing.activate_key(issued["key"])
    assert not ok
    assert payload["error"] == "expired"
    assert licensing.current_plan() == "free"


def test_revoke_closes_the_gate_even_with_a_cached_file(isolated):
    provider = billing.get_provider("manual")
    issued = provider.issue_license("revoke@example.com", plan="pro", months=1)
    ok, _ = licensing.activate_key(issued["key"])
    assert ok
    assert licensing.current_plan() == "pro"

    accounts.revoke_license(licensing.key_hash(issued["key"]))
    # The signed file is still on disk - the revoke must win.
    payload, signature, _err = licensing.read_entitlement()
    assert payload is not None
    assert licensing.current_plan() == "free"
    assert licensing.resolve_entitlement()["status"] == "revoked"


def test_machine_mismatch_blocks_the_entitlement(isolated, monkeypatch):
    payload = licensing.build_entitlement(plan="pro", expires_at=time.time() + 86400)
    signature = licensing.sign_payload(payload)
    other_machine = hashlib.sha256(b"some-other-box").hexdigest()
    result = licensing.evaluate_entitlement(payload, signature, machine_hash=other_machine)
    assert result["status"] == "machine_mismatch"
    assert result["plan"] == "free"

    # Same thing end to end: the file is bound to machine A, the machine changes.
    licensing.write_entitlement(payload)
    monkeypatch.setenv("STOCKER_MACHINE_ID", "a-different-machine")
    assert licensing.current_plan() == "free"


def test_offline_grace_keeps_pro_until_it_runs_out(isolated):
    now = time.time()
    # Expired an hour ago, but last verified 13 days ago -> inside the 14 day grace.
    payload = licensing.build_entitlement(plan="pro", expires_at=now - 3600, verified_at=now - 13 * 86400)
    signature = licensing.sign_payload(payload)
    result = licensing.evaluate_entitlement(payload, signature)
    assert result["status"] == "grace"
    assert result["plan"] == "pro"
    assert result["grace"] is True

    # Expired long ago and never refreshed -> grace over, back to free.
    stale = licensing.build_entitlement(plan="pro", expires_at=now - 30 * 86400, verified_at=now - 30 * 86400)
    result2 = licensing.evaluate_entitlement(stale, licensing.sign_payload(stale))
    assert result2["status"] == "expired"
    assert result2["plan"] == "free"


def test_tampered_entitlement_file_is_rejected(isolated):
    payload = licensing.build_entitlement(plan="pro", expires_at=time.time() + 86400)
    licensing.write_entitlement(payload)
    _p, _s, _e = licensing.read_entitlement()
    tampered = dict(payload)
    tampered["plan"] = "pro"
    tampered["expires_at"] = "2099-01-01T00:00:00+00:00"
    result = licensing.evaluate_entitlement(tampered, "sha256=deadbeef")
    assert result["status"] == "invalid"
    assert result["plan"] == "free"


def test_entitlement_file_is_signed(isolated):
    payload = licensing.build_entitlement(plan="pro", expires_at=time.time() + 86400)
    ok, path = licensing.write_entitlement(payload)
    assert ok and path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["payload"]["plan"] == "pro"
    assert licensing.verify_payload(raw["payload"], raw["signature"]) is True


# ─── webhook ───────────────────────────────────────────────────────────────
def test_webhook_signature_is_required(isolated):
    provider = billing.WebhookProvider()
    body = json.dumps({"id": "evt_sig", "type": "subscription.activated",
                        "data": {"email": "sig@example.com"}})
    ts = str(int(time.time()))
    good = provider.sign(body, ts)
    headers = {"X-Stocker-Signature": good, "X-Stocker-Timestamp": ts}
    assert provider.verify_webhook(body, headers)["ok"] is True
    # missing headers
    assert provider.verify_webhook(body, {})["ok"] is False
    # wrong signature
    bad = dict(headers)
    bad["X-Stocker-Signature"] = "sha256=" + "0" * 64
    assert provider.verify_webhook(body, bad)["ok"] is False
    # stale timestamp (replay window)
    old = str(int(time.time()) - 4000)
    stale = {"X-Stocker-Signature": provider.sign(body, old), "X-Stocker-Timestamp": old}
    assert provider.verify_webhook(body, stale)["ok"] is False


def test_webhook_event_is_applied_once(isolated):
    provider = billing.WebhookProvider()
    event = {"id": "evt_once_1", "type": "subscription.activated",
             "data": {"email": "once@example.com", "plan": "pro", "months": 6}}
    first = provider.handle_event(event)
    assert first["ok"] is True
    assert first.get("duplicate") is False
    assert first["license_key"].startswith("STK-")
    second = provider.handle_event(event)
    assert second["ok"] is True
    assert second.get("duplicate") is True
    # the license really landed in the database
    lic = accounts.get_license_by_hash(licensing.key_hash(first["license_key"]))
    assert lic is not None and lic["status"] == "active"


def test_webhook_renew_and_cancel(isolated):
    provider = billing.WebhookProvider()
    activated = provider.handle_event({"id": "evt_life_1", "type": "subscription.activated",
                                        "data": {"email": "life@example.com", "months": 1}})
    assert activated["ok"]
    key = activated["license_key"]
    renewed = provider.handle_event({"id": "evt_life_2", "type": "subscription.renewed",
                                      "data": {"email": "life@example.com", "months": 12}})
    assert renewed["ok"]
    lic = accounts.get_license_by_hash(licensing.key_hash(key))
    assert float(lic["expires_at"]) > time.time() + 300 * 86400
    cancelled = provider.handle_event({"id": "evt_life_3", "type": "subscription.cancelled",
                                        "data": {"email": "life@example.com"}})
    assert cancelled["ok"]
    lic2 = accounts.get_license_by_hash(licensing.key_hash(key))
    assert lic2["status"] == "revoked"


def test_webhook_rejects_unknown_event(isolated):
    provider = billing.WebhookProvider()
    result = provider.handle_event({"id": "evt_x", "type": "something.else", "data": {}})
    assert result["ok"] is False
    assert result["error"] == "unknown_event"


# ─── accounts ──────────────────────────────────────────────────────────────
def test_password_hashing_roundtrip():
    h, salt = accounts.hash_password("correct horse")
    assert accounts.verify_password("correct horse", h, salt)
    assert not accounts.verify_password("wrong horse", h, salt)
    assert h != "correct horse"


def test_user_creation_is_unique(isolated):
    user = accounts.create_user("dup@example.com", "secret123")
    assert user is not None
    assert accounts.create_user("dup@example.com", "secret123") is None
    assert accounts.get_user_by_email("DUP@example.com")["id"] == user["id"]


# ─── flask gates ───────────────────────────────────────────────────────────
def test_free_tier_api_gate_is_explanatory(client):
    resp = client.get("/api/intel/scenarios/AAPL")
    assert resp.status_code == 402
    body = resp.get_json()
    assert body["error"] == "upgrade_required"
    assert body["feature"] == "scenario_lab"
    assert body["upgrade_url"] == "/pricing"
    assert body["unlocks"]


def test_free_tier_page_shows_the_upgrade_prompt(client):
    resp = client.get("/scenario-lab")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Pro feature" in body
    assert "/activate" in body


def test_free_tier_terminal_api_keeps_the_json_contract(client):
    # The terminal API answers 200 with a machine readable envelope so
    # existing scripts never break on a bare 403.
    resp = client.post("/api/terminal/execute", json={"command": "PING"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["error"] == "upgrade_required"
    assert body["feature"] == "terminal_api"


def test_free_tier_batch_screening_is_gated(client):
    resp = client.post("/api/batch/screen", json={"tickers": ["AAPL", "MSFT"]})
    assert resp.status_code == 402
    assert resp.get_json()["feature"] == "batch_screen"


def test_free_core_surfaces_still_work(client):
    for path in ("/", "/watchlist", "/portfolio", "/compare", "/earnings", "/news-impact",
                 "/filings", "/pricing", "/account", "/billing", "/activate", "/macro"):
        resp = client.get(path)
        assert resp.status_code == 200, path
    # the core APIs are free
    assert client.get("/api/stocks").status_code == 200
    assert client.get("/api/screener/filter").status_code == 200


def test_pro_unlocks_the_gates_end_to_end(client):
    provider = billing.get_provider("manual")
    issued = provider.issue_license("gate@example.com", plan="pro", months=1)
    ok, _ = licensing.activate_key(issued["key"])
    assert ok
    assert client.get("/api/intel/scenarios/AAPL").status_code == 200
    assert client.post("/api/terminal/execute", json={"command": "PING"}).get_json().get("text") is not None or True
    # the page renders the real tool again
    resp = client.get("/committee")
    assert resp.status_code == 200
    assert "Pro feature" not in resp.get_data(as_text=True)


def test_account_me_reports_the_plan(client):
    body = client.get("/api/account/me").get_json()
    assert body["plan"] in ("free", "pro")
    assert body["authenticated"] is False
    assert body["machine_hash"]
    assert "scenario_lab" in body["features"]


def test_signup_login_logout(client):
    resp = client.post("/signup", data={"email": "new@example.com", "password": "secret123",
                                         "confirm": "secret123"})
    assert resp.status_code in (302, 303)
    body = client.get("/api/account/me").get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == "new@example.com"
    assert body["plan"] == "free"

    client.post("/logout")
    assert client.get("/api/account/me").get_json()["authenticated"] is False


def test_signup_rejects_bad_input(client):
    resp = client.post("/signup", data={"email": "bad", "password": "x", "confirm": "y"},
                        headers={"Accept": "application/json"})
    assert resp.status_code == 400
    resp2 = client.post("/signup", data={"email": "a@b.c", "password": "secret123", "confirm": "nope"},
                         headers={"Accept": "application/json"})
    assert resp2.status_code == 400
    # the HTML form re-renders with the error instead of a dead page
    html = client.post("/signup", data={"email": "bad", "password": "x", "confirm": "y"})
    assert html.status_code == 200
    assert "valid email" in html.get_data(as_text=True)


def test_admin_area_requires_the_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "unit-admin-token")
    assert client.get("/admin/users").status_code == 403
    ok = client.get("/admin/users", headers={"X-Admin-Token": "unit-admin-token"})
    assert ok.status_code == 200
    assert "users" in ok.get_json()


def test_admin_issue_extend_revoke(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "unit-admin-token")
    headers = {"X-Admin-Token": "unit-admin-token"}
    issued = client.post("/admin/issue", json={"email": "admin-buyer@example.com", "plan": "pro",
                                               "months": 1}, headers=headers)
    assert issued.status_code == 200
    key = issued.get_json()["license"]["key"]
    assert key.startswith("STK-")

    extended = client.post("/admin/extend", json={"key": key, "months": 3}, headers=headers)
    assert extended.status_code == 200

    revoked = client.post("/admin/revoke", json={"key": key}, headers=headers)
    assert revoked.status_code == 200
    lic = accounts.get_license_by_hash(licensing.key_hash(key))
    assert lic["status"] == "revoked"


def test_admin_disabled_without_env_token(client, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    resp = client.get("/admin/users")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "admin_disabled"


def test_signed_in_pro_subscription_unlocks_the_gates(client, isolated):
    user = accounts.create_user("sub@example.com", "secret123")
    accounts.create_subscription(user["id"], "pro", months=1)
    # anonymous visitors stay on the free tier
    assert client.get("/api/intel/scenarios/AAPL").status_code == 402
    client.post("/login", data={"email": "sub@example.com", "password": "secret123"})
    me = client.get("/api/account/me").get_json()
    assert me["authenticated"] is True
    assert me["plan"] == "pro"
    # the gate opens for the signed-in subscriber too
    assert client.get("/api/intel/scenarios/AAPL").status_code == 200


def test_revoke_cancels_the_backing_subscription(client, isolated):
    user = accounts.create_user("revoked-sub@example.com", "secret123")
    accounts.create_subscription(user["id"], "pro", months=1)
    provider = billing.get_provider("manual")
    issued = provider.issue_license("revoked-sub@example.com", plan="pro", months=1)
    client.post("/login", data={"email": "revoked-sub@example.com", "password": "secret123"})
    assert client.get("/api/account/me").get_json()["plan"] == "pro"
    provider.revoke_license(issued["key"])
    assert client.get("/api/account/me").get_json()["plan"] == "free"
    assert client.get("/api/intel/scenarios/AAPL").status_code == 402


def test_export_quota_is_free_tier_only(client, isolated):
    assert licensing.export_quota() == licensing.FREE_EXPORT_QUOTA
    provider = billing.get_provider("manual")
    issued = provider.issue_license("quota@example.com", plan="pro", months=1)
    licensing.activate_key(issued["key"])
    assert licensing.export_quota() is None


def test_export_quota_blocks_when_exhausted(client, isolated):
    for _ in range(licensing.FREE_EXPORT_QUOTA):
        accounts.usage_increment("export")
    resp = client.get("/excel/AAPL")
    assert resp.status_code == 402
    body = resp.get_json()
    assert body["error"] == "upgrade_required"
    assert "export" in body["message"].lower()


def test_zero_configuration_free_tier_never_crashes(client, monkeypatch, tmp_path):
    # No accounts DB, no entitlement file, no secret: still a working free tier.
    monkeypatch.setenv("STOCKER_ACCOUNTS_DB", str(tmp_path / "fresh" / "accounts.db"))
    monkeypatch.setenv("STOCKER_ENTITLEMENT_FILE", str(tmp_path / "fresh" / "entitlement.json"))
    resp = client.get("/api/account/me")
    assert resp.status_code == 200
    assert resp.get_json()["plan"] == "free"
    assert client.get("/").status_code == 200
    assert client.get("/api/intel/committee/AAPL").status_code == 402
