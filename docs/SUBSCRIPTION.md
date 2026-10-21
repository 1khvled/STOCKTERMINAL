# StockerAI Subscriptions - Plans, Licensing and Operator Runbook

StockerAI is **desktop software**: the buyer runs it on their own machine, their
data never leaves it, and they bring their own LLM key. The subscription is
enforced the way real desktop software enforces it - a license key, bound to
the machine, verified against an entitlement source, with a signed local
entitlement file so the buyer is never locked out when offline.

```
checkout  ->  license key  ->  /activate  ->  machine bound  ->  Pro surfaces open
                                            \
                                             -> signed entitlement file (offline, 14d grace)
```

---

## 1. Plans

| | **StockerAI Free** | **StockerAI Pro** |
|---|---|---|
| Price | $0 forever | $49/mo, $399/yr, $999 lifetime |
| Analysis pipeline (DCF, WACC, Monte Carlo, Altman Z, Piotroski, Beneish, DuPont) | yes | yes |
| Dashboard, watchlist, portfolio, compare + AI judge | yes | yes |
| News impact, SEC filings, macro regime | yes | yes |
| Screener (21 filters + natural language) | yes | yes |
| Model exports (Excel + JSON) | 10 / day | unlimited |
| **Scenario Lab** (bull / base / bear + Monte Carlo fan) | - | yes |
| **Investment Committee** (multi-agent buy-side debate) | - | yes |
| **Red Flags** (forensic scan: Beneish / Altman / DuPont) | - | yes |
| **Headless terminal API** (`POST /api/terminal/execute`) | - | yes |
| **Batch screening** (`POST /api/batch/screen`) | - | yes |

### Why this split

The buyer pays for *their own* LLM inference (their `.env` key), so an analysis
run costs the operator nothing. Gating the analysis loop would only cripple the
marketing. What the operator actually sells is the **analyst-grade surface
area**: the multi-model surfaces that turn a stock screener into a desk.

So the free tier keeps everything a retail investor touches (run a ticker, read
the dashboard, screen, compare, track a portfolio) and Pro gates the four
surfaces that are only useful in a professional workflow: scenario modelling,
the investment committee, forensic red flags and the headless API for
automation. Exports are capped on free because each Excel model is a
"take the work home with you" moment - the classic desktop-software upsell.

### What a gated surface does

* **Pages** (`/scenario-lab`, `/committee`, `/red-flags`) render the
  **upgrade prompt** (HTTP 200). The buyer always sees what they would get.
* **APIs** answer **HTTP 402 Payment Required** with a machine readable body:

```json
{
  "error": "upgrade_required",
  "message": "Scenario Lab is a Pro feature. Activate a Pro license key to unlock it.",
  "feature": "scenario_lab",
  "feature_label": "Scenario Lab",
  "required_plan": "pro",
  "upgrade_url": "/pricing",
  "activate_url": "/activate",
  "unlocks": ["Scenario Lab - bull / base / bear cases with Monte Carlo fan", "..."],
  "price_month": 49,
  "price_year": 399
}
```

* **Exception - the headless terminal API** answers **HTTP 200** with the same
  envelope (`error: "upgrade_required"`). The terminal API's contract is a
  JSON envelope consumed by scripts; a bare 403 would break existing clients
  and the existing test suite. The command simply does not execute and the
  body says exactly what to do.

---

## 2. Architecture

| File | Purpose |
|---|---|
| `app/licensing.py` | Key generation/validation, machine binding, HMAC signing of entitlement payloads, offline entitlement file, grace period, plan checks, `@requires_plan`, and the operator CLI (`python -m app.licensing`). |
| `app/accounts.py` | `sqlite3` (stdlib) store in `output/accounts.db`: `users`, `subscriptions`, `licenses`, `entitlements`, `audit_log` (+ `usage_counters`, `processed_events`). |
| `app/billing.py` | Pluggable provider interface: `ManualProvider` (operator issues keys), `WebhookProvider` (signed checkout events), `NullProvider` (free only). |
| `app/account_bp.py` | Flask blueprint: `/signup`, `/login`, `/logout`, `/account`, `/billing`, `/activate`, `/pricing`, `/api/account/me`, `/api/billing/webhook`, `/api/entitlement/verify`, `/admin/*`. |
| `app/server.py` | Registers the blueprint and wires the gates (`licensing.plan_guard`) into the existing routes. No existing route was removed. |
| `app/templates/{auth,account,billing,activate,pricing,upgrade,admin}.html` | The new pages, in the existing dark terminal style. |

### Data model (`output/accounts.db`)

* **users** - email, pbkdf2-hmac-sha256 password hash + salt, role, plan.
* **subscriptions** - plan, status, started/expires, source (`manual`,
  `webhook`, `signup`, `seed`), external_ref. `expires_at = NULL` = perpetual.
* **licenses** - the license **hash** (never the plaintext), last-4 hint, plan,
  expiry, revocation, `machine_hash` binding, seats, notes, source.
* **entitlements** - entitlement snapshots cached for a machine.
* **audit_log** - every issue / activate / extend / revoke / webhook, with actor.
* **usage_counters** - daily export counters (free tier quota).
* **processed_events** - webhook idempotency ledger (`event_id` unique).

