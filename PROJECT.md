# Project: StockerAI Personal Terminal - Bloomberg Grade Single-User

## Architecture
- Backend: Flask Server (app/server.py), AI Engine (app/ai_engine.py), Data Fetcher (app/data_fetcher.py) with yfinance+SEC+AlphaVantage, DCF/WACC registry
- Frontend: Bloomberg terminal 3-col layout HTML/CSS/JS in app/templates and app/static (dashboard_new.css, theme.css, hub.js, dashboard.js)
- Database: Local JSON cache -> Supabase optional mirror (app/supabase_db.py) + output/database/*.json, local portfolio.json
- External: Yahoo Finance, Groq/OpenRouter/Gemini (config.py), Notion optional, SEC EDGAR

## Code Layout
- `app/server.py`: Flask entrypoint, 45 routes, SSE stream, catalog/screener/query, intel/portfolio/terminal - all local, no auth
- `app/data_fetcher.py`: Concurrent yfinance fetch with 15m cache, 14d statement cache, _yf_with_retry, SEC retry, DCF/MonteCarlo/CCA/DDM, scores (Altman/Piotroski/Beneish/DuPont)
- `app/ai_engine.py`: Unified _call_llm (OpenCode->OpenRouter->Anthropic->Groq) with key rotation/cool-down, 3 prompts (fund/val, macro/risk, red-team)
- `app/dashboard_generator.py`: Generates per-ticker HTML dashboard, Valuation & DCF panel
- `app/templates`: index.html hub, dashboard.html, intel_page.html/pro_page.html, modules/*, 404.html; `app/static/css|js`
- `tests/e2e`: Playwright + requests (conftest.py) with STOCKER_TEST_MODE=1

## Personal Terminal Principles (no premium)
- Single local user, no login/register/pricing/stripe/credits - all features unlocked
- All routes local: /watchlist /reports /market-feed /system /news-impact /filings /scenario-lab /committee /red-flags /portfolio
- Bloomberg terminal UX: data-dense, zero undefined leaks (safeDisplay), fetch retry on 429, SSE stream with keepalive

## Milestones
| # | Name | Scope | Status |
|---|------|-------|--------|
| 1 | Merge & Personalize | ALONE+BACKUP merged, SaaS stripped, Bloomberg layout, .env deduped | DONE af28b33 |
| 2 | Backend Reliability | yf retry (status-aware 429, Retry-After, jitter, no retry on bad ticker), SEC 429 backoff (exponential + jitter, Host-aware), cache (15m/14d/1d rglob), graceful missing-data fallback, server JSON error boundaries, persistent Flask secret, CORS locked to localhost | DONE 2026-09-01 |
| 3 | Frontend Polish | 8 modules work, safeDisplay/esc guards, toast.js on all pages, price flash live 30s, fetch retry on 429, skeleton loaders, Notion subnav, responsive Bloomberg CSS | DONE 2026-09-01 |
| 4 | E2E Suite | Pass Tiers 1-4 (conftest STOCKER_TEST_MODE, Playwright) — 3 core tests pass; TEST_MODE fast paths for history/live-quote | DONE 2026-09-01 |
| 5 | Adversarial Hardening | Tier 5 malformed tickers, empty DB, rate-limit soak — is_valid_ticker hardened (12 char, no traversal), financials/history/live-quote validate 400, SEC/yf retry hardened, 13 adversarial tests | DONE 2026-09-01 |
| 6 | Polish A-Z (2026-09-01) | Security: removed hardcoded Groq keys, .env.example, .flask_secret gitignored, CORS no credentials; Infra: duckduckgo-search pinned, start.cmd quiet, NUL removed, dashboard_new.css price-flash+toast+shimmer; Docs: Supabase REST note, Bloomberg UX contracts | DONE |

## Interface Contracts
### Frontend <-> Backend
- JSON or HTML fragments; backend returns 400/404/500 JSON for /api/*, HTML for pages; frontend shows error boundaries via toast.js
### Backend <-> External APIs
- All yfinance/SEC calls via _yf_with_retry/_sec_request_with_retry with Retry-After; on failure returns empty DataFrame + fallback metrics, never crashes analyzer

## Quick Start
```
pip install -r requirements.txt
python -m app.stock_analyzer AAPL            # one-off
python -m app.server                         # http://127.0.0.1:5001
STOCKER_TEST_MODE=1 pytest tests/e2e -v
```

## Polish Notes (2026-09-01)
- Config: no hardcoded secrets, keys from .env only
- Server: persistent secret at output/.flask_secret, CORS localhost-only, is_valid_ticker hardened, 404/500/429 JSON handlers, rglob cache size
- Data: yf retry status-aware + Retry-After + jitter + no-retry on bad ticker; SEC retry Host-aware + exponential jitter capped 30s
- Frontend: dashboard.js safeDisplay/esc/toast, fetchData retry with Retry-After, pollLive price flash, recalc validation; hub.js catalog toast; dashboard.html+index.html load toast.js; dashboard_new.css adds price-flash, toast, shimmer, notion-btn
- Infra: requirements pinned flask-cors>=4.0.0 + duckduckgo-search, .env.example, .gitignore + .flask_secret/output/cache/*.log, start.cmd checks flask before pip
- Tests: tests/e2e/test_adversarial.py (13 Tier5 tests), server TEST_MODE fast paths for history/live-quote
