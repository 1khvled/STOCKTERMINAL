# STOCKERAI PERSONAL TERMINAL — PROJECT TIMELINE (A → Z)

**Canonical:** `docs/PROJECT_TIMELINE.md` (in repo)
**Mirror:** `C:\Users\Abdelli\Documents\PROJECT_TIMELINE.md` (for agents using filesystem tool)
**Both must stay in sync after every change — append only, never rewrite history.**

---

## Agent Rule — Context Timeline (MANDATORY)

### Before any edit
- Read `docs/PROJECT_TIMELINE.md` (and `C:\Users\Abdelli\Documents\PROJECT_TIMELINE.md` mirror) fully. It is the A-to-Z timeline. Do not re-discover what is already documented.
- Read `AGENTS.md` and `PROJECT.md` for conventions.

### After every modification (code / env / DB / deploy / worker / docs)
- **Update `docs/PROJECT_TIMELINE.md`:**
  1. Append a dated bullet under `## Timeline` — date, commit SHA, deployment ID (if any), what/why, files changed, verification (tsc, tests, curl, logs).
  2. Copy the updated file to `C:\Users\Abdelli\Documents\PROJECT_TIMELINE.md` (mirror for filesystem tool).
  3. Keep it strictly chronological, no gaps, no rewriting history — append only.
- If you skip this, you are violating the project rule. The file must stay the full A-to-Z for the next agent.

### Conventions to enforce
- `event_id` dedup, per-item locks, `maxDuration` exports, `isQuotaExhaustedBody`, `due_date + localToday()`, `CHUNK_SIZE` 1 for Hobby (if workers existed — adapted for Flask: `OUTPUT_DIR` via `config.py`, `DB_DIR = OUTPUT_ROOT / "database"`, no hardcoded `C:\...` paths).
- Personal terminal: **NO premium** — no auth, no Stripe, no pricing, no login, no credits gate. All routes local, all models free (Groq/Qwen, OpenRouter, Gemini fallback). `GROQ_MODEL=qwen/qwen3-32b` via `.env` + embedded fallback in `app/config.py:34`.
- `public/*` canonical + `Copy-Item` to root (if static), `tsc --noEmit` clean equivalent `py_compile` clean, tests `pytest`, `eslint 0 errors` equivalent `py_compile 0 errors`.
- `OUTPUT_DIR = BASE_DIR / "output"` , `DB_DIR = OUTPUT_ROOT / "database"`, cache `output/cache/*.pkl` with TTLs (15m raw, 14d statements, 1d aux).
- Where the timeline lives both paths must stay in sync.

---

## Timeline

### 2026-05-28 — Initial History (pre-personal)
- **c8c24b1** `initial commit` — Base Flask + yfinance + Groq scaffold. Files: `app/server.py`, `app/data_fetcher.py`, `app/ai_engine.py`, `app/config.py`, `app/dashboard_generator.py`, `app/templates/*`, `requirements.txt`. Verification: git log.

### 2026-05-28 — Bloomberg Restyle
- **a984b1d** `Restyled stock dashboard template and stylesheet into Bloomberg Terminal design language` — 3-column dark terminal, hero, stats strip. Files: `app/templates/dashboard.html`, `app/static/css/dashboard_new.css`, `app/static/css/theme.css`. Verification: manual.

### 2026-05-28 — Strip SaaS Endpoints
- **33c0461** `Strip remaining macro/auth endpoints and reorganize stock workstation into data-dense 3-column Bloomberg layout` — Removed macro/auth bloat, reorganized workstation. Files: `app/server.py`, `app/static/js/hub.js`. Verification: grep no `auth` hits.

### 2026-05-28 — Hub Merge Fix
- **3eb3ecf** `Fix merge conflict in hub.js` — Resolved hub.js conflict, 838 insertions, 1032 deletions. Files: `app/static/js/hub.js`. Verification: `hub.js` 74331 B.