`output/` is gitignored, so the database never lands in the repo.

### Machine binding

`machine_fingerprint()` = `sha256("stocker-machine-v1|" + machine_id)` where
`machine_id` is, in order:

1. `STOCKER_MACHINE_ID` (override, used by tests and by users whose machine id
   is not stable),
2. the Windows `MachineGuid` (registry),
3. `/etc/machine-id` (Linux),
4. `platform.node() + uuid.getnode()`.

The fingerprint is shown to the buyer on `/account` so the operator can pin a
license to a specific machine with `python -m app.licensing bind`.

### Entitlement file (the offline path)

`output/.entitlement.json` (override: `STOCKER_ENTITLEMENT_FILE`):

```json
{
  "payload": {
    "v": 1, "plan": "pro", "license_key": "STK-...-ABCD", "key_hint": "ABCD",
    "email": "buyer@example.com", "seats": 1,
    "issued_at": "2026-10-21T12:00:00+00:00",
    "expires_at": "2027-10-21T12:00:00+00:00",
    "machine_hash": "<64 hex>",
    "source": "manual",
    "verified_at": "2026-10-21T12:00:00+00:00",
    "grace_until": "2026-11-04T12:00:00+00:00"
  },
  "signature": "<hmac-sha256 hex over the canonical payload>"
}
```

* Signature = `HMAC-SHA256(secret, canonical_json(payload))`, verified with
  `hmac.compare_digest`.
* The payload is bound to the machine fingerprint.
* `grace_until = verified_at + 14 days` (`STOCKER_GRACE_DAYS`).
* A tampered file is rejected (`status: invalid`) and falls back to free tier.

### How a key gets activated (3 paths, in order)

1. **Self-signed offline key** - `STK1.<payload>.<signature>`. Verified
   locally with the shared secret; works with no network and no control plane.
2. **Local database** - the key hash is in `output/accounts.db` (the app is
   running on the same machine as the operator, i.e. a self-hosted install).
   The license is bound to this machine on first activation.
3. **Remote entitlement service** - `STOCKER_ENTITLEMENT_URL` points at a
   control-plane instance of this app. The app posts
   `{key, machine_hash, email}` to `/api/entitlement/verify` and gets a signed
   entitlement back, which it verifies locally before caching it.

If the control plane is unreachable the app falls back to the signed local
file + grace period. **The buyer is never locked out.**

---

## 3. Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `STOCKER_LICENSE_SECRET` | auto-generated into `output/.license_secret` | HMAC secret used to sign entitlement payloads and self-signed keys. **Set the same value on the control plane and on the desktop installs** so offline entitlements verify. |
| `ADMIN_TOKEN` | *(unset)* | Enables the `/admin/*` console. Unset = the admin area is disabled (403 `admin_disabled`). |
| `BILLING_PROVIDER` | `manual` | `manual` (operator issues keys), `webhook` (checkout platform posts events), `none` (free tier only). |
| `BILLING_WEBHOOK_SECRET` | falls back to `STOCKER_LICENSE_SECRET` | Shared secret for the webhook signature (`X-Stocker-Signature`). |
| `STOCKER_WEBHOOK_TOLERANCE` | `300` | Replay window in seconds for webhook timestamps. `0` disables it. |
| `STOCKER_ENTITLEMENT_URL` | *(unset)* | Base URL of the control plane used by desktop installs to validate keys. |
| `STOCKER_ENTITLEMENT_API_TOKEN` | *(unset)* | Optional token required on `/api/entitlement/verify` (`X-Entitlement-Token`). |
| `STOCKER_ENTITLEMENT_FILE` | `output/.entitlement.json` | Where the signed offline entitlement is cached. |
| `STOCKER_ACCOUNTS_DB` | `output/accounts.db` | Accounts database path. |
| `STOCKER_GRACE_DAYS` | `14` | Offline grace period. |
| `STOCKER_MACHINE_ID` | *(auto)* | Override the machine id (tests / unstable machine ids). |
| `STOCKER_CHECKOUT_URL` | *(unset)* | Hosted checkout URL used by the `/billing` page. |

Nothing above is required: **with zero configuration the app runs on the free
tier**, never crashes and never shows a traceback.

---

## 4. Operator runbook (10 lines)

1. **Sell**: the buyer checks out and receives a license key by email.
2. **Self-hosted (MANUAL)**: run `python -m app.licensing issue --email <e> --plan pro --months 12`
   and send the printed key. Add `--signed` for a self-validating offline key.
3. **Hosted checkout (WEBHOOK)**: set `BILLING_PROVIDER=webhook` +
   `BILLING_WEBHOOK_SECRET`, point the platform at `POST /api/billing/webhook`;
   the event creates the subscription and returns the key (`license_key`) -
   send that to the buyer.
4. **Buyer activates** on their machine at `/activate`; the key is bound to
   their machine fingerprint (shown on `/account`).
5. **Buyer is offline**: the signed entitlement file keeps Pro running for 14
   days past the last successful check - nothing to do, but mention it in the
   sales email.
