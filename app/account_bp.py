"""Account, billing and admin routes for StockerAI.

Registered as a Flask blueprint so app/server.py stays a routing surface and
not an account system. Routes:

    /signup              create the local account (free tier)
    /login  /logout      local session
    /account             plan, entitlement, machine fingerprint, usage
    /billing             plan + license key entry + checkout pointer
    /activate            enter a license key (one time)
    /pricing             the tier comparison / upgrade page
    /api/account/me      machine readable account state
    /api/billing/webhook signed subscription events from a checkout platform
    /api/entitlement/verify  control-plane key check (used by desktop clients)
    /admin/*             operator console protected by ADMIN_TOKEN
"""
import logging
import os

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

try:
    from . import accounts
except ImportError:  # flat import when app/ is on sys.path
    import accounts

try:
    from . import billing
except ImportError:  # flat import when app/ is on sys.path
    import billing

try:
    from . import licensing
except ImportError:  # flat import when app/ is on sys.path
    import licensing

logger = logging.getLogger(__name__)

bp = Blueprint("account", __name__)


# ─── helpers ───────────────────────────────────────────────────────────────
def admin_token():
    return (os.environ.get("ADMIN_TOKEN") or "").strip()


def admin_authorized():
    """ADMIN_TOKEN from env, presented as header, query arg or form field."""
    token = admin_token()
    if not token:
        return False
    supplied = request.headers.get("X-Admin-Token") or request.args.get("token") or ""
    if not supplied and request.method == "POST":
        supplied = (request.form.get("token") or "").strip()
    return bool(supplied) and supplied == token


def require_admin():
    """Returns (ok, payload). Never raises."""
    if not admin_token():
        return False, (jsonify({
            "error": "admin_disabled",
            "message": "The admin area is disabled. Set ADMIN_TOKEN in the environment to enable it.",
        }), 403)
    if not admin_authorized():
        return False, (jsonify({
            "error": "forbidden",
            "message": "Invalid admin token. Send it as the X-Admin-Token header, ?token= or the token field.",
        }), 403)
    return True, None


def signed_in_user():
    return licensing.current_user()


def account_state():
    """The full account/entitlement picture used by pages and /api/account/me."""
    user = signed_in_user()
    ent = licensing.resolve_entitlement(user)
    state = {
        "user": {
            "id": (user or {}).get("id"),
            "email": (user or {}).get("email"),
            "role": (user or {}).get("role"),
            "created_at": licensing._iso((user or {}).get("created_at")),
        } if user else None,
        "authenticated": bool(user),
        "plan": ent.get("plan", licensing.FREE_PLAN),
        "plan_name": licensing.PLANS.get(ent.get("plan"), licensing.PLANS[licensing.FREE_PLAN])["name"],
        "status": ent.get("status", "none"),
        "grace": bool(ent.get("grace")),
        "reason": ent.get("reason", ""),
        "source": ent.get("source", "none"),
        "expires_at": ent.get("expires_at"),
        "grace_until": ent.get("grace_until"),
        "machine_hash": ent.get("machine_hash"),
        "license_key": ent.get("license_key", ""),
        "features": ent.get("features", {}),
        "export_quota": licensing.export_quota(user),
        "exports_today": accounts.usage_count("export"),
        "billing": billing.provider_status(),
        "plans": licensing.PLANS,
    }
    return state


def _wants_json():
    if request.path.startswith("/api/"):
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept and "text/html" not in accept


# ─── auth pages ────────────────────────────────────────────────────────────
@bp.route("/signup", methods=["GET", "POST"])
def signup():
    error = ""
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if not email or "@" not in email:
            error = "Enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif accounts.get_user_by_email(email):
            error = "That email already has an account - log in instead."
        else:
            user = accounts.create_user(email, password, username=email.split("@")[0])
            if not user:
                error = "Could not create the account."
            else:
                accounts.create_subscription(user["id"], licensing.FREE_PLAN, status="active", source="signup")
                accounts.audit("signup", actor=email, target=email, detail="local account created")
                session["uid"] = user["id"]
                return redirect(url_for("account.account"))
    if _wants_json():
        return jsonify({"error": error or None, "account": account_state()}), (400 if error else 200)
    return render_template("auth.html", mode="signup", error=error, email=email,
                           plan=licensing.PLANS[licensing.FREE_PLAN])


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = accounts.get_user_by_email(email)
        if not user:
            error = "No account for that email."
        elif not accounts.verify_password(password, user.get("password_hash"), user.get("password_salt")):
            error = "Wrong password."
        else:
            accounts.touch_login(user["id"])
            accounts.audit("login", actor=email, target=email, detail="session opened")
            session["uid"] = user["id"]
            return redirect(url_for("account.account"))
    if _wants_json():
        return jsonify({"error": error or None, "account": account_state()}), (400 if error else 200)
    return render_template("auth.html", mode="login", error=error, email=email,
                           plan=licensing.PLANS[licensing.FREE_PLAN])


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    user = signed_in_user()
    if user:
        accounts.audit("logout", actor=user.get("email"), target=user.get("email"), detail="session closed")
    session.pop("uid", None)
    if _wants_json():
        return jsonify({"ok": True, "account": account_state()})
    return redirect(url_for("account.account"))


