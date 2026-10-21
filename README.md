# StockerAI — Personal Bloomberg-Grade Terminal

Single-user, local-first stock terminal. Bloomberg-dense UI + institutional quant engine, running entirely on your machine. Free tier covers the whole quant core; Pro adds the desk-grade surfaces (scenario lab, investment committee, red flags, headless API).

**Live:** `python app/server.py` → http://127.0.0.1:5001

## Quick Start

```cmd
:: Windows — double-click or:
start.cmd

:: Manual:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   :: fill GROQ_API_KEY or OPENROUTER_API_KEY
python -m app.server     :: http://127.0.0.1:5001

:: One-off analysis (no server):
python -m app.stock_analyzer AAPL
python -m app.stock_analyzer AAPL,MSFT,NVDA

:: Tests (no network):
set STOCKER_TEST_MODE=1 && pytest tests/e2e -v
```

Minimum env: at least one LLM key

```
GROQ_API_KEY=gsk_...                # console.groq.com (free)
# or OPENROUTER_API_KEY=sk-or-...   # openrouter.ai
# or GEMINI_API_KEY=... / ANTHROPIC_API_KEY=...
SEC_USER_AGENT=YourName email@example.com
```

See `.env.example` for all options (Finnhub, Notion are optional).

## Plans

| | Free | Pro |
|---|---|---|
| Analysis pipeline, dashboard, watchlist, portfolio, compare, news, filings, macro, screener | yes | yes |
| Model exports | 10/day | unlimited |
| Scenario Lab, Investment Committee, Red Flags, headless terminal API, batch screening | - | yes |

A Pro license is one key, entered once at `/activate`, bound to the machine.
Offline works for 14 days past the last check. **Zero configuration = free tier,**
never a crash. Operator runbook: `docs/SUBSCRIPTION.md`.

```cmd
python -m app.licensing seed                          :: demo (pro) + free accounts
python -m app.licensing issue --email b@x.com --plan pro --months 12
```

## Features

- **Analysis pipeline:** `app/stock_analyzer.py` — fetch → AI → dashboard + Excel + JSON cache. DCF/WACC registry, Monte Carlo, CCA/DDM, Altman Z, Piotroski F, Beneish M, DuPont.
- **Data:** `app/data_fetcher.py` — yfinance + SEC EDGAR with 15m quote cache / 14d statement cache, status-aware retry (429 Retry-After + jitter), graceful fallback to empty frames, never crashes analyzer.
- **AI:** `app/ai_engine.py` — `_call_llm` with rotation (Groq-first easy route; hard route OpenCode → OpenRouter → Gemini → Anthropic → Groq), key rotation + cooldown, 3 skeptical prompts (fund/val, macro/risk, red-team), valuation coherence enforcement.
- **Server:** `app/server.py` — Flask, 69 routes, SSE `/api/stream` with keepalive, `/api/stocks` catalog, screener (`/api/screener/filter` + AI, 21 TradingView filters), compare AI judge (`/api/compare/judge`), query, intel (`/api/intel/*`), portfolio (SPY benchmark), terminal (`/api/terminal/execute` 64-char whitelist), live quotes `/api/stocks/live-quotes` (30s poll) + ticker tape (5m), quarterly auto-update worker, persistent `output/.flask_secret`, CORS localhost-only, JSON 400/404/500.
- **Frontend:** Bloomberg 3-col dark terminal (`theme.css`, `dashboard_new.css`), safeDisplay/esc guards, `toast.js` on every page, price-flash live poll, 429 retry with Retry-After, skeleton + shimmer, Notion subnav. Command UIs are dormant: the overlay was culled and the shell bar (`terminal_shell.js`) never initializes — no page sets the `terminal-shell` body class and its CSS is gone — so navigate via page links. Headless terminal API stays available (`POST /api/terminal/execute`: `HELP/CLEAR/PING/[TICKER]/DES/DCF/COMP/CHART/ER/SCREEN/NEWS/SEC/LAB/IC/FLAGS/PORT ADD|REMOVE|LIST`); its responses may reference a `runTerminalCommand()` handler that stock pages do not define, so consume the API directly.
- **Storage:** Local JSON `output/database/*.json` + `output/portfolio.json` (`app/local_db.py`, pure stdlib, no database needed).
- **Subscriptions:** `app/licensing.py` + `app/accounts.py` + `app/billing.py` + `app/account_bp.py` — license keys (hashed in `output/accounts.db`), machine binding (hashed machine fingerprint), signed offline entitlement file with a 14-day grace period, plan gates on the Pro surfaces, operator CLI (`python -m app.licensing`) and an `ADMIN_TOKEN` console. Stdlib only (`sqlite3`, `hmac`, `hashlib`). See `docs/SUBSCRIPTION.md`.
- **Outputs:** `output/<TICKER>/` → `<TICKER>_dashboard.html`, `<TICKER>_Financial_Model.xlsx` (dynamic formulas), `cache/`, `database/`.

