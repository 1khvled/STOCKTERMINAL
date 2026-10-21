"""Account, subscription and license storage for StockerAI.

Pure stdlib ``sqlite3`` - no ORM, no driver, no new dependency. The database
lives in ``output/accounts.db`` which is gitignored together with the rest of
``output/`` (the local terminal's own data directory).

Tables
------
users            local buyer accounts (email + pbkdf2 password hash, role)
subscriptions    plan + period per user (plan, status, started/expires)
licenses         issued license keys (hashed), plan, expiry, machine binding
entitlements     entitlement snapshots cached for this machine
audit_log        operator + app level audit trail (who did what, when)
usage_counters   daily counters used by the free-tier export quota
processed_events webhook idempotency ledger (event_id -> result)

Everything is defensive: a missing/corrupt database must never crash the
terminal, it degrades to "no accounts" (free tier).
"""
import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from config import OUTPUT_DIR
except ImportError:
    from .config import OUTPUT_DIR

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("STOCKER_ACCOUNTS_DB") or (Path(OUTPUT_DIR) / "accounts.db"))

PBKDF2_ITERATIONS = 200_000
FREE_PLAN = "free"
PRO_PLAN = "pro"
VALID_PLANS = (FREE_PLAN, PRO_PLAN)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    username      TEXT,
    password_hash TEXT,
    password_salt TEXT,
    role          TEXT NOT NULL DEFAULT 'user',
    plan          TEXT NOT NULL DEFAULT 'free',
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    REAL NOT NULL,
    last_login_at REAL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              INTEGER NOT NULL,
    plan                 TEXT NOT NULL DEFAULT 'free',
    status               TEXT NOT NULL DEFAULT 'active',
    started_at           REAL NOT NULL,
    expires_at           REAL,
    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
    source               TEXT NOT NULL DEFAULT 'manual',
    external_ref         TEXT,
    updated_at           REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS licenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash     TEXT NOT NULL UNIQUE,
    key_hint     TEXT,
    user_id      INTEGER,
    plan         TEXT NOT NULL DEFAULT 'pro',
    status       TEXT NOT NULL DEFAULT 'active',
    issued_at    REAL NOT NULL,
    expires_at   REAL,
    revoked_at   REAL,
    machine_hash TEXT,
    bound_at     REAL,
    seats        INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    source       TEXT NOT NULL DEFAULT 'manual',
    external_ref TEXT
);

CREATE TABLE IF NOT EXISTS entitlements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    license_hash TEXT,
    plan         TEXT NOT NULL DEFAULT 'pro',
    machine_hash TEXT,
    issued_at    REAL NOT NULL,
    expires_at   REAL,
    verified_at  REAL,
    grace_until  REAL,
    source       TEXT NOT NULL DEFAULT 'local',
    payload      TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     REAL NOT NULL,
    actor  TEXT NOT NULL DEFAULT 'system',
    action TEXT NOT NULL,
    target TEXT,
    detail TEXT,
    ip     TEXT
);

CREATE TABLE IF NOT EXISTS usage_counters (
    day  TEXT NOT NULL,
    kind TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, kind)
);

CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    kind     TEXT,
    received_at REAL NOT NULL,
    result   TEXT
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_licenses_user ON licenses(user_id);
CREATE INDEX IF NOT EXISTS idx_entitlements_user ON entitlements(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);
"""


# ─── helpers ───────────────────────────────────────────────────────────────
def now_ts():
    """Current UTC time as epoch seconds."""
    return time.time()


def iso(ts):
    """Epoch seconds -> ISO-8601 UTC string (None passes through)."""
    if ts in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def parse_iso(value):
    """ISO-8601 string (or epoch) -> epoch seconds (None passes through)."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def db_path():
    """Resolve the accounts DB path at call time (env may change in tests)."""
    override = os.environ.get("STOCKER_ACCOUNTS_DB")
    return Path(override) if override else DB_PATH


