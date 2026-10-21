"""Licensing for StockerAI: keys, machine binding, signed entitlements, gates.

The terminal is a desktop app: the buyer runs it on their own machine and the
subscription is enforced the way real desktop software enforces it.

    1. A LICENSE KEY is handed over at checkout and entered once (/activate).
    2. The key is bound to the machine (hashed fingerprint of a stable machine id).
    3. The app verifies the key against an entitlement source (the local
       accounts DB when the app doubles as the control plane, or a remote
       entitlement endpoint when it does not) and caches a SIGNED entitlement
       file on disk.
    4. When the machine is offline the signed file is used, with a grace
       period (default 14 days) so the buyer is never locked out on a plane.

Signing uses HMAC-SHA256 with a secret from the environment - stdlib only, no
new dependency. See docs/SUBSCRIPTION.md for the operator runbook and for the
known trade-off of a shared secret (v2 should move to asymmetric signatures).

CLI
---
    python -m app.licensing issue --email buyer@x.com --plan pro --months 12
    python -m app.licensing list
    python -m app.licensing extend --key STK-... --months 12
    python -m app.licensing revoke --key STK-...
    python -m app.licensing bind --key STK-... --machine <fingerprint>
    python -m app.licensing seed
"""
import argparse
import functools
import hashlib
import hmac
import json
import logging
import os
import platform
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from .config import OUTPUT_DIR
except ImportError:  # flat import when app/ is on sys.path
    from config import OUTPUT_DIR

try:
    from . import accounts
except ImportError:  # flat import when app/ is on sys.path
    import accounts

logger = logging.getLogger(__name__)

# ─── plans ─────────────────────────────────────────────────────────────────
FREE_PLAN = "free"
PRO_PLAN = "pro"

PLANS = {
    FREE_PLAN: {
        "id": FREE_PLAN,
        "name": "StockerAI Free",
        "tier": 0,
        "price_month": 0,
        "price_year": 0,
        "tagline": "The whole quant core, on your own machine, forever free.",
        "features": [
            "Full analysis pipeline: DCF, WACC, Monte Carlo, Altman Z, Piotroski, Beneish, DuPont",
            "Live dashboard, watchlist, portfolio, compare + AI judge",
            "News impact, SEC filings, macro regime",
            "Screener: 21 filters + natural-language queries",
            "10 model exports per day (Excel + JSON)",
        ],
    },
    PRO_PLAN: {
        "id": PRO_PLAN,
        "name": "StockerAI Pro",
        "tier": 1,
        "price_month": 49,
        "price_year": 399,
        "price_lifetime": 999,
        "tagline": "The institutional desk: scenarios, committee, forensics, automation.",
        "features": [
            "Scenario Lab - bull / base / bear cases with Monte Carlo fan",
            "Investment Committee - multi-agent buy-side debate memo",
            "Red Flags - forensic scan (Beneish / Altman / DuPont)",
            "Headless terminal API for automation and scripting",
            "Batch screening - AI sweep across the whole coverage universe",
            "Unlimited model exports, priority quarterly auto-refresh",
        ],
    },
}

# Feature -> minimum plan. Every entry is a surface the free tier can see
# (the upgrade prompt always shows what is behind the gate).
FEATURE_PLANS = {
    "scenario_lab": PRO_PLAN,
    "committee": PRO_PLAN,
    "red_flags": PRO_PLAN,
    "terminal_api": PRO_PLAN,
    "batch_screen": PRO_PLAN,
    "unlimited_export": PRO_PLAN,
}

FEATURE_LABELS = {
    "scenario_lab": "Scenario Lab",
    "committee": "Investment Committee",
    "red_flags": "Red Flags forensic scan",
    "terminal_api": "Headless terminal API",
    "batch_screen": "Batch screening",
    "unlimited_export": "Unlimited model exports",
}

FREE_EXPORT_QUOTA = 10  # model exports per day, free tier

# ─── keys ──────────────────────────────────────────────────────────────────
KEY_PREFIX = "STK"
_KEY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32 (no I/L/O/U)
_KEY_BODY_LEN = 20
_KEY_CHECKSUM_LEN = 1
_HASH_SALT = b"stocker-license-v1"
_MACHINE_SALT = b"stocker-machine-v1"


def _now():
    return time.time()