### 2026-09-08 — Understanding Both Clones (this chat)
- **No commit** — Compared `C:\Users\Abdelli\Desktop\Projects\STOCK_TERMINAL_ALONE` (229 files, 30 tickers, personal Bloomberg branch, no remote) vs `STOCK_TERMINAL_ALONE_BACKUP` (946 files, 11 tickers, SaaS branch with `app/auth.py`, `app/saas_db.py`, `pricing.html`, `vercel.json`, `origin https://github.com/1khvled/STOCKTERMINAL.git`). Found BACKUP = ALONE + SaaS bloat, ALONE working tree had uncommitted personal improvements (7573 insertions). Compared `data_fetcher.py` (ALONE 92243 B vs BACKUP 135665 B), `server.py` (ALONE 42289 B clean vs BACKUP 94289 B SaaS). Verification: `robocopy /L`, `git log --graph`, `Get-FileHash`, `Select-String` premium hits.

### 2026-09-08 — Merge Valuable Assets
- **No commit yet** — Copied `app/news_engine.py` (9416 B) missing in ALONE, merged 3 tickers `META.json`, `NOW.json`, `ORCL.json` from BACKUP `output/database/` (BACKUP had 11, ALONE had 30 → 33), merged `data/verdict_history.json`. Verification: `Test-Path`, `Copy-Item`.

### 2026-09-08 — Strip Premium Traces
- **No commit yet** — Renamed `BACKUP` → `STOCK_TERMINAL_ALONE_BACKUP_ARCHIVED_DO_NOT_USE`, added remote to ALONE, cleaned `app/server.py:1` SaaS comment → Personal, `app/stock_analyzer.py:36` banner, `app/dashboard_generator.py:1594` `Premium Data & DCF` → `Valuation & DCF`, deduped `.env` 39→26 lines (removed duplicate `FINNHUB/FMP/TIINGO/GROQ` keys), fixed `dashboard_new.css` header garble. Verification: `python -m py_compile` none, `Flask app 45 routes`.

### 2026-09-08 — Personal Commit (Merge)
- **f6c7c6d** `Personal terminal: merge ALONE+BACKUP, strip SaaS/premium, Bloomberg 3-col layout, single-user local - no auth/billing` — 66 files, 18995 insertions, 2880 deletions. Files: `PROJECT.md`, `TEST_INFRA.md`, `app/intelligence_terminal.py`, `app/news_engine.py`, `app/supabase_db.py`, `app/templates/*`, `app/static/*`, `package.json`, `tests/e2e/conftest.py`, delete `strip_server.py`. Verification: `git show --stat`, `py_compile` none, `app.test_client` 45 routes.

### 2026-09-08 — Audit Hardcoded Path
- **af28b33** `audit: fix hardcoded absolute path in query_search, use DB_DIR for portability` — Replaced `C:\Users\Abdelli\...\output\database` with `DB_DIR` `app/server.py:414` and `db_dir.glob("*.json")`. Files: `app/server.py` 6 insertions. Verification: `Select-String C:\\` 0 hits, `app.test_client` `/api/query/search?q=AAPL` 200.

### 2026-09-08 — Improve All (Reliability)
- **6fe776c** `improve all: yf retry with backoff, server JSON error boundaries (404/500/429), fetch retry, safeDisplay, personal PROJECT.md` — Added `_yf_with_retry` with 429/Retry-After `app/data_fetcher.py:283`, wrapped concurrent `ticker.info/history` `app/data_fetcher.py:1739`, added `404/500/429` JSON handlers `app/server.py:1052`, wrapped `api/stocks`/`screener/filter`, added `_fetchWithRetry` `app/static/js/hub.js:1`, `safeDisplay` `app/static/js/dashboard.js:10`, rewrote `PROJECT.md`. Files: 5 files. Verification: `py_compile` none, `pytest tests/e2e 3 passed` (37s), `/api/system/health` 33.

### 2026-09-08 — Hub Simplified (Remove Hebrish Clutter)
- **a49e81e** `personal: strip hebrish clutter, simplify hub to single free analyzer (FCF/DCF/monte/calc, no premium, local DB 33 stocks)` — Replaced `app/templates/index.html` 261→113 lines fiscal bloat → minimal personal hub (ticker input, Analyze streaming, 30-stock grid). Kept `dashboard.html` (70k) for analyzer. Deleted `index.old.html`. Files: `app/templates/index.html` 109 insertions, 257 deletions. Verification: `Invoke-WebRequest /` 7173 B `NEW INDEX OK`, `/api/stocks` 200.

