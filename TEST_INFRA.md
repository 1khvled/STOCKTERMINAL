# E2E Test Infra: StockerAI Personal Terminal (2026-09-08 rewrite, counts refreshed 2026-10-21)
# Replaces the stale Tier 1-4 plan - documents the 103-test reality.

## Reality (verified 2026-10-21)
- Runner: `pytest` (`pytest.ini`: `testpaths=tests`, `test_*.py`)
- Collection: **103 tests** (`pytest --collect-only -q`)
  - `tests/e2e/test_dummy.py` (3): server up, Playwright chromium body visible, mock SSE `REDIRECT: /dashboard/AAPL`
  - `tests/e2e/test_adversarial.py` (28): Tier-5 malformed tickers, empty/stream/screener/query/portfolio/terminal/rate-limit/missing/404/health/live-quote/peers/research
  - `tests/e2e/test_macro.py` (10): macro snapshot/yields/regime contracts, intel-macro ticker validation, macro page HTML
  - `tests/e2e/test_perf.py` (4): response-time budgets + shape checks for live-quotes/movers/macro
  - `tests/e2e/test_portfolio_crud.py` (6): portfolio add/duplicate/clamp/remove/totals/persistence on synthetic tickers
  - `tests/e2e/test_guards.py` (5): unit regressions, no server needed — Piotroski ΔROA improvement, local_db ticker validation, non-finite number guards, portfolio benchmark spread
  - `tests/e2e/test_compare_judge.py` (5): AI judge endpoint — winner pick, single/invalid rejection, missing-ticker report, six-way ranking
  - `tests/e2e/test_screener_tv.py` (3): TV screener — catalog field projection, filter discrimination, NL query parse
  - `tests/e2e/test_subscription.py` (35): licensing units + contract — key format, machine binding, issue→activate→gate opens, expiry, revoke, machine mismatch, offline grace, tampered entitlement, webhook signature/replay, signup/login, admin token, export quota, zero-config
  - `tests/e2e/test_subscription_flow.py` (4): full flow vs the running server — signed webhook→key→activate→gate opens→admin revoke→gate closes
- No Tier 1-4 feature-matrix files exist - adversarial + smoke + macro + perf + portfolio + unit guards + judge + tv-screener + subscription is the suite.

## Environment
- `tests/e2e/conftest.py`: spawns `venv\Scripts\python.exe -m app.server` on **port 5005** (`STOCKER_PORT`), `STOCKER_TEST_MODE=1`, waits 30x0.5s on `/`. Prod runs 5001 - never collide.
- Licensing isolation (set by conftest before the server starts): `STOCKER_ACCOUNTS_DB=%TEMP%\stocker_e2e_accounts.db`, `STOCKER_ENTITLEMENT_FILE=%TEMP%\stocker_e2e_entitlement.json`, `STOCKER_LICENSE_SECRET`, `BILLING_WEBHOOK_SECRET`, `ADMIN_TOKEN`, `BILLING_PROVIDER=webhook`. The real `output/` tree and the developer's own licenses are never touched.
- `STOCKER_TEST_MODE=1` fast paths (no network): `app/server.py` (mock SSE stream, mock history/live-quote/live-quotes, mock ticker-tape), `app/data_fetcher.py` (mock yfinance/requests), `app/ai_engine.py` (`_call_llm` returns None -> deterministic `_fallback`), `app/terminal_commands.py`.
- Playwright: `pytest-playwright` + `playwright` (Python). Chromium required: `venv\Scripts\playwright install chromium`.

## Commands
```
venv\Scripts\python.exe -m pytest tests/e2e/test_adversarial.py -q   # fast, no browser (~5s)
venv\Scripts\python.exe -m pytest tests/e2e/test_subscription.py -q   # licensing units/contracts (~10s)
venv\Scripts\python.exe -m pytest tests/e2e -q                        # full incl. chromium
STOCKER_TEST_MODE=1 venv\Scripts\python.exe -m pytest tests/e2e -v
```

## Hardening contract (enforced by tests)
- Malformed tickers (`../`, `;`, backticks, 50-char, `!!!`): `/api/stock/*` -> **400/404/422 only, never 200/500**, JSON error body on /api/*
- `/api/screener/filter` junk (`' OR 1=1 --`, `not_a_number`): **200/400 only, never 500**
- Unknown dashboard `ZZZZQ` -> **404** with "not found"; overlong ticker -> 400/404
- Empty `/api/stream` -> 200 with error text or 400; `/api/screener/ai` empty query -> 400
- Plan gates (free tier): gated APIs -> **402** with `error: "upgrade_required"`; gated pages -> **200** with the upgrade prompt; `/api/terminal/execute` -> **200** envelope (never a bare 403); zero configuration -> free tier, never a 500