def connect():
    """Open a short-lived connection. Per-call connections keep threads safe."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=8000")
    except Exception:
        pass
    return conn


def init_db():
    """Create the schema if missing. Safe to call repeatedly."""
    try:
        with connect() as conn:
            conn.executescript(SCHEMA)
        return True
    except Exception as e:
        logger.error(f"[Accounts] failed to init db at {db_path()}: {e}")
        return False


def _rows(cursor):
    try:
        return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []


# ─── passwords ─────────────────────────────────────────────────────────────
def hash_password(password, salt=None):
    """PBKDF2-HMAC-SHA256 password hash. Returns (hash_hex, salt_hex)."""
    if password is None:
        password = ""
    salt_hex = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", str(password).encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    )
    return digest.hex(), salt_hex


def verify_password(password, password_hash, salt_hex):
    """Constant-time password check. Never raises."""
    try:
        if not password_hash or not salt_hex:
            return False
        candidate, _ = hash_password(password or "", salt_hex)
        return hmac.compare_digest(candidate, password_hash)
    except Exception:
        return False


# ─── users ─────────────────────────────────────────────────────────────────
def create_user(email, password=None, username=None, role="user", plan=FREE_PLAN):
    """Create a user. Returns the user dict or None when the email exists."""
    email = str(email or "").strip().lower()
    if not email or "@" not in email:
        return None
    plan = plan if plan in VALID_PLANS else FREE_PLAN
    now = now_ts()
    pw_hash = pw_salt = None
    if password:
        pw_hash, pw_salt = hash_password(password)
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users (email, username, password_hash, password_salt, role, plan, status, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (email, username, pw_hash, pw_salt, role, plan, "active", now),
            )
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        logger.error(f"[Accounts] create_user failed: {e}")
        return None
    return get_user_by_email(email)


def get_user(user_id):
    if user_id in (None, ""):
        return None
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def get_user_by_email(email):
    email = str(email or "").strip().lower()
    if not email:
        return None
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def list_users(limit=200):
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM users ORDER BY id DESC LIMIT ?", (int(limit),))
            return _rows(cur)
    except Exception:
        return []


def set_password(user_id, password):
    try:
        pw_hash, pw_salt = hash_password(password)
        with connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
                (pw_hash, pw_salt, user_id),
            )
        return True
    except Exception:
        return False


def touch_login(user_id):
    try:
        with connect() as conn:
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_ts(), user_id))
    except Exception:
        pass


def set_user_role(user_id, role):
    try:
        with connect() as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        return True
    except Exception:
        return False


# ─── subscriptions ─────────────────────────────────────────────────────────
def create_subscription(user_id, plan=PRO_PLAN, months=1, expires_at=None, status="active",
                       source="manual", external_ref=None):
    """Create (or replace) the subscription of a user. Returns the row dict."""
    plan = plan if plan in VALID_PLANS else PRO_PLAN
    now = now_ts()
    if plan == FREE_PLAN:
        expires_at = None  # the free tier never expires
    elif expires_at is None:
        expires_at = now + (float(months or 1) * 30.0 * 86400.0)
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO subscriptions (user_id, plan, status, started_at, expires_at,"
                " cancel_at_period_end, source, external_ref, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (user_id, plan, status, now, expires_at, 0, source, external_ref, now),
            )
            sub_id = cur.lastrowid
            if user_id:
                # Keep the user row in sync - never downgrade an active pro user.
                conn.execute(
                    "UPDATE users SET plan = ? WHERE id = ? AND (plan <> 'pro' OR ? = 'pro')",
                    (plan, user_id, plan),
                )
    except Exception as e:
        logger.error(f"[Accounts] create_subscription failed: {e}")
        return None
    return get_subscription_by_id(sub_id)


def get_subscription_by_id(sub_id):
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def get_subscription(user_id):
    """Most recent subscription for a user."""
    if user_id in (None, ""):
        return None
    try:
        with connect() as conn:
            cur = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def list_subscriptions(limit=200):
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM subscriptions ORDER BY id DESC LIMIT ?", (int(limit),))
            return _rows(cur)
    except Exception:
        return []


def update_subscription(sub_id, **fields):
    allowed = {"plan", "status", "expires_at", "cancel_at_period_end", "source", "external_ref"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return get_subscription_by_id(sub_id)
    sets["updated_at"] = now_ts()
    clause = ", ".join(f"{k} = ?" for k in sets)
    try:
        with connect() as conn:
            conn.execute(f"UPDATE subscriptions SET {clause} WHERE id = ?", (*sets.values(), sub_id))
    except Exception:
        return None
    return get_subscription_by_id(sub_id)


def subscription_is_active(sub, at=None):
    """True when a subscription row grants access right now."""
    if not sub:
        return False
    if str(sub.get("status") or "").lower() not in ("active", "trialing", "past_due"):
        return False
    exp = sub.get("expires_at")
    if exp in (None, ""):
        return True
    try:
        return float(exp) > float(at if at is not None else now_ts())
    except Exception:
        return True


# ─── licenses ──────────────────────────────────────────────────────────────
def upsert_license(key_hash, key_hint, user_id, plan=PRO_PLAN, expires_at=None, seats=1,
                   notes="", source="manual", external_ref=None, status="active"):
    """Insert or refresh a license row keyed by the key hash."""
    now = now_ts()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO licenses (key_hash, key_hint, user_id, plan, status, issued_at,"
                " expires_at, seats, notes, source, external_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(key_hash) DO UPDATE SET key_hint=excluded.key_hint, user_id=excluded.user_id,"
                " plan=excluded.plan, expires_at=excluded.expires_at, seats=excluded.seats,"
                " notes=excluded.notes, source=excluded.source, external_ref=excluded.external_ref,"
                " status=excluded.status",
                (key_hash, key_hint, user_id, plan, status, now, expires_at, seats, notes, source, external_ref),
            )
    except Exception as e:
        logger.error(f"[Accounts] upsert_license failed: {e}")
        return None
    return get_license_by_hash(key_hash)


def get_license_by_hash(key_hash):
    if not key_hash:
        return None
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM licenses WHERE key_hash = ?", (key_hash,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def get_license_for_user(user_id):
    if user_id in (None, ""):
        return None
    try:
        with connect() as conn:
            cur = conn.execute(
                "SELECT * FROM licenses WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def list_licenses(limit=200):
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM licenses ORDER BY id DESC LIMIT ?", (int(limit),))
            return _rows(cur)
    except Exception:
        return []


def license_is_active(lic, at=None):
    if not lic:
        return False
    if str(lic.get("status") or "").lower() != "active":
        return False
    if lic.get("revoked_at"):
        return False
    exp = lic.get("expires_at")
    if exp in (None, ""):
        return True
    try:
        return float(exp) > float(at if at is not None else now_ts())
    except Exception:
        return True


def revoke_license(key_hash):
    """Mark a license revoked. Returns the updated row or None."""
    lic = get_license_by_hash(key_hash)
    if not lic:
        return None
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE licenses SET status='revoked', revoked_at=? WHERE key_hash=?",
                (now_ts(), key_hash),
            )
    except Exception as e:
        logger.error(f"[Accounts] revoke_license failed: {e}")
        return None
    return get_license_by_hash(key_hash)


def revoke_license_and_subscription(key_hash):
    """Revoke a license and cancel the subscription that backed it.

    A revoke is the operator's "off" switch: without cancelling the
    subscription a signed-in user would keep Pro through the subscription.
    """
    lic = get_license_by_hash(key_hash)
    if not lic:
        return None
    revoke_license(key_hash)
    user_id = lic.get("user_id")
    if user_id:
        sub = get_subscription(user_id)
        if sub:
            update_subscription(sub["id"], status="cancelled")
    return get_license_by_hash(key_hash)


def extend_license(key_hash, months=1):
    """Extend a license (and its subscription) by N months. None when unknown."""
    lic = get_license_by_hash(key_hash)
    if not lic:
        return None
    now = now_ts()
    base = lic.get("expires_at")
    try:
        base = float(base) if base else now
    except Exception:
        base = now
    if base < now:
        base = now
    new_exp = base + (float(months or 1) * 30.0 * 86400.0)
    try:
        with connect() as conn:
            conn.execute("UPDATE licenses SET expires_at=? WHERE key_hash=?", (new_exp, key_hash))
            if lic.get("user_id"):
                conn.execute(
                    "UPDATE subscriptions SET expires_at=?, status='active', updated_at=?"
                    " WHERE user_id=? AND id=(SELECT id FROM subscriptions WHERE user_id=? ORDER BY id DESC LIMIT 1)",
                    (new_exp, now, lic.get("user_id"), lic.get("user_id")),
                )
    except Exception as e:
        logger.error(f"[Accounts] extend_license failed: {e}")
        return None
    return get_license_by_hash(key_hash)


def bind_license(key_hash, machine_hash):
    """Bind a license to a machine fingerprint."""
    lic = get_license_by_hash(key_hash)
    if not lic:
        return None
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE licenses SET machine_hash=?, bound_at=? WHERE key_hash=?",
                (machine_hash, now_ts(), key_hash),
            )
    except Exception as e:
        logger.error(f"[Accounts] bind_license failed: {e}")
        return None
    return get_license_by_hash(key_hash)


# ─── entitlements ──────────────────────────────────────────────────────────
def record_entitlement(user_id, plan, machine_hash, expires_at=None, verified_at=None,
                       grace_until=None, source="local", payload=None, license_hash=None):
    now = now_ts()
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO entitlements (user_id, license_hash, plan, machine_hash, issued_at,"
                " expires_at, verified_at, grace_until, source, payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (user_id, license_hash, plan, machine_hash, now, expires_at,
                 verified_at if verified_at is not None else now, grace_until, source, payload),
            )
            ent_id = cur.lastrowid
    except Exception as e:
        logger.error(f"[Accounts] record_entitlement failed: {e}")
        return None
    return get_entitlement_by_id(ent_id)


def get_entitlement_by_id(ent_id):
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM entitlements WHERE id = ?", (ent_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def latest_entitlement(machine_hash=None):
    """Most recent entitlement, optionally filtered by machine fingerprint."""
    try:
        with connect() as conn:
            if machine_hash:
                cur = conn.execute(
                    "SELECT * FROM entitlements WHERE machine_hash = ? ORDER BY id DESC LIMIT 1",
                    (machine_hash,),
                )
            else:
                cur = conn.execute("SELECT * FROM entitlements ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


# ─── audit log ─────────────────────────────────────────────────────────────
def audit(action, actor="system", target="", detail="", ip=""):
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, actor, action, target, detail, ip) VALUES (?,?,?,?,?,?)",
                (now_ts(), str(actor or "system"), str(action), str(target or ""), str(detail or ""), str(ip or "")),
            )
    except Exception as e:
        logger.error(f"[Accounts] audit failed: {e}")


def list_audit(limit=200):
    try:
        with connect() as conn:
            cur = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (int(limit),))
            return _rows(cur)
    except Exception:
        return []


# ─── usage counters (free tier export quota) ──────────────────────────────
def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def usage_increment(kind, day=None):
    """Bump a daily counter and return the new value."""
    day = day or _today()
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO usage_counters (day, kind, count) VALUES (?,?,1)"
                " ON CONFLICT(day, kind) DO UPDATE SET count = count + 1",
                (day, kind),
            )
            cur = conn.execute("SELECT count FROM usage_counters WHERE day=? AND kind=?", (day, kind))
            row = cur.fetchone()
            return int(row["count"]) if row else 1
    except Exception:
        return 0


def usage_count(kind, day=None):
    day = day or _today()
    try:
        with connect() as conn:
            cur = conn.execute("SELECT count FROM usage_counters WHERE day=? AND kind=?", (day, kind))
            row = cur.fetchone()
            return int(row["count"]) if row else 0
    except Exception:
        return 0


# ─── webhook idempotency ───────────────────────────────────────────────────
def mark_event(event_id, kind="", result=""):
    """Record an event id. Returns True when it is new (first delivery)."""
    if not event_id:
        return True
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO processed_events (event_id, kind, received_at, result)"
                " VALUES (?,?,?,?)",
                (str(event_id), str(kind), now_ts(), str(result)),
            )
            return bool(cur.rowcount)
    except Exception as e:
        logger.error(f"[Accounts] mark_event failed: {e}")
        return True


def event_seen(event_id):
    if not event_id:
        return False
    try:
        with connect() as conn:
            cur = conn.execute("SELECT event_id FROM processed_events WHERE event_id = ?", (str(event_id),))
            return cur.fetchone() is not None
    except Exception:
        return False
