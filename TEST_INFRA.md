# E2E Test Infra: StockerAI Personal Terminal (2026-09-08 rewrite)
# Replaces the stale Tier 1-4 plan - documents the 29-test reality.

## Reality (verified 2026-09-08)
- Runner: `pytest` (`pytest.ini`: `testpaths=tests`, `test_*.py`)
- Collection: **29 tests** (`pytest --collect-only -q`)
  - `tests/e2e/test_dummy.py` (3): server up, Playwright chromium body visible, mock SSE `REDIRECT: /dashboard/AAPL`
  - `tests/e2e/test_adversarial.py` (26): Tier-5 malformed tickers (14 params), empty/stream/screener/query/portfolio/terminal/rate-limit/missing/404/health/live-quote
- No Tier 1-4 feature-matrix files exist - adversarial + smoke is the suite.

## Environment
- `tests/e2e/conftest.py`: spawns `venv\Scripts\python.exe -m app.server` on **port 5005** (`STOCKER_PORT`), `STOCKER_TEST_MODE=1`, waits 30x0.5s on `/`. Prod runs 5001 - never collide.
- `STOCKER_TEST_MODE=1` fast paths (no network): `app/server.py` (mock SSE stream, mock history/live-quote/live-quotes, mock ticker-tape), `app/data_fetcher.py` (mock yfinance/requests), `app/ai_engine.py` (`_call_llm` returns None -> deterministic `_fallback`), `app/terminal_commands.py`.
- Playwright: `pytest-playwright` + `playwright` (Python). Chromium required: `venv\Scripts\playwright install chromium`.

## Commands
```
venv\Scripts\python.exe -m pytest tests/e2e/test_adversarial.py -q   # fast, no browser (~5s)
venv\Scripts\python.exe -m pytest tests/e2e -q                        # full incl. chromium
STOCKER_TEST_MODE=1 venv\Scripts\python.exe -m pytest tests/e2e -v
```

## Hardening contract (enforced by tests)
- Malformed tickers (`../`, `;`, backticks, 50-char, `!!!`): `/api/stock/*` -> **400/404/422 only, never 200/500**, JSON error body on /api/*
- `/api/screener/filter` junk (`' OR 1=1 --`, `not_a_number`): **200/400 only, never 500**
- Unknown dashboard `ZZZZQ` -> **404** with "not found"; overlong ticker -> 400/404
- Empty `/api/stream` -> 200 with error text or 400; `/api/screener/ai` empty query -> 400
