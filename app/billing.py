"""Billing providers for StockerAI.

Pluggable so the same code serves three deployment shapes:

    MANUAL   the operator issues keys by hand (CLI or /admin area). Default.
    WEBHOOK  a checkout platform posts signed subscription events to
             /api/billing/webhook. Signature is verified and every event is
             applied exactly once (idempotent).
    NONE     no billing configured - the terminal stays on the free tier and
             never crashes.

Only stdlib is used (hmac + hashlib for signatures, urllib for outbound
calls). No payment SDK is required: the provider interface is the seam.
"""
import hashlib
import hmac
import json
import logging
import os
import time

try:
    from . import accounts
except ImportError:  # flat import when app/ is on sys.path
    import accounts

try:
    from . import licensing
except ImportError:  # flat import when app/ is on sys.path
    import licensing

logger = logging.getLogger(__name__)

FREE_PLAN = licensing.FREE_PLAN
PRO_PLAN = licensing.PRO_PLAN

WEBHOOK_SIGNATURE_HEADER = "X-Stocker-Signature"
WEBHOOK_TIMESTAMP_HEADER = "X-Stocker-Timestamp"
WEBHOOK_TOLERANCE_SECONDS = 300

EVENT_ACTIVATED = "subscription.activated"
EVENT_RENEWED = "subscription.renewed"
EVENT_CANCELLED = "subscription.cancelled"

_EVENT_ALIASES = {
    "subscription.activated": EVENT_ACTIVATED,
    "subscription_activated": EVENT_ACTIVATED,
    "subscription.created": EVENT_ACTIVATED,
    "subscription_created": EVENT_ACTIVATED,
    "order.completed": EVENT_ACTIVATED,
    "subscription.renewed": EVENT_RENEWED,
    "subscription_renewed": EVENT_RENEWED,
    "subscription.updated": EVENT_RENEWED,
    "subscription.cancelled": EVENT_CANCELLED,
    "subscription_cancelled": EVENT_CANCELLED,
    "subscription.canceled": EVENT_CANCELLED,
    "customer.subscription.deleted": EVENT_CANCELLED,
}


class BillingError(Exception):
    """Raised when a billing operation cannot be completed."""


class BillingProvider:
    """Base provider - the shared local issue/revoke/extend behaviour."""

    name = "base"
    supports_webhook = False

    def __init__(self):
        accounts.init_db()

    # -- plans -------------------------------------------------------------
    @staticmethod
    def _months_to_expiry(months, lifetime=False):
        if lifetime:
            return None
        return time.time() + (float(months or 1) * 30.0 * 86400.0)

    # -- issuance ----------------------------------------------------------
    def issue_license(self, email, plan=PRO_PLAN, months=12, seats=1, notes="", user_id=None,
                      lifetime=False, source=None, external_ref=None):
        """Create the subscription + license and return the plaintext key."""
        plan = plan if plan in licensing.PLANS else PRO_PLAN
        email = str(email or "").strip().lower()
        if not email or "@" not in email:
            raise BillingError("a valid email is required")
        user = accounts.get_user(user_id) if user_id else accounts.get_user_by_email(email)
        if not user:
            user = accounts.create_user(email, None, username=email.split("@")[0])
        if not user:
            raise BillingError(f"could not create the account for {email}")
        expires_at = self._months_to_expiry(months, lifetime)
        accounts.create_subscription(
            user["id"], plan, months=months, expires_at=expires_at,
            status="active", source=source or self.name, external_ref=external_ref,
        )
        key = licensing.generate_license_key()
        accounts.upsert_license(
            licensing.key_hash(key), licensing.key_hint(key), user["id"], plan,
            expires_at=expires_at, seats=seats, notes=notes,
            source=source or self.name, external_ref=external_ref,
        )
        accounts.audit("license.issued", actor=self.name, target=email,
                       detail=f"plan={plan} expires={licensing._iso(expires_at) or 'never'}")
        return {
            "key": key,
            "key_hint": licensing.key_hint(key),
            "plan": plan,
            "email": email,
            "user_id": user["id"],
            "expires_at": licensing._iso(expires_at),
            "lifetime": bool(lifetime),
            "provider": self.name,
        }

    def revoke_license(self, key):
        normalized = licensing.normalize_key(key)
        if not normalized:
            raise BillingError("invalid license key")
        lic = accounts.get_license_by_hash(licensing.key_hash(normalized))
        if not lic:
            raise BillingError("license not found")
        accounts.revoke_license_and_subscription(lic["key_hash"])
        accounts.audit("license.revoked", actor=self.name, target=lic.get("key_hint"), detail="revoked")
        licensing.clear_entitlement()
        return {"ok": True, "key_hint": lic.get("key_hint")}

    def extend_license(self, key, months=12):
        normalized = licensing.normalize_key(key)
        if not normalized:
            raise BillingError("invalid license key")
        lic = accounts.get_license_by_hash(licensing.key_hash(normalized))
        if not lic:
            raise BillingError("license not found")
        updated = accounts.extend_license(lic["key_hash"], months)
        accounts.audit("license.extended", actor=self.name, target=lic.get("key_hint"),
                       detail=f"months={months}")
        return {"ok": True, "expires_at": licensing._iso(updated.get("expires_at"))}

    def bind_license(self, key, machine_hash):
        normalized = licensing.normalize_key(key)
        if not normalized:
            raise BillingError("invalid license key")
        lic = accounts.get_license_by_hash(licensing.key_hash(normalized))
        if not lic:
            raise BillingError("license not found")
        accounts.bind_license(lic["key_hash"], machine_hash)
        accounts.audit("license.bound", actor=self.name, target=lic.get("key_hint"),
                       detail=f"machine={str(machine_hash)[:12]}")
        return {"ok": True, "machine_hash": machine_hash}

    # -- checkout ----------------------------------------------------------
    def create_checkout(self, plan=PRO_PLAN, email="", return_url=""):
        """Where the buyer goes to pay. Manual providers point at /billing."""
        plan = plan if plan in licensing.PLANS else PRO_PLAN
        return {
            "provider": self.name,
            "plan": plan,
            "url": "/billing",
            "manual": True,
            "message": "Contact the operator for a license key, or paste the key you received.",
        }

    # -- webhook -----------------------------------------------------------
    def verify_webhook(self, body, headers):
        return {"ok": False, "error": "webhook_not_supported",
                "message": f"The {self.name} provider does not accept webhooks."}

    def handle_event(self, event):
        raise BillingError("webhook_not_supported")

    def cancel_subscription(self, email):
        user = accounts.get_user_by_email(email)
        if not user:
            raise BillingError(f"no account for {email}")
        sub = accounts.get_subscription(user["id"])
        if not sub:
            raise BillingError(f"no subscription for {email}")
        accounts.update_subscription(sub["id"], status="cancelled")
        lic = accounts.get_license_for_user(user["id"])
        if lic:
            accounts.revoke_license_and_subscription(lic["key_hash"])
        accounts.audit("subscription.cancelled", actor=self.name, target=email, detail="cancelled")
        return {"ok": True, "email": email}