## Routes

- Pages: `/` hub, `/dashboard/<TICKER>`, `/compare`, `/watchlist`, `/reports`, `/market-feed`, `/system`, `/news-impact`, `/filings`, `/scenario-lab`, `/committee`, `/red-flags`, `/portfolio`, `/guide`, `/module/<name>`
- Account: `/signup`, `/login`, `/logout`, `/account`, `/billing`, `/activate`, `/pricing`, `/admin`
- APIs: `/api/stocks`, `/api/stock/<TICKER>`, `/api/stock/<TICKER>/financials|history|live-quote|recalculate`, `/api/stocks/live-quotes`, `/api/ticker-tape`, `/api/screener/*`, `/api/query/search`, `/api/intel/*`, `/api/portfolio`, `/api/terminal/execute`, `/api/batch/screen`, `/api/account/me`, `/api/billing/webhook`, `/api/entitlement/verify`, `/api/system/health`, `/api/system/auto-update/*`, `/api/reports`, `/api/stream?ticker=`

## Project Layout

```
app/server.py              Flask entrypoint
app/config.py              Env keys (no hardcoded secrets), validate_config
app/data_fetcher.py        yfinance/SEC fetch, scores, DCF registry
app/ai_engine.py            LLM routing + valuation coherence
app/stock_analyzer.py      CLI pipeline + terminal quant briefing
app/dashboard_generator.py  Per-ticker HTML generation
app/excel_generator.py      Dynamic Excel model
app/local_db.py             Local JSON file database (no cloud)
app/terminal_commands.py    64-char whitelist, html-escaped, test-mode mock
app/intelligence_terminal.py  News/sec/scenario/committee/flags cache 15m
app/licensing.py           License keys, machine binding, signed entitlements, plan gates, operator CLI
app/accounts.py            sqlite3 accounts/subscriptions/licenses/entitlements/audit (output/accounts.db)
app/billing.py             Pluggable provider: manual | webhook | none
app/account_bp.py          Flask blueprint: signup/login/account/billing/activate/pricing/admin/webhook
app/templates/              index.html, dashboard.html, intel_page.html, pro_page.html, guide.html, 404.html,
                            auth.html, account.html, billing.html, activate.html, pricing.html, upgrade.html, admin.html
app/static/css|js           theme.css, terminal.css, hub.js, dashboard.js, toast.js, terminal.js
output/                    database/*.json, portfolio.json, cache, .flask_secret, accounts.db,
                           .entitlement.json, .license_secret (gitignored)
tests/e2e/                 Playwright+requests, conftest STOCKER_TEST_MODE=1
docs/SUBSCRIPTION.md       Plans, licensing architecture, operator runbook
start.cmd / kill_server.cmd Windows launchers
```

## Tech

Python 3.11+, Flask 3 + flask-cors, yfinance, pandas/numpy, openpyxl/xlsxwriter, requests, beautifulsoup4, groq/anthropic SDKs, duckduckgo-search (optional). Node not required. Tests: pytest + playwright. Licensing adds **no** dependency: `sqlite3` + `hmac` + `hashlib` only.

## Notes

- Local-first, single-user desktop app — the buyer runs it on their own machine, their data never leaves it.
- Subscriptions: one license key, bound to the machine, offline-capable for 14 days. Free tier works with zero configuration. See `docs/SUBSCRIPTION.md`.
- `output/` and `.flask_secret` are gitignored; 454 MB catalog example is local only.
- Live prices: frontend polls `/api/stocks/live-quotes` every 30s; ticker tape cached 5m.
- Quarterly auto-update: worker checks hourly, refreshes >85d or earnings-near tickers, 60–90s pacing. Manual: `POST /api/system/auto-update/trigger`.
- See `PROJECT.md` for milestones/contracts and `TEST_INFRA.md` for test tiers.
