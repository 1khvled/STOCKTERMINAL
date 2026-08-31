# Project: StockerAI Personal Terminal - Bloomberg Grade Single-User

## Architecture
- Backend: Flask Server (app/server.py:1), AI Engine (app/ai_engine.py:1), Data Fetcher (app/data_fetcher.py:1) with yfinance+SEC+AlphaVantage, DCF/WACC registry
- Frontend: Bloomberg terminal 3-col layout HTML/CSS/JS in app/templates and app/static (dashboard_new.css, theme.css, hub.js, dashboard.js)
- Database: Local JSON cache -> Supabase optional mirror (app/supabase_db.py:1) + output/database/*.json, local portfolio.json
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
| 2 | Backend Reliability | yf retry, SEC 429 backoff, cache (15m/14d/1d), graceful missing-data fallback, server JSON error boundaries | IN_PROGRESS |
| 3 | Frontend Polish | 8 modules work, undefined guards, error toasts, price flash, watchlist/portfolio local | IN_PROGRESS |
| 4 | E2E Suite | Pass Tiers 1-4 (conftest STOCKER_TEST_MODE) | PLANNED |
| 5 | Adversarial Hardening | Tier 5 malformed tickers, empty DB, rate-limit soak | PLANNED |

## Interface Contracts
### Frontend <-> Backend
- JSON or HTML fragments; backend returns 400/404/500 JSON for /api/*, HTML for pages; frontend shows error boundaries via toast.js
### Backend <-> External APIs
- All yfinance/SEC calls via _yf_with_retry/_sec_request_with_retry with Retry-After; on failure returns empty DataFrame + fallback metrics, never crashes analyzer

## Quick Start
```
pip install -r requirements.txt
python -m app.stock_analyzer AAPL            # one-off
python -m app.server --server               # http://127.0.0.1:5001
STOCKER_TEST_MODE=1 pytest tests/e2e -v
```
