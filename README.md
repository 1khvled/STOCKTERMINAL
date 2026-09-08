# StockerAI — Personal Bloomberg-Grade Terminal

Single-user, local-only stock terminal. No auth, no billing, no premium gates. Bloomberg-dense UI + institutional quant engine, running entirely on your machine.

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

## Features

- **Analysis pipeline:** `app/stock_analyzer.py` — fetch → AI → dashboard + Excel + JSON cache. DCF/WACC registry, Monte Carlo, CCA/DDM, Altman Z, Piotroski F, Beneish M, DuPont.
- **Data:** `app/data_fetcher.py` — yfinance + SEC EDGAR with 15m quote cache / 14d statement cache, status-aware retry (429 Retry-After + jitter), graceful fallback to empty frames, never crashes analyzer.
- **AI:** `app/ai_engine.py` — `_call_llm` with rotation (OpenCode → OpenRouter → Anthropic → Groq), key rotation + cooldown, 3 skeptical prompts (fund/val, macro/risk, red-team), valuation coherence enforcement.
- **Server:** `app/server.py` — Flask, 45 routes, SSE `/api/stream` with keepalive, `/api/stocks` catalog, screener (`/api/screener/filter` + AI), query, intel (`/api/intel/*`), portfolio, terminal (`/api/terminal/execute` 64-char whitelist), live quotes `/api/stocks/live-quotes` (30s poll) + ticker tape (5m), quarterly auto-update worker, persistent `output/.flask_secret`, CORS localhost-only, JSON 400/404/500.
- **Frontend:** Bloomberg 3-col dark terminal (`theme.css`, `dashboard_new.css`), safeDisplay/esc guards, `toast.js` on every page, price-flash live poll, 429 retry with Retry-After, skeleton + shimmer, Notion subnav, terminal overlay (`Ctrl+~`, `CLEAR`, `DES/DCF/COMP/CHART/ER/SCREEN/NEWS/SEC/LAB/IC/FLAGS/PORT`).
- **Storage:** Local JSON `output/database/*.json` + `output/portfolio.json` (`app/local_db.py`, pure stdlib, no database needed).
- **Outputs:** `output/<TICKER>/` → `<TICKER>_dashboard.html`, `<TICKER>_Financial_Model.xlsx` (dynamic formulas), `cache/`, `database/`.

## Routes

- Pages: `/` hub, `/dashboard/<TICKER>`, `/compare`, `/watchlist`, `/reports`, `/market-feed`, `/system`, `/news-impact`, `/filings`, `/scenario-lab`, `/committee`, `/red-flags`, `/portfolio`, `/guide`, `/module/<name>`
- APIs: `/api/stocks`, `/api/stock/<TICKER>`, `/api/stock/<TICKER>/financials|history|live-quote|recalculate`, `/api/stocks/live-quotes`, `/api/ticker-tape`, `/api/screener/*`, `/api/query/search`, `/api/intel/*`, `/api/portfolio`, `/api/terminal/execute`, `/api/system/health`, `/api/system/auto-update/*`, `/api/reports`, `/api/stream?ticker=`

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
app/templates/              index.html, dashboard.html, intel_page.html, pro_page.html, guide.html, 404.html
app/static/css|js           theme.css, terminal.css, hub.js, dashboard.js, toast.js, terminal.js
output/                    database/*.json, portfolio.json, cache, .flask_secret (gitignored)
tests/e2e/                 Playwright+requests, conftest STOCKER_TEST_MODE=1
start.cmd / kill_server.cmd Windows launchers
```

## Tech

Python 3.11+, Flask 3 + flask-cors, yfinance, pandas/numpy, openpyxl/xlsxwriter, requests, beautifulsoup4, groq/anthropic SDKs, duckduckgo-search (optional). Node not required. Tests: pytest + playwright.

## Notes

- Single local user — no login, no Stripe, no credits.
- `output/` and `.flask_secret` are gitignored; 454 MB catalog example is local only.
- Live prices: frontend polls `/api/stocks/live-quotes` every 30s; ticker tape cached 5m.
- Quarterly auto-update: worker checks hourly, refreshes >85d or earnings-near tickers, 60–90s pacing. Manual: `POST /api/system/auto-update/trigger`.
- See `PROJECT.md` for milestones/contracts and `TEST_INFRA.md` for test tiers.