6. **Buyer complains "it says Pro but the Lab is locked"**: ask for the
   machine fingerprint from `/account`, then `python -m app.licensing bind --key
   <key> --machine <fingerprint>` (or re-issue).
7. **Buyer complains "it expired"**: `python -m app.licensing extend --key <key>
   --months 12` (or issue a fresh key and revoke the old one).
8. **Refund / chargeback**: `python -m app.licensing revoke --key <key>` -
   the revoke beats the cached file immediately, the buyer drops to free tier.
9. **"I moved to a new laptop"**: re-bind (`bind`) after the buyer activates
   the same key on the new machine, or extend + re-issue.
10. **Never** ask the buyer for their LLM key, their data or their machine
    admin rights; the license key is the only credential you ever handle.

### CLI reference

```cmd
python -m app.licensing issue  --email b@x.com --plan pro --months 12 [--lifetime] [--seats 2] [--signed]
python -m app.licensing list
python -m app.licensing extend --key STK-... --months 12        (or --email)
python -m app.licensing revoke --key STK-...                    (or --email)
python -m app.licensing bind   --key STK-... --machine <64-hex fingerprint>
python -m app.licensing seed                                    :: demo + free accounts
python -m app.licensing verify                                  :: this machine's entitlement
python -m app.licensing entitlement                             :: signed payload on disk
python -m app.licensing machine                                 :: this machine's fingerprint
```

Seeded demo accounts (`python -m app.licensing seed`):
`demo@stocker.ai / demo1234` (pro) and `free@stocker.ai / free1234` (free).

### Admin console (HTTP)

`/admin` (HTML) plus `/admin/users`, `/admin/audit` (GET) and
`/admin/issue`, `/admin/extend`, `/admin/revoke`, `/admin/bind` (POST).
Send the token as `X-Admin-Token: <ADMIN_TOKEN>`, `?token=` or a `token` form
field. Every action is written to `audit_log`.

---

## 5. Webhook contract (checkout platform -> app)

`POST /api/billing/webhook`

Headers:

```
X-Stocker-Signature: sha256=<hmac-sha256(secret, "<timestamp>." + raw body)>
X-Stocker-Timestamp: <unix seconds>
```

The timestamp must be inside `STOCKER_WEBHOOK_TOLERANCE` (default 300s) and
the signature is compared with `hmac.compare_digest`.

Body:

```json
{
  "id": "evt_123",
  "type": "subscription.activated",
  "data": {"email": "buyer@example.com", "plan": "pro", "months": 12,
           "seats": 1, "external_ref": "order_42"}
}
```

Accepted types: `subscription.activated`, `subscription.renewed`,
`subscription.cancelled` (aliases: `subscription_created`, `order.completed`,
`subscription.updated`, `customer.subscription.deleted`, ...).

Responses:

* `200 {"ok": true, "license_key": "STK-...", "expires_at": "..."}` - the key
  was issued, send it to the buyer.
* `200 {"ok": true, "duplicate": true}` - the event id was already processed
  (**idempotent**, no second key is issued).
* `400 {"error": "invalid_signature" | "stale_timestamp" | "unknown_event" | ...}`.

---

## 6. Security notes and known trade-offs

* Passwords: `hashlib.pbkdf2_hmac("sha256", ..., 200_000)` with a per-user
  salt - no new dependency.
* License keys are stored **hashed** (`sha256(salt || key)`); the plaintext is
  printed once at issue time. The admin console shows only the last 4
  characters. A lost key must be re-issued, not recovered.
* Webhooks: HMAC + timestamp window + an idempotency ledger.
* **Known trade-off (v1)**: the desktop app verifies offline entitlements with
  a *shared* HMAC secret (`STOCKER_LICENSE_SECRET`). A user who extracts that
  secret could forge an entitlement. Mitigation today: the secret lives in the
  app's own config, the entitlement is still bound to a machine fingerprint,
  and the authoritative check happens against the control plane whenever the
  machine is online. **v2 hardening (planned):** sign entitlements with
  Ed25519 and ship only the *public* key in the desktop app - the private key
  never leaves the control plane. The signature helpers
  (`sign_payload` / `verify_payload`) are the single seam to swap.
* `ADMIN_TOKEN` is a bearer token: keep it out of shell history and rotate it
  if it leaks (`/admin` is disabled entirely when it is unset).

---

## 7. Tests

```cmd
venv\Scripts\python.exe -m pytest tests\e2e -q
```

* `tests/e2e/test_subscription.py` - key format, machine binding, issue ->
  activate -> gate opens, expiry, revoke, machine mismatch, offline grace,
  tampered entitlement, webhook signature + idempotency, signup/login, admin
  token, export quota, zero-config behaviour.
* `tests/e2e/test_subscription_flow.py` - the full flow against the running
  test server: signed webhook -> key -> `/activate` -> gate opens -> admin
  revoke -> gate closes.
* `tests/e2e/conftest.py` - the suite gets its own accounts DB
  (`%TEMP%\stocker_e2e_accounts.db`), its own entitlement file and
  deterministic secrets, so the real `output/` tree is never touched.