### 2026-09-08 — Dashboard CRM Polish + Qwen
- **7f91e47** `dashboard CRM: fix hebrish mojibake (cleanText, arrows, placeholders), sticky tab nav, hero polish; embed Groq gsk_... + Qwen qwen/qwen3-32b algos` — Fixed `cleanText` mojibake `app/static/js/dashboard.js:10`, arrows `^/v` `app/static/js/dashboard.js:340`, placeholders `--` `app/static/js/dashboard.js:338`, `dashboard_new.css` sticky `tab-nav` `app/static/css/dashboard_new.css:503`, embedded `GROQ_API_KEY=[REDACTED-GROQ-KEY]...` fallback + `GROQ_MODEL=qwen/qwen3-32b` `app/config.py:34`, `.env` added `GROQ_MODEL`. Files: 3 files. Verification: `GET /dashboard/CRM` 70270 B `garbled? False`.

### 2026-09-08 — Live Prices + Quarterly Auto-Update
- **5bb99db** `live prices: yfinance batch live-quotes + 30s poll on hub/dashboard; quarterly auto-update scheduler (85d/earnings, hourly check, manual trigger /api/system/auto-update/*)` — Live `api_live_quotes` batch `yf.Tickers` `app/server.py:1011`, hub 30s `refreshLive` `app/templates/index.html:68`, dashboard `pollLive` every 30s `app/static/js/dashboard.js:446`, auto-update worker `_auto_update_worker` `app/server.py:1072` (85d age or earnings, hourly scan, 90s throttle), endpoints `GET /api/system/auto-update/status` + `POST /api/system/auto-update/trigger` `app/server.py:1072`. Files: 3 files. Verification: `/api/stocks/live-quotes?tickers=AAPL,CRM` live `yfinance` `price 316.85/257.54`, `/api/system/auto-update/status` 33 tracked, hub `Live` true.

### 2026-09-08 — Delete NEW PROJECT Duplicate
- **No commit (file delete)** — Removed `C:\Users\Abdelli\Desktop\Projects\NEW PROJECT` (1.7 GB, 40740 B `app/server.py` with `@premium_required`, `app/auth.py`). Confirmed duplicate SaaS/premium via `Select-String` `premium_required`, `Get-FileHash`. Verification: `Test-Path` false, `Get-ChildItem Projects` no NEW PROJECT.

### 2026-09-08 — Rebuild Dashboard From Scratch (Minimal)
- **e07fc64** `rebuild dashboard from scratch: clean Bloomberg minimal (FCF/DCF/monte/PE peers/financials/risks), live price 30s, no hebrish` — Backed up `dashboard.html/js/css`, replaced `dashboard.html` 8512 B 118 lines (was 70k), `dashboard.js` 10476 B 189 lines (was 85k), `dashboard_new.css` 15→54 lines Bloomberg dark. Features: `VERDICT/VALUATION/FINANCIALS/PEERS/RISKS` tabs, `FCF base • WACC • Terminal` `app/templates/dashboard.html:68`, `priceTarget 12m/Bull/Bear`, `Monte/ CCA/DDM/regression`, Notion stripped for minimal. Files: 3 files, 6080 deletions. Verification: `GET /dashboard/APP` 8447 B `CRM OK new dashboard`.

### 2026-09-08 — Dashboard v3 Notion Research
- **f7bed79** `dashboard v3: add Notion RESEARCH tab (briefing/earnings/price/risk subpages), render notion html, FCF/DCF valuation polished` — Added `NOTION RESEARCH` tab `app/templates/dashboard.html:48`, `panel-notion` with `notion-subnav`/`notion-content` `app/templates/dashboard.html:105`, CSS `.notion-*` `app/static/css/dashboard_new.css:55`, JS render `subpages` `app/static/js/dashboard.js:98` (`briefing, earnings, price_review, risks` for CRM from `/api/stock/CRM` `notion_data`). Verification: `GET /dashboard/CRM` 9093 B `notion? True tabs? True`, `notion keys: briefing, earnings, overview, price_review, risks`.

### 2026-09-08 — Context Timeline (This File)
- **Pending commit** — Created `docs/PROJECT_TIMELINE.md` full A-Z + mirror `C:\Users\Abdelli\Documents\PROJECT_TIMELINE.md`, embedded rule for future agents to append Timeline + Agent Log after every modification. Files: `docs/PROJECT_TIMELINE.md`, mirror. Verification: `Test-Path docs`, `git status`.