class ManualProvider(BillingProvider):
    """The operator issues keys by hand (CLI or /admin area)."""

    name = "manual"
    supports_webhook = False


class WebhookProvider(BillingProvider):
    """A checkout platform posts signed subscription events to us."""

    name = "webhook"
    supports_webhook = True

    def secret(self):
        env = os.environ.get("BILLING_WEBHOOK_SECRET") or os.environ.get("STOCKER_WEBHOOK_SECRET")
        if env and env.strip():
            return env.strip()
        return licensing.license_secret()

    def tolerance(self):
        try:
            return max(0, int(os.environ.get("STOCKER_WEBHOOK_TOLERANCE", str(WEBHOOK_TOLERANCE_SECONDS))))
        except Exception:
            return WEBHOOK_TOLERANCE_SECONDS

    def create_checkout(self, plan=PRO_PLAN, email="", return_url=""):
        plan = plan if plan in licensing.PLANS else PRO_PLAN
        base = os.environ.get("STOCKER_CHECKOUT_URL", "").strip()
        if base:
            sep = "&" if "?" in base else "?"
            url = f"{base}{sep}plan={plan}"
            if email:
                url += f"&email={email}"
            return {"provider": self.name, "plan": plan, "url": url, "manual": False,
                    "message": "Continue to checkout."}
        return {"provider": self.name, "plan": plan, "url": "/billing", "manual": True,
                "message": "Set STOCKER_CHECKOUT_URL to enable hosted checkout."}

    # -- signature ---------------------------------------------------------
    def sign(self, body, timestamp):
        """Helper used by the CLI/tests to produce a valid signature."""
        if isinstance(body, str):
            body = body.encode("utf-8")
        message = f"{timestamp}.".encode("utf-8") + body
        digest = hmac.new(self.secret().encode("utf-8"), message, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def verify_webhook(self, body, headers):
        """Verify the signature and the replay window of an incoming event."""
        if isinstance(body, str):
            body = body.encode("utf-8")
        headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        signature = headers.get(WEBHOOK_SIGNATURE_HEADER.lower(), "")
        timestamp = headers.get(WEBHOOK_TIMESTAMP_HEADER.lower(), "")
        if not signature or not timestamp:
            return {"ok": False, "error": "missing_signature",
                    "message": f"Both {WEBHOOK_SIGNATURE_HEADER} and {WEBHOOK_TIMESTAMP_HEADER} are required."}
        try:
            ts = int(float(timestamp))
        except Exception:
            return {"ok": False, "error": "bad_timestamp", "message": "The timestamp header is not a number."}
        tolerance = self.tolerance()
        if tolerance and abs(time.time() - ts) > tolerance:
            return {"ok": False, "error": "stale_timestamp",
                    "message": "The webhook timestamp is outside the accepted replay window."}
        expected = self.sign(body, timestamp)
        if not hmac.compare_digest(expected, str(signature).strip()):
            return {"ok": False, "error": "invalid_signature",
                    "message": "The webhook signature does not match."}
        try:
            event = json.loads(body.decode("utf-8"))
        except Exception as e:
            return {"ok": False, "error": "invalid_json", "message": f"Body is not valid JSON: {e}"}
        if not isinstance(event, dict):
            return {"ok": False, "error": "invalid_json", "message": "Body must be a JSON object."}
        return {"ok": True, "event": event}

    # -- events ------------------------------------------------------------
    def handle_event(self, event):
        """Apply a subscription event exactly once."""
        if not isinstance(event, dict):
            return {"ok": False, "error": "invalid_event", "message": "Event must be an object."}
        raw_type = str(event.get("type") or event.get("event") or "").strip().lower()
        event_type = _EVENT_ALIASES.get(raw_type)
        if not event_type:
            return {"ok": False, "error": "unknown_event",
                    "message": f"Unsupported event type: {raw_type or '(missing)'}."}
        data = event.get("data") if isinstance(event.get("data"), dict) else event
        event_id = str(event.get("id") or event.get("event_id") or data.get("id") or "").strip()
        if not event_id:
            return {"ok": False, "error": "missing_event_id",
                    "message": "An event id is required for idempotency."}
        if accounts.event_seen(event_id):
            return {"ok": True, "duplicate": True, "event_id": event_id, "type": event_type,
                    "message": "Event already processed - nothing to do."}

        email = str(data.get("email") or data.get("customer_email") or "").strip().lower()
        plan = str(data.get("plan") or PRO_PLAN).strip().lower()
        if plan not in licensing.PLANS:
            plan = PRO_PLAN
        try:
            months = float(data.get("months") or data.get("term_months") or 12)
        except Exception:
            months = 12
        seats = int(data.get("seats") or 1)
        lifetime = bool(data.get("lifetime"))
        external_ref = data.get("external_ref") or data.get("order_id")

        if event_type == EVENT_ACTIVATED:
            issued = self.issue_license(email, plan=plan, months=months, seats=seats,
                                        notes="issued by webhook", lifetime=lifetime,
                                        source="webhook", external_ref=external_ref)
            accounts.mark_event(event_id, event_type, json.dumps({"key_hint": issued["key_hint"]}))
            return {"ok": True, "duplicate": False, "event_id": event_id, "type": event_type,
                    "plan": plan, "email": email, "license_key": issued["key"],
                    "expires_at": issued["expires_at"]}

        if event_type == EVENT_RENEWED:
            user = accounts.get_user_by_email(email)
            if not user:
                return {"ok": False, "error": "unknown_customer",
                        "message": f"No account for {email}."}
            sub = accounts.get_subscription(user["id"])
            expires_at = time.time() + (months * 30.0 * 86400.0)
            if sub:
                accounts.update_subscription(sub["id"], status="active", expires_at=expires_at,
                                             external_ref=external_ref)
            else:
                accounts.create_subscription(user["id"], plan, months=months, expires_at=expires_at,
                                             source="webhook", external_ref=external_ref)
            lic = accounts.get_license_for_user(user["id"])
            if lic:
                accounts.extend_license(lic["key_hash"], months)
            accounts.audit("subscription.renewed", actor=self.name, target=email, detail=f"months={months}")
            accounts.mark_event(event_id, event_type, "renewed")
            return {"ok": True, "duplicate": False, "event_id": event_id, "type": event_type,
                    "email": email, "expires_at": licensing._iso(expires_at)}

        # cancelled
        try:
            self.cancel_subscription(email)
        except BillingError as e:
            return {"ok": False, "error": "unknown_customer", "message": str(e)}
        accounts.mark_event(event_id, event_type, "cancelled")
        return {"ok": True, "duplicate": False, "event_id": event_id, "type": event_type, "email": email}


class NullProvider(BillingProvider):
    """No billing configured - free tier only, never an error page."""

    name = "none"
    supports_webhook = False

    def issue_license(self, email, plan=PRO_PLAN, months=12, seats=1, notes="", user_id=None,
                      lifetime=False, source=None, external_ref=None):
        raise BillingError("No billing provider is configured on this machine.")

    def create_checkout(self, plan=PRO_PLAN, email="", return_url=""):
        return {"provider": self.name, "plan": plan, "url": "/pricing", "manual": True,
                "message": "This installation has no billing provider configured."}


def get_provider(name=None):
    """Resolve the configured provider (MANUAL by default)."""
    name = (name or os.environ.get("BILLING_PROVIDER", "") or "").strip().lower()
    if name in ("webhook", "webhooks"):
        return WebhookProvider()
    if name in ("none", "null", "off", "disabled"):
        return NullProvider()
    if name in ("manual", "admin", ""):
        return ManualProvider()
    logger.info(f"[Billing] unknown provider '{name}' - falling back to manual")
    return ManualProvider()


def provider_status():
    """Small status blob for /api/account/me and the admin console."""
    provider = get_provider()
    return {
        "provider": provider.name,
        "supports_webhook": bool(provider.supports_webhook),
        "checkout_url": provider.create_checkout().get("url"),
        "admin_enabled": bool(os.environ.get("ADMIN_TOKEN", "").strip()),
        "webhook_configured": bool(
            (os.environ.get("BILLING_WEBHOOK_SECRET") or os.environ.get("STOCKER_WEBHOOK_SECRET") or "").strip()
        ),
    }