def _iso(ts=None):
    if ts is None:
        ts = _now()
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _parse_iso(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


# ─── secrets ───────────────────────────────────────────────────────────────
def secret_path():
    return Path(OUTPUT_DIR) / ".license_secret"


def license_secret():
    """The HMAC secret. Env first, then a per-install file in output/.

    Zero-config installs get an auto-generated local secret, so signing never
    crashes a fresh checkout. Operators set STOCKER_LICENSE_SECRET so the
    control plane and the desktop app agree.
    """
    env = os.environ.get("STOCKER_LICENSE_SECRET") or os.environ.get("LICENSE_SECRET")
    if env and env.strip():
        return env.strip()
    path = secret_path()
    try:
        if path.exists():
            cached = path.read_text(encoding="utf-8").strip()
            if cached:
                return cached
    except Exception:
        pass
    generated = secrets.token_hex(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return generated


def canonical_json(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sign_payload(payload):
    """HMAC-SHA256 hex signature over the canonical payload."""
    return hmac.new(
        license_secret().encode("utf-8"), canonical_json(payload).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_payload(payload, signature):
    """Constant-time signature check. Never raises."""
    try:
        if not signature or not isinstance(payload, dict):
            return False
        return hmac.compare_digest(sign_payload(payload), str(signature))
    except Exception:
        return False


# ─── license keys ──────────────────────────────────────────────────────────
def _checksum_int(body):
    total = 0
    for idx, char in enumerate(body):
        value = _KEY_ALPHABET.index(char)
        total = (total + value * (idx + 1)) % (32 ** 2)
    return total


def _checksum_char(body):
    return _KEY_ALPHABET[_checksum_int(body) % 32]


def format_key(body):
    """Format a 20 char body into the canonical STK-XXXX-XXXX-XXXX-XXXX-XXXX."""
    groups = [body[i:i + 4] for i in range(0, len(body), 4)]
    return f"{KEY_PREFIX}-" + "-".join(groups)


def generate_license_key():
    """Random, human-transcribable license key with a check character."""
    body = "".join(secrets.choice(_KEY_ALPHABET) for _ in range(_KEY_BODY_LEN - _KEY_CHECKSUM_LEN))
    body += _checksum_char(body)
    return format_key(body)


def normalize_key(raw):
    """Canonicalise a pasted key. Returns None when the key is malformed.

    Accepts the short random key (``STK-XXXX-XXXX-XXXX-XXXX-XXXX``) and the
    self-signed offline key (``STK1.<payload>.<signature>``). The signed key is
    case sensitive (base64 payload), the short key is not.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text[:4].upper() == "STK1":
        return text if _signed_key_parts(text) else None
    compact = "".join(ch for ch in text.upper() if ch.isalnum())
    if compact.startswith("STK"):
        compact = compact[3:]
    if len(compact) != _KEY_BODY_LEN:
        return None
    if any(ch not in _KEY_ALPHABET for ch in compact):
        return None
    if _checksum_char(compact[:-1]) != compact[-1]:
        return None
    return format_key(compact)


def key_hash(key):
    """Stable hash of a license key (the plaintext is never stored)."""
    return hashlib.sha256(_HASH_SALT + str(key or "").encode("utf-8")).hexdigest()


def key_hint(key):
    """Last four characters of the key body, safe to display."""
    if not key:
        return ""
    compact = "".join(ch for ch in str(key).upper() if ch.isalnum())
    return compact[-4:] if len(compact) >= 4 else compact


def mask_key(key):
    """Display form: STK-****-****-****-****-ABCD."""
    if not key:
        return ""
    compact = "".join(ch for ch in str(key).upper() if ch.isalnum())
    if len(compact) <= 4:
        return "*" * 8
    return f"{KEY_PREFIX}-****-****-****-****-{compact[-4:]}"


# ─── self-signed offline keys ──────────────────────────────────────────────
def _b64e(raw):
    import base64
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text):
    import base64
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _signed_key_parts(key):
    """Split ``STK1.<payload>.<sig>`` into (payload_dict, signature)."""
    try:
        head, payload_b64, sig_b64 = str(key).split(".", 2)
        if head != "STK1":
            return None
        payload = json.loads(_b64d(payload_b64).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        return payload, sig_b64
    except Exception:
        return None


def issue_signed_key(plan=PRO_PLAN, months=1, email="", seats=1, expires_at=None):
    """Build a self-validating offline key (payload + HMAC signature).

    The buyer can activate this key on a machine with no network access to the
    control plane - the desktop app verifies the signature locally.
    """
    plan = plan if plan in PLANS else PRO_PLAN
    if expires_at is None and plan != FREE_PLAN:
        expires_at = _now() + (float(months or 1) * 30.0 * 86400.0)
    payload = {
        "v": 1,
        "plan": plan,
        "email": str(email or "").strip().lower(),
        "seats": int(seats or 1),
        "issued_at": _iso(),
        "expires_at": _iso(expires_at) if expires_at else None,
        "nonce": secrets.token_hex(8),
    }
    signature = sign_payload(payload)
    return f"STK1.{_b64e(canonical_json(payload).encode('utf-8'))}.{signature}", payload, signature


def verify_signed_key(key):
    """Validate a self-signed key. Returns (ok, payload, reason)."""
    parts = _signed_key_parts(str(key or "").strip())
    if not parts:
        return False, None, "malformed key"
    payload, signature = parts
    if not verify_payload(payload, signature):
        return False, None, "invalid signature"
    return True, payload, ""


# ─── machine binding ───────────────────────────────────────────────────────
def machine_id():
    """A stable per-machine identifier (no hardware serial numbers)."""
    override = os.environ.get("STOCKER_MACHINE_ID")
    if override and override.strip():
        return override.strip()
    if platform.system() == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    return str(guid)
        except Exception:
            pass
    else:
        for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id", "/var/db/dbus/machine-id"):
            try:
                path = Path(candidate)
                if path.exists():
                    value = path.read_text(encoding="utf-8").strip()
                    if value:
                        return value
            except Exception:
                continue
    try:
        node = platform.node() or "unknown"
    except Exception:
        node = "unknown"
    return f"{node}:{uuid.getnode()}"


def machine_fingerprint():
    """Hashed, stable fingerprint of this machine (64 hex chars)."""
    return hashlib.sha256(_MACHINE_SALT + str(machine_id()).encode("utf-8")).hexdigest()


# ─── entitlement file ──────────────────────────────────────────────────────
def entitlement_path():
    override = os.environ.get("STOCKER_ENTITLEMENT_FILE")
    if override:
        return Path(override)
    return Path(OUTPUT_DIR) / ".entitlement.json"


def grace_days():
    try:
        return max(0, int(os.environ.get("STOCKER_GRACE_DAYS", "14")))
    except Exception:
        return 14


def build_entitlement(plan=PRO_PLAN, license_key="", email="", expires_at=None, machine_hash=None,
                      source="manual", seats=1, verified_at=None):
    """Create the entitlement payload that gets signed and stored on disk."""
    now = _now()
    verified = verified_at if verified_at is not None else now
    grace_until = verified + (grace_days() * 86400.0)
    payload = {
        "v": 1,
        "plan": plan if plan in PLANS else PRO_PLAN,
        "license_key": license_key or "",
        "key_hint": key_hint(license_key),
        "email": str(email or "").strip().lower(),
        "seats": int(seats or 1),
        "issued_at": _iso(now),
        "expires_at": _iso(expires_at) if expires_at else None,
        "machine_hash": machine_hash or machine_fingerprint(),
        "source": source,
        "verified_at": _iso(verified),
        "grace_until": _iso(grace_until),
    }
    return payload


def write_entitlement(payload):
    """Sign and persist the entitlement file. Returns (ok, path)."""
    path = entitlement_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {"payload": payload, "signature": sign_payload(payload)}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))
        invalidate_cache()
        return True, path
    except Exception as e:
        logger.error(f"[Licensing] failed to write entitlement file: {e}")
        return False, path


def invalidate_cache():
    """Drop the per-request entitlement cache (after activate / revoke)."""
    try:
        from flask import g
        g._stocker_entitlement_cache = {}
    except Exception:
        pass


def read_entitlement():
    """Read the local entitlement file. Returns (payload, signature, error)."""
    path = entitlement_path()
    try:
        if not path.exists():
            return None, None, "no entitlement file"
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, None, f"unreadable entitlement file: {e}"
    if not isinstance(envelope, dict):
        return None, None, "malformed entitlement file"
    payload = envelope.get("payload")
    signature = envelope.get("signature")
    if not isinstance(payload, dict) or not signature:
        return None, None, "malformed entitlement file"
    return payload, signature, ""


def clear_entitlement():
    """Remove the local entitlement file (used on revoke / sign out)."""
    path = entitlement_path()
    invalidate_cache()
    try:
        if path.exists():
            path.unlink()
            return True
    except Exception as e:
        logger.error(f"[Licensing] failed to clear entitlement file: {e}")
    return False


def evaluate_entitlement(payload, signature, machine_hash=None, at=None):
    """Validate a signed entitlement against this machine and the clock.

    Returns a dict with ``status`` in
    active | grace | expired | machine_mismatch | invalid | none.
    """
    result = {
        "status": "none",
        "plan": FREE_PLAN,
        "grace": False,
        "reason": "",
        "expires_at": None,
        "grace_until": None,
        "license_key": "",
        "email": "",
        "source": "",
    }
    if not payload:
        result["reason"] = "No license activated on this machine."
        return result
    if not verify_payload(payload, signature):
        result["status"] = "invalid"
        result["reason"] = "Entitlement signature does not match - the file was tampered with."
        return result
    machine = machine_hash or machine_fingerprint()
    if payload.get("machine_hash") and payload.get("machine_hash") != machine:
        result["status"] = "machine_mismatch"
        result["reason"] = "This license is bound to a different machine."
        return result
    now = at if at is not None else _now()
    expires_at = _parse_iso(payload.get("expires_at"))
    grace_until = _parse_iso(payload.get("grace_until"))
    result["expires_at"] = payload.get("expires_at")
    result["grace_until"] = payload.get("grace_until")
    result["license_key"] = payload.get("license_key") or ""
    result["email"] = payload.get("email") or ""
    result["source"] = payload.get("source") or ""
    plan = payload.get("plan") if payload.get("plan") in PLANS else FREE_PLAN
    if expires_at is None or expires_at > now:
        result["status"] = "active"
        result["plan"] = plan
        result["reason"] = "Subscription active."
        return result
    if grace_until is not None and now <= grace_until:
        result["status"] = "grace"
        result["plan"] = plan
        result["grace"] = True
        result["reason"] = "Subscription expired - running in offline grace period."
        return result
    result["status"] = "expired"
    result["plan"] = FREE_PLAN
    result["reason"] = "Subscription expired."
    return result


# ─── plan resolution ───────────────────────────────────────────────────────
def _db_entitlement(machine_hash):
    """Entitlement granted by a license bound to this machine (local DB)."""
    try:
        rows = accounts.list_licenses(500)
    except Exception:
        return None
    best = None
    for lic in rows or []:
        if not lic.get("machine_hash") or lic.get("machine_hash") != machine_hash:
            continue
        if not accounts.license_is_active(lic):
            continue
        best = lic
        break
    return best


def _revoked_hashes():
    try:
        rows = accounts.list_licenses(500)
    except Exception:
        return set()
    return {
        accounts_key_hash_of(row) for row in (rows or [])
        if str(row.get("status") or "").lower() == "revoked" or row.get("revoked_at")
    }


def accounts_key_hash_of(license_row):
    """Key hash of a license row (stored hashed, never in plaintext)."""
    if not license_row:
        return ""
    hint = license_row.get("key_hint") or ""
    raw = license_row.get("key_hash") or ""
    return raw


def resolve_entitlement(user=None):
    """Resolve the effective entitlement of this machine.

    Sources, in order: a license bound to this machine in the local database,
    the signed entitlement file on disk. A revoked license always wins over
    the cached file so a revoke takes effect immediately.
    """
    try:
        from flask import g
        cache = getattr(g, "_stocker_entitlement_cache", None)
        if cache is None:
            cache = {}
            g._stocker_entitlement_cache = cache
        uid = (user or {}).get("id")
        if uid in cache:
            return cache[uid]
        resolved = _resolve_entitlement(user)
        cache[uid] = resolved
        return resolved
    except Exception:
        return _resolve_entitlement(user)


def _resolve_entitlement(user=None):
    machine = machine_fingerprint()
    result = {
        "plan": FREE_PLAN,
        "status": "none",
        "grace": False,
        "reason": "No license activated on this machine.",
        "source": "none",
        "license_key": "",
        "email": "",
        "expires_at": None,
        "grace_until": None,
        "machine_hash": machine,
        "features": {},
    }

    payload, signature, err = read_entitlement()
    file_eval = evaluate_entitlement(payload, signature, machine) if payload else None

    revoked = _revoked_hashes()
    if file_eval and payload:
        file_hash = key_hash(payload.get("license_key") or "")
        if file_hash and file_hash in revoked:
            file_eval = {
                "status": "revoked",
                "plan": FREE_PLAN,
                "grace": False,
                "reason": "This license was revoked.",
                "expires_at": payload.get("expires_at"),
                "grace_until": payload.get("grace_until"),
                "license_key": payload.get("license_key") or "",
                "email": payload.get("email") or "",
                "source": payload.get("source") or "",
            }

    lic = _db_entitlement(machine)
    if lic:
        result.update({
            "plan": lic.get("plan") if lic.get("plan") in PLANS else FREE_PLAN,
            "status": "active",
            "grace": False,
            "reason": "License active on this machine.",
            "source": "database",
            "license_key": "",
            "email": "",
            "expires_at": _iso(lic.get("expires_at")),
            "grace_until": None,
        })
        hint = lic.get("key_hint") or ""
        result["license_key"] = f"STK-****-****-****-****-{hint}" if hint else ""
    elif file_eval:
        result.update({
            "plan": file_eval["plan"],
            "status": file_eval["status"],
            "grace": file_eval["grace"],
            "reason": file_eval["reason"],
            "source": "file",
            "license_key": mask_key(file_eval.get("license_key")) if file_eval.get("license_key") else "",
            "email": file_eval.get("email") or "",
            "expires_at": file_eval.get("expires_at"),
            "grace_until": file_eval.get("grace_until"),
        })
    elif payload is None and err and err != "no entitlement file":
        result["reason"] = err

    # A signed-in user with an active pro subscription also unlocks Pro.
    if user and result["plan"] == FREE_PLAN:
        sub = accounts.get_subscription(user.get("id"))
        if accounts.subscription_is_active(sub) and sub.get("plan") == PRO_PLAN:
            result.update({
                "plan": PRO_PLAN,
                "status": "active",
                "source": "subscription",
                "reason": "Subscription active.",
                "expires_at": _iso(sub.get("expires_at")),
            })

    result["features"] = feature_map(result["plan"])
    return result


def feature_map(plan):
    """Which premium features a plan unlocks."""
    return {name: plan_allows(plan, required) for name, required in FEATURE_PLANS.items()}


def plan_allows(plan, required):
    """True when ``plan`` is at least as good as ``required``."""
    plan = plan if plan in PLANS else FREE_PLAN
    required = required if required in PLANS else FREE_PLAN
    return PLANS[plan]["tier"] >= PLANS[required]["tier"]


def current_plan(user=None):
    """The effective plan right now ('free' or 'pro').

    With no explicit user the signed-in session user is used, so a Pro
    subscription unlocks the same surfaces as an activated license.
    """
    try:
        if user is None:
            user = current_user()
        return resolve_entitlement(user).get("plan", FREE_PLAN)
    except Exception:
        return FREE_PLAN


def has_feature(feature, user=None):
    """True when the current entitlement unlocks ``feature``."""
    required = FEATURE_PLANS.get(feature)
    if not required:
        return True
    return plan_allows(current_plan(user), required)


def export_quota(user=None):
    """Model exports allowed per day for the current plan."""
    return None if has_feature("unlimited_export", user) else FREE_EXPORT_QUOTA


# ─── flask helpers ─────────────────────────────────────────────────────────
def current_user():
    """The signed-in user (None when anonymous). Never raises."""
    try:
        from flask import session
        uid = session.get("uid")
        if not uid:
            return None
        return accounts.get_user(uid)
    except Exception:
        return None


def upgrade_payload(feature, plan=PRO_PLAN):
    """Machine readable explanation of what an upgrade unlocks."""
    label = FEATURE_LABELS.get(feature, feature)
    return {
        "error": "upgrade_required",
        "message": f"{label} is a Pro feature. Activate a Pro license key to unlock it.",
        "feature": feature,
        "feature_label": label,
        "required_plan": plan,
        "upgrade_url": "/pricing",
        "activate_url": "/activate",
        "unlocks": PLANS[plan]["features"],
        "price_month": PLANS[plan]["price_month"],
        "price_year": PLANS[plan]["price_year"],
    }


def upgrade_response(feature, plan=PRO_PLAN, status=402):
    """Render the upgrade prompt: JSON for APIs, the upgrade page for pages."""
    payload = upgrade_payload(feature, plan)
    try:
        from flask import jsonify, render_template, request
        if request.path.startswith("/api/"):
            return jsonify(payload), status
        return render_template(
            "upgrade.html",
            feature=feature,
            feature_label=payload["feature_label"],
            required_plan=plan,
            plan=PLANS[plan],
        ), 200
    except Exception:
        return payload, status


def plan_guard(feature, status=402):
    """Return a response when ``feature`` is locked, otherwise None.

    Pages get the upgrade prompt (HTTP 200). APIs get HTTP 402 with a machine
    readable explanation of what the upgrade unlocks.
    """
    try:
        if has_feature(feature):
            return None
        return upgrade_response(feature, FEATURE_PLANS.get(feature, PRO_PLAN), status=status)
    except Exception as e:
        logger.error(f"[Licensing] plan_guard failed on {feature}: {e}")
        return None


def requires_plan(plan, feature=None, status=402):
    """Route decorator enforcing a plan.

    Pages render the upgrade prompt (HTTP 200, never a dead 403). APIs return
    HTTP 402 with a machine readable explanation of what is missing.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                ent = resolve_entitlement(current_user())
                if not plan_allows(ent.get("plan", FREE_PLAN), plan):
                    return upgrade_response(feature or plan, plan, status=status)
            except Exception as e:  # never let the gate itself break the app
                logger.error(f"[Licensing] gate error on {fn.__name__}: {e}")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def inject_plan_context():
    """Template context: current plan, badge and upgrade link."""
    try:
        ent = resolve_entitlement(current_user())
    except Exception:
        ent = {"plan": FREE_PLAN, "status": "none", "reason": "", "expires_at": None}
    plan = ent.get("plan", FREE_PLAN)
    return {
        "current_plan": plan,
        "current_plan_name": PLANS.get(plan, PLANS[FREE_PLAN])["name"],
        "plan_badge": "PRO" if plan == PRO_PLAN else "FREE",
        "entitlement": ent,
        "plans": PLANS,
        "feature_labels": FEATURE_LABELS,
        "upgrade_url": "/pricing",
    }


# ─── activation ────────────────────────────────────────────────────────────
def activate_key(raw_key, email="", source="manual", user=None):
    """Validate a license key and activate it on this machine.

    Order of resolution:
      1. self-signed offline key  (STK1....)  - verified locally with the HMAC secret
      2. local database lookup     (this machine is the control plane)
      3. remote entitlement endpoint (STOCKER_ENTITLEMENT_URL)

    Returns (ok, payload_dict) where payload carries ``error`` on failure.
    """
    key = normalize_key(raw_key)
    if not key:
        return False, {"error": "invalid_key", "message": "That does not look like a StockerAI license key."}

    # 1. self-signed offline key
    if key.startswith("STK1."):
        ok, payload, reason = verify_signed_key(key)
        if not ok:
            return False, {"error": "invalid_key", "message": f"License key rejected: {reason}."}
        expires_at = _parse_iso(payload.get("expires_at"))
        if expires_at is not None and expires_at <= _now():
            return False, {"error": "expired", "message": "This license key has expired."}
        ent = build_entitlement(
            plan=payload.get("plan", PRO_PLAN),
            license_key=key,
            email=payload.get("email") or email,
            expires_at=expires_at,
            source="offline-key",
            seats=payload.get("seats", 1),
        )
        wrote, path = write_entitlement(ent)
        if not wrote:
            return False, {"error": "write_failed", "message": f"Could not write the entitlement file at {path}."}
        accounts.audit("activate", actor=email or "local", target=mask_key(key), detail="offline signed key")
        return True, {"entitlement": ent, "message": "Pro activated on this machine."}

    # 2. local database
    lic = accounts.get_license_by_hash(key_hash(key))
    if lic:
        if str(lic.get("status") or "").lower() != "active" or lic.get("revoked_at"):
            return False, {"error": "revoked", "message": "This license has been revoked."}
        if not accounts.license_is_active(lic):
            return False, {"error": "expired", "message": "This license has expired."}
        machine = machine_fingerprint()
        bound = lic.get("machine_hash")
        if bound and bound != machine:
            return False, {
                "error": "machine_mismatch",
                "message": "This license is bound to a different machine.",
            }
        expires_at = lic.get("expires_at")
        user_id = lic.get("user_id")
        if bound is None:
            accounts.bind_license(accounts_key_hash_of(lic) or key_hash(key), machine)
        ent = build_entitlement(
            plan=lic.get("plan", PRO_PLAN),
            license_key=key,
            email=(accounts.get_user(user_id) or {}).get("email", "") if user_id else "",
            expires_at=expires_at,
            source="database",
            seats=lic.get("seats", 1),
        )
        wrote, path = write_entitlement(ent)
        if not wrote:
            return False, {"error": "write_failed", "message": f"Could not write the entitlement file at {path}."}
        if user_id:
            accounts.record_entitlement(user_id, ent["plan"], machine, expires_at,
                                        source="database", license_hash=key_hash(key),
                                        payload=canonical_json(ent))
        accounts.audit("activate", actor=email or "local", target=mask_key(key), detail="database license")
        return True, {"entitlement": ent, "message": "Pro activated on this machine."}

    # 3. remote entitlement endpoint
    endpoint = os.environ.get("STOCKER_ENTITLEMENT_URL", "").strip()
    if endpoint:
        result = _activate_remote(endpoint, key, email)
        if result.get("ok"):
            return True, result
        return False, result

    return False, {
        "error": "not_found",
        "message": "This license key was not found. Check the key, or ask the operator to re-issue it.",
    }


def _activate_remote(endpoint, key, email=""):
    """Validate a key against the operator's entitlement service."""
    import urllib.error
    import urllib.request
    machine = machine_fingerprint()
    body = json.dumps({"key": key, "machine_hash": machine, "email": email}).encode("utf-8")
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/api/entitlement/verify",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {}
        return {"ok": False, "error": data.get("error", "remote_error"),
                "message": data.get("message", f"Entitlement service returned HTTP {e.code}.")}
    except Exception as e:
        return {"ok": False, "error": "offline", "message": f"Could not reach the entitlement service: {e}"}
    payload = data.get("payload")
    signature = data.get("signature")
    if not isinstance(payload, dict) or not verify_payload(payload, signature):
        return {"ok": False, "error": "invalid_signature",
                "message": "The entitlement service returned an unverifiable entitlement."}
    if payload.get("machine_hash") and payload.get("machine_hash") != machine:
        return {"ok": False, "error": "machine_mismatch",
                "message": "This license is bound to a different machine."}
    wrote, path = write_entitlement(payload)
    if not wrote:
        return {"ok": False, "error": "write_failed",
                "message": f"Could not write the entitlement file at {path}."}
    accounts.audit("activate", actor=email or "local", target=mask_key(key), detail="remote entitlement")
    return {"ok": True, "entitlement": payload, "message": "Pro activated on this machine."}


# ─── CLI ───────────────────────────────────────────────────────────────────
def _print_plan(ent):
    print(f"  plan      : {ent.get('plan')}")
    print(f"  status    : {ent.get('status')}")
    print(f"  source    : {ent.get('source')}")
    print(f"  expires   : {ent.get('expires_at') or 'never'}")
    if ent.get("grace_until"):
        print(f"  grace till: {ent.get('grace_until')}")
    print(f"  machine   : {ent.get('machine_hash')}")


def _seed_accounts():
    """Create the demo pro + free accounts and their licenses."""
    accounts.init_db()
    created = []
    demo = [
        ("demo@stocker.ai", "demo1234", PRO_PLAN, "Pro demo account"),
        ("free@stocker.ai", "free1234", FREE_PLAN, "Free demo account"),
    ]
    for email, password, plan, notes in demo:
        user = accounts.get_user_by_email(email) or accounts.create_user(email, password, username=email.split("@")[0])
        if not user:
            print(f"  ! could not create {email}")
            continue
        accounts.set_password(user["id"], password)
        if plan == PRO_PLAN:
            accounts.create_subscription(user["id"], PRO_PLAN, months=12, source="seed")
            key = generate_license_key()
            accounts.upsert_license(key_hash(key), key_hint(key), user["id"], PRO_PLAN,
                                    expires_at=_now() + 365 * 86400.0, notes=notes, source="seed")
            created.append((email, password, plan, key))
        else:
            accounts.create_subscription(user["id"], FREE_PLAN, status="active", source="seed")
            created.append((email, password, plan, ""))
    accounts.audit("seed", actor="cli", target="demo accounts", detail="seeded demo + free accounts")
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m app.licensing",
        description="StockerAI license key + subscription operator CLI.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_issue = sub.add_parser("issue", help="issue a license key (and subscription) for a user")
    p_issue.add_argument("--email", required=True)
    p_issue.add_argument("--plan", default=PRO_PLAN, choices=[FREE_PLAN, PRO_PLAN])
    p_issue.add_argument("--months", type=float, default=12)
    p_issue.add_argument("--lifetime", action="store_true", help="perpetual license (no expiry)")
    p_issue.add_argument("--seats", type=int, default=1)
    p_issue.add_argument("--notes", default="")
    p_issue.add_argument("--signed", action="store_true",
                         help="issue a self-validating offline key (STK1....) instead of a short key")

    sub.add_parser("list", help="list licenses and subscriptions")

    p_extend = sub.add_parser("extend", help="extend a subscription")
    p_extend.add_argument("--key", default="")
    p_extend.add_argument("--email", default="")
    p_extend.add_argument("--months", type=float, default=12)

    p_revoke = sub.add_parser("revoke", help="revoke a license")
    p_revoke.add_argument("--key", default="")
    p_revoke.add_argument("--email", default="")

    p_bind = sub.add_parser("bind", help="bind a license to a machine fingerprint")
    p_bind.add_argument("--key", required=True)
    p_bind.add_argument("--machine", required=True, help="machine fingerprint (64 hex chars)")

    sub.add_parser("seed", help="create the demo pro + free accounts")
    sub.add_parser("verify", help="verify this machine's entitlement")
    sub.add_parser("entitlement", help="print the signed entitlement payload for this machine")
    sub.add_parser("machine", help="print this machine's fingerprint")

    args = parser.parse_args(argv)
    accounts.init_db()

    if args.cmd == "issue":
        user = accounts.get_user_by_email(args.email)
        if not user:
            user = accounts.create_user(args.email, None, username=args.email.split("@")[0])
            if not user:
                print("! could not create the user")
                return 1
        expires_at = None if args.lifetime else (_now() + args.months * 30.0 * 86400.0)
        accounts.create_subscription(user["id"], args.plan, months=args.months, expires_at=expires_at,
                                    source="manual")
        if args.signed:
            key, payload, _sig = issue_signed_key(args.plan, args.months, args.email, args.seats, expires_at)
            accounts.upsert_license(key_hash(key), key_hint(key), user["id"], args.plan,
                                    expires_at=expires_at, seats=args.seats, notes=args.notes, source="manual")
            print(f"license key (self-signed, offline):\n  {key}")
        else:
            key = generate_license_key()
            accounts.upsert_license(key_hash(key), key_hint(key), user["id"], args.plan,
                                    expires_at=expires_at, seats=args.seats, notes=args.notes, source="manual")
            print(f"license key:\n  {key}")
        accounts.audit("issue", actor="cli", target=args.email, detail=f"plan={args.plan}")
        print(f"  email   : {args.email}")
        print(f"  plan    : {args.plan}")
        print(f"  expires : {_iso(expires_at) or 'never'}")
        print(f"  machine : {machine_fingerprint()}  (share with the buyer for --bind)")
        return 0

    if args.cmd == "list":
        print("LICENSES")
        for lic in accounts.list_licenses(50):
            print(f"  {mask_key_from_row(lic)}  plan={lic.get('plan'):<4} status={lic.get('status'):<8} "
                  f"user={lic.get('user_id')} expires={_iso(lic.get('expires_at')) or 'never'} "
                  f"machine={(lic.get('machine_hash') or '-')[:12]}")
        print("SUBSCRIPTIONS")
        for sub in accounts.list_subscriptions(50):
            user = accounts.get_user(sub.get("user_id")) or {}
            print(f"  {user.get('email', '?'):<28} plan={sub.get('plan'):<4} status={sub.get('status'):<8} "
                  f"expires={_iso(sub.get('expires_at')) or 'never'}")
        print("USERS")
        for user in accounts.list_users(50):
            print(f"  {user.get('email', '?'):<28} role={user.get('role'):<6} plan={user.get('plan')}")
        return 0

    if args.cmd == "extend":
        lic = _find_license(args.key, args.email)
        if not lic:
            print("! license not found")
            return 1
        updated = accounts.extend_license(lic["key_hash"], args.months)
        accounts.audit("extend", actor="cli", target=lic.get("key_hint"), detail=f"months={args.months}")
        print(f"extended to {_iso(updated.get('expires_at')) or 'never'}")
        return 0

    if args.cmd == "revoke":
        lic = _find_license(args.key, args.email)
        if not lic:
            print("! license not found")
            return 1
        accounts.revoke_license_and_subscription(lic["key_hash"])
        clear_entitlement()
        accounts.audit("revoke", actor="cli", target=lic.get("key_hint"), detail="revoked by operator")
        print("revoked")
        return 0

    if args.cmd == "bind":
        lic = accounts.get_license_by_hash(key_hash(normalize_key(args.key) or ""))
        if not lic:
            print("! license not found")
            return 1
        accounts.bind_license(lic["key_hash"], args.machine.strip().lower())
        accounts.audit("bind", actor="cli", target=lic.get("key_hint"), detail=f"machine={args.machine[:12]}")
        print(f"bound to {args.machine}")
        return 0

    if args.cmd == "seed":
        created = _seed_accounts()
        print("SEEDED")
        for email, password, plan, key in created:
            print(f"  {email:<22} password={password:<10} plan={plan:<5} key={key or '-'}")
        return 0

    if args.cmd == "verify":
        ent = resolve_entitlement()
        _print_plan(ent)
        print(f"  reason   : {ent.get('reason')}")
        return 0

    if args.cmd == "entitlement":
        payload, signature, err = read_entitlement()
        if not payload:
            print(f"! {err}")
            return 1
        print(json.dumps({"payload": payload, "signature": signature}, indent=2))
        return 0

    if args.cmd == "machine":
        print(machine_fingerprint())
        return 0

    parser.print_help()
    return 0


def mask_key_from_row(row):
    hint = row.get("key_hint") or ""
    return f"STK-****-****-****-****-{hint}" if hint else "STK-****"


def _find_license(key="", email=""):
    if key:
        normalized = normalize_key(key)
        lic = accounts.get_license_by_hash(key_hash(normalized)) if normalized else None
        if lic:
            return lic
    if email:
        user = accounts.get_user_by_email(email)
        if user:
            lic = accounts.get_license_for_user(user["id"])
            if lic:
                return lic
    return None


if __name__ == "__main__":
    raise SystemExit(main())