---

## Architecture (Current)

- **Backend:** `app/server.py:1` Flask 45 routes + SSE `api/stream` + live `api/stocks/live-quotes` (yfinance batch) + auto-update `api/system/auto-update/*`, `OUTPUT_ROOT = Path(OUTPUT_DIR)` `DB_DIR = OUTPUT_ROOT / "database"`.
- **Data:** `app/data_fetcher.py:1` concurrent yfinance with `_yf_with_retry` (429, Retry-After), SEC retry, 15m raw cache + 14d statements + 1d aux, DCF `calculate_dcf` mid-year, Monte 500, CCA/DDM/regression, scores Altman/Piotroski/Beneish/DuPont.
- **AI:** `app/ai_engine.py:1` unified `_call_llm` (OpenCode → OpenRouter → Anthropic → Groq `qwen/qwen3-32b` `app/config.py:34` with key rotation/cool-down, 3 prompts fund/val, macro/risk, red-team).
- **Frontend:** Hub `app/templates/index.html:1` minimal personal (ticker input, 30s live poll, 30-stock grid), Dashboard `app/templates/dashboard.html:1` 6 tabs with Notion, `app/static/css/dashboard_new.css:1` Bloomberg dark, `app/static/js/dashboard.js:1` live poll 30s, `safeDisplay`, `pollLive`.
- **DB:** Local `output/database/*.json` 33 stocks (CRM, APP, etc.) + optional Supabase mirror `app/supabase_db.py:1`, local `portfolio.json`, Notion research via `app/notion_integrator.py:1`.
- **Tests:** `tests/e2e` Playwright + `STOCKER_TEST_MODE=1` `tests/e2e/conftest.py:1`, 3 tests pass.

---

## Agent Log

| Date | Model | Task | Commit | Files |
|------|-------|------|--------|-------|
| 2026-09-08 | muse-spark-1.2 | Merge ALONE+BACKUP, strip SaaS, Bloomberg | f6c7c6d | 66 files, app/*, PROJECT.md |
| 2026-09-08 | muse-spark-1.2 | Audit hardcoded path | af28b33 | app/server.py |
| 2026-09-08 | muse-spark-1.2 | Improve all (yf retry, error boundaries) | 6fe776c | app/data_fetcher.py, app/server.py, hub.js, dashboard.js, PROJECT.md |
| 2026-09-08 | muse-spark-1.2 | Strip hebrish, simplify hub | a49e81e | app/templates/index.html |
| 2026-09-08 | muse-spark-1.2 | Dashboard CRM mojibake fix + Qwen | 7f91e47 | app/config.py, dashboard.js/css, .env |
| 2026-09-08 | muse-spark-1.2 | Live prices + quarterly auto-update | 5bb99db | app/server.py, dashboard.js, index.html |
| 2026-09-08 | muse-spark-1.2 | Rebuild dashboard from scratch | e07fc64 | dashboard.html/js/css |
| 2026-09-08 | muse-spark-1.2 | Dashboard v3 Notion | f7bed79 | dashboard.html/js/css |
| 2026-09-08 | muse-spark-1.2 | Context timeline creation | pending | docs/PROJECT_TIMELINE.md + mirror |

---

## Verification Checklist (for next agent)

- `python -m py_compile` none
- `pytest tests/e2e -v` 3 passed
- `curl http://127.0.0.1:5001/api/system/health` → 33
- `curl http://127.0.0.1:5001/dashboard/APP` → 200, no `�`
- `curl http://127.0.0.1:5001/api/stocks/live-quotes?tickers=AAPL,CRM` → `yfinance` source
- `git log --oneline -5` shows timeline commits

---

## Quick Start (Personal)

```
pip install -r requirements.txt
python -m app.server --server   # http://127.0.0.1:5001
# Hub: http://127.0.0.1:5001/
# Dashboard: http://127.0.0.1:5001/dashboard/AAPL
# Live: polling /api/stocks/live-quotes + /api/stock/<ticker>/live-quote 30s
# Auto: POST /api/system/auto-update/trigger
STOCKER_TEST_MODE=1 pytest tests/e2e -v
```