# ─── account / billing ─────────────────────────────────────────────────────
@bp.route("/account")
def account():
    state = account_state()
    if _wants_json():
        return jsonify(state)
    return render_template("account.html", state=state, state_json=state)


@bp.route("/billing")
def billing_page():
    state = account_state()
    provider = billing.get_provider()
    checkout = provider.create_checkout(plan=licensing.PRO_PLAN, email=(state.get("user") or {}).get("email", ""))
    if _wants_json():
        return jsonify({"account": state, "checkout": checkout})
    return render_template("billing.html", state=state, checkout=checkout)


@bp.route("/activate", methods=["GET", "POST"])
def activate():
    state = account_state()
    error = ""
    ok = False
    if request.method == "POST":
        raw_key = (request.form.get("key") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        if not raw_key:
            error = "Paste the license key you received at checkout."
        else:
            success, payload = licensing.activate_key(raw_key, email=email, source="activate")
            ok = bool(success)
            if ok:
                accounts.audit("activate.success", actor=email or "local",
                               target=licensing.mask_key(raw_key), detail="pro unlocked")
                state = account_state()
                if request.form.get("json"):
                    return jsonify({"ok": True, "message": payload.get("message"), "account": state})
                return redirect(url_for("account.account"))
            error = payload.get("message") or "Could not activate that key."
            accounts.audit("activate.failed", actor=email or "local",
                           target=licensing.mask_key(raw_key), detail=error)
    if _wants_json():
        return jsonify({"error": error or None, "ok": ok, "account": state}), (400 if error else 200)
    return render_template("activate.html", state=state, error=error, ok=ok)


@bp.route("/pricing")
@bp.route("/upgrade")
def pricing():
    state = account_state()
    if _wants_json():
        return jsonify({"plans": licensing.PLANS, "account": state})
    return render_template("pricing.html", state=state)


@bp.route("/api/account/me")
def api_account_me():
    return jsonify(account_state())


# ─── control plane + webhook ───────────────────────────────────────────────
@bp.route("/api/entitlement/verify", methods=["POST"])
def api_entitlement_verify():
    """Control-plane endpoint: desktop clients check their key here."""
    expected = (os.environ.get("STOCKER_ENTITLEMENT_API_TOKEN") or "").strip()
    if expected:
        supplied = request.headers.get("X-Entitlement-Token") or ""
        if supplied != expected:
            return jsonify({"error": "forbidden", "message": "Invalid entitlement API token."}), 403
    payload = request.get_json(silent=True) or {}
    key = licensing.normalize_key(payload.get("key") or "")
    machine = (payload.get("machine_hash") or "").strip().lower()
    if not key:
        return jsonify({"error": "invalid_key", "message": "A license key is required."}), 400
    lic = accounts.get_license_by_hash(licensing.key_hash(key))
    if not lic:
        return jsonify({"error": "not_found", "message": "Unknown license key."}), 404
    if str(lic.get("status") or "").lower() != "active" or lic.get("revoked_at"):
        return jsonify({"error": "revoked", "message": "This license has been revoked."}), 403
    if not accounts.license_is_active(lic):
        return jsonify({"error": "expired", "message": "This license has expired."}), 403
    if machine:
        bound = lic.get("machine_hash")
        if bound and bound != machine:
            return jsonify({"error": "machine_mismatch",
                            "message": "This license is bound to a different machine."}), 409
        if not bound:
            accounts.bind_license(lic["key_hash"], machine)
    ent = licensing.build_entitlement(
        plan=lic.get("plan", licensing.PRO_PLAN),
        license_key=key,
        email=(accounts.get_user(lic.get("user_id")) or {}).get("email", "") if lic.get("user_id") else "",
        expires_at=lic.get("expires_at"),
        machine_hash=machine or licensing.machine_fingerprint(),
        source="control-plane",
        seats=lic.get("seats", 1),
    )
    signature = licensing.sign_payload(ent)
    accounts.audit("entitlement.issued", actor="control-plane",
                   target=licensing.mask_key(key), detail=f"machine={str(machine)[:12]}")
    return jsonify({"payload": ent, "signature": signature, "plan": ent["plan"]})


@bp.route("/api/billing/webhook", methods=["POST"])
def api_billing_webhook():
    """Signed subscription events from the checkout platform (idempotent)."""
    provider = billing.get_provider()
    if not provider.supports_webhook:
        return jsonify({
            "error": "webhook_not_supported",
            "message": "This installation does not accept billing webhooks. Set BILLING_PROVIDER=webhook.",
        }), 501
    body = request.get_data(cache=False) or b""
    check = provider.verify_webhook(body, request.headers)
    if not check.get("ok"):
        accounts.audit("webhook.rejected", actor="webhook", target=request.path,
                       detail=str(check.get("error")))
        return jsonify({"error": check.get("error"), "message": check.get("message")}), 400
    result = provider.handle_event(check["event"])
    accounts.audit("webhook.applied", actor="webhook", target=request.path,
                   detail=f"type={result.get('type')} duplicate={result.get('duplicate')}")
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── admin console ─────────────────────────────────────────────────────────
@bp.route("/admin")
def admin_home():
    ok, failure = require_admin()
    if not ok:
        return failure
    state = {
        "provider": billing.provider_status(),
        "users": accounts.list_users(50),
        "licenses": accounts.list_licenses(50),
        "audit": accounts.list_audit(50),
        "machine_hash": licensing.machine_fingerprint(),
    }
    if _wants_json():
        return jsonify(state)
    return render_template("admin.html", state=state)


@bp.route("/admin/users")
def admin_users():
    ok, failure = require_admin()
    if not ok:
        return failure
    return jsonify({"users": accounts.list_users(200), "subscriptions": accounts.list_subscriptions(200)})


@bp.route("/admin/audit")
def admin_audit():
    ok, failure = require_admin()
    if not ok:
        return failure
    return jsonify({"audit": accounts.list_audit(200)})


@bp.route("/admin/issue", methods=["POST"])
def admin_issue():
    ok, failure = require_admin()
    if not ok:
        return failure
    payload = request.get_json(silent=True) or request.form
    email = (payload.get("email") or "").strip().lower()
    plan = (payload.get("plan") or licensing.PRO_PLAN).strip().lower()
    try:
        months = float(payload.get("months") or 12)
    except Exception:
        months = 12
    lifetime = str(payload.get("lifetime") or "").lower() in ("1", "true", "yes", "on")
    try:
        issued = billing.get_provider().issue_license(
            email, plan=plan, months=months,
            seats=int(payload.get("seats") or 1),
            notes=str(payload.get("notes") or ""),
            lifetime=lifetime,
        )
    except billing.BillingError as e:
        return jsonify({"error": "issue_failed", "message": str(e)}), 400
    return jsonify({"ok": True, "license": issued})


@bp.route("/admin/extend", methods=["POST"])
def admin_extend():
    ok, failure = require_admin()
    if not ok:
        return failure
    payload = request.get_json(silent=True) or request.form
    key = (payload.get("key") or "").strip()
    try:
        months = float(payload.get("months") or 12)
    except Exception:
        months = 12
    try:
        result = billing.get_provider().extend_license(key, months)
    except billing.BillingError as e:
        return jsonify({"error": "extend_failed", "message": str(e)}), 400
    return jsonify({"ok": True, **result})


@bp.route("/admin/revoke", methods=["POST"])
def admin_revoke():
    ok, failure = require_admin()
    if not ok:
        return failure
    payload = request.get_json(silent=True) or request.form
    key = (payload.get("key") or "").strip()
    try:
        result = billing.get_provider().revoke_license(key)
    except billing.BillingError as e:
        return jsonify({"error": "revoke_failed", "message": str(e)}), 400
    licensing.clear_entitlement()
    return jsonify({"ok": True, **result})


@bp.route("/admin/bind", methods=["POST"])
def admin_bind():
    ok, failure = require_admin()
    if not ok:
        return failure
    payload = request.get_json(silent=True) or request.form
    key = (payload.get("key") or "").strip()
    machine = (payload.get("machine_hash") or "").strip().lower()
    if not machine:
        return jsonify({"error": "bad_request", "message": "machine_hash is required."}), 400
    try:
        result = billing.get_provider().bind_license(key, machine)
    except billing.BillingError as e:
        return jsonify({"error": "bind_failed", "message": str(e)}), 400
    return jsonify({"ok": True, **result})


# ─── wiring ────────────────────────────────────────────────────────────────
def init_app(app):
    """Register the blueprint and the shared template context."""
    app.register_blueprint(bp)

    @app.context_processor
    def _inject_account():
        try:
            return licensing.inject_plan_context()
        except Exception:
            return {"current_plan": licensing.FREE_PLAN, "plan_badge": "FREE",
                    "entitlement": {}, "plans": licensing.PLANS,
                    "feature_labels": licensing.FEATURE_LABELS, "upgrade_url": "/pricing"}

    return app
