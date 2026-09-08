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

### 2026-09-08 — Polish A-Z Backend/Reliability (pre-existing, backfilled)
- **dd49ce2** `polish A-Z: backend reliability, frontend, security, infra` — yf retry status-aware + Retry-After + jitter, SEC Host-aware retry, server JSON error boundaries, persistent Flask secret, CORS localhost-only, hardened `is_valid_ticker`, rglob cache size. Verification: per commit message.

### 2026-09-08 — Polish A-Z Terminal/Hardening (pre-existing, backfilled)
- **d36efb3** `polish A-Z pt2: terminal hardening, stream/test mocks, frontend toast, docs` — Terminal command hardening, SSE TEST_MODE mocks, toast.js error boundaries, docs. Verification: per commit message.

### 2026-09-08 — Audit Follow-up (pre-existing, backfilled)
- **0e9f328** `audit follow-up: path traversal, cache memo, search limits, period whitelist, auto-update lock` — Path traversal guards (`relative_to` checks on excel/json), estimates cache memo, query search limits, history period whitelist (`ALLOWED_PERIODS`), `_auto_update_lock` introduced, TEST_MODE fast paths. Verification: `pytest` adversarial Tier-5.

### 2026-09-08 — Context Timeline File Committed
- **ddd93b8** `docs: add full A-Z PROJECT_TIMELINE + agent rule + mirror` — Created this file (canonical `docs/PROJECT_TIMELINE.md`, 13681 B) + mirror `C:\Users\Abdelli\Documents\PROJECT_TIMELINE.md`, embedded mandatory agent rule (read before edit, append Timeline + Agent Log + mirror after every modification). Verification: `Test-Path` both, server health 35 stocks.

### 2026-09-09 — A-Z Overhaul Plan (4-subagent audit)
- **No commit** — Launched 4 parallel `explore` subagents (backend / frontend / data-AI-Notion / infra-tests-docs, very thorough, research-only). Findings: 60-file uncommitted backlog safe to commit; worker lock race; SSE buffering; estimates TOCTOU; live-quotes uncached; dead `_catalog_row`/`cache_clear`; radar `.replace` crash; shell RUN no-op + dup NEWS; pro_pages `Promise.all`; CSS dup; Qwen model ids invalid (all AI on fallback); dead `llama-3.1-8b`/`nemotron` fallbacks; fragile Notion imports; non-atomic pickle; 11-ticker peer map; ignored test infra; stale TEST_INFRA/TIMELINE. Plan: Phase 0 triage → A backend → B frontend → C data/AI → D infra/docs → E verify. Verification: 4 audit reports on file.

### 2026-09-09 — Phase 0 Triage Commit
- **279765b** `triage: commit previous-AI backlog (local_db migration, Qwen 3.8-27b, frontend cull -12k)` — 62 files `+1957/-12311`: `supabase_db.py` deleted → new `app/local_db.py` (pure-stdlib, same schema), Qwen reasoning params, −12k lines dead CSS/JS/templates, new `app/templates/earnings.html`. Fixed 6 `git diff --check` whitespace errors first. Verification: `py_compile` 16 files 0 errors, `pytest --collect-only` 29 tests, secrets scan clean (only `gsk_...` placeholder in `.env.example` diff), `.env`/`output/.flask_secret` ignored + unstaged.

### 2026-09-09 — Phase A Backend Reliability
- **9afb935** `phase A backend: worker lock, SSE headers, estimates single-lock, live-quotes cache, dedup, trigger cap, CIK cache` — `_auto_update_worker` now `acquire(blocking=False)` + release on both paths (`app/server.py:1617`); SSE `Cache-Control:no-cache` + `X-Accel-Buffering:no` on mock + live streams (`app/server.py:319`); estimates single-lock read-modify-write (`app/server.py:1305`); `live_quotes_cache` 30s keyed (`app/server.py:1381`); `_db_path` delegates to `local_db.DB_DIR`, deleted dead 39-line `_catalog_row` + `cache_clear` no-op; trigger targets validated `list[str]` + capped 10; `terminal_commands.py:6` absolute `OUTPUT_DIR` via `config`; CIK 7d cache (`app/intelligence_terminal.py:537`). Verification: `test_client` health 200/39 stocks, SSE headers present, dashboard 200, `_db_path` delegates True, `py_compile` clean.

### 2026-09-09 — Phase B Frontend Fixes
- **1d37f5a** `phase B frontend: radar guard, shell RUN autorun, allSettled, wraps, dedup, aria, TOC` — `compare.html:576` `String(res.upside ?? '')` guard + call-site try/catch; shell `RUN X` works via hub `?ticker=` autorun (`index.html`), dup `NEWS` branch → `FEED`-only; `pro_pages.js:89` `Promise.all→allSettled` partial degrade; compare header/input `flex-wrap`; removed dup `.skeleton`/`shimmer` (`dashboard_new.css`); intel nav map + `aria-current`; guide TOC static capped strip on mobile (was `display:none`). Dropped B8 (theme vars all exist — non-issue). Verification: all 10 routes 200 via `test_client`, hub autorun present.

### 2026-09-09 — Phase C Data/AI (model emergency fixed by live probe)
- **d2ce9f3** `phase C data/AI: pin verified-live gpt-oss-120b, drop legacy, json mode, notion imports, atomic pickle, 39-ticker peers` — Probed Groq with both user keys: `llama-3.3-70b`, `qwen/qwen3-32b`, `qwen/qwen3.8-27b`, `llama-4-maverick`, `kimi-k2`, `qwen3-235b-thinking`, `deepseek-r1-distill` ALL dead (404 retired/decommissioned); only `openai/gpt-oss-120b` + `openai/gpt-oss-20b` LIVE. Pinned `GROQ_MODEL=openai/gpt-oss-120b` (`app/config.py:36`, `.env`), fallbacks → `gpt-oss-20b`, deleted 128-line `_call_llm_legacy` (+`nemotron-ultra`), `response_format=json_object` for OpenCode + OpenRouter, prompt headers → gpt-oss (Qwen params stay `_is_qwen`-gated), Notion dual `config`/`ai_engine` imports + server fallback, atomic tmp+rename pickle ×2, peer map 11→39 tickers (kills OpenRouter discovery call for all held stocks), `.env.example` SEC real-email note. Verification: live JSON `{"ok":true}` via Groq direct AND full `_call_llm` chain; `py_compile` clean.

### 2026-09-09 — Phase D Infra/Tests/Docs
- **ecaa00b** `phase D infra: un-ignore+pin test deps, module launch, Get-CimInstance, TEST_INFRA rewrite, harden asserts, drop Node/scratch` — Removed `pytest.ini` + `requirements-dev.txt` from `.gitignore`, pinned `pytest==9.0.3/pytest-playwright==0.8.0/playwright==1.60.0/requests==2.34.2`; `start.cmd` → `python -u -m app.server`; `kill_server.cmd` `wmic` (removed Win11 24H2) → `Get-CimInstance` + kept netstat fallback; rewrote `TEST_INFRA.md` (29-test reality, port 5005 vs 5001, TEST_MODE fast paths, hardening contract); hardened `test_adversarial.py` (malformed → 400/404/422 never 200/500; screener never 500; `ZZZZQ` → 404 + overlong → 400/404 — old test expected 200/404 for 14-char ticker, outdated after 12-char hardening); deleted `node_modules/` + `package.json`/`package-lock.json`/`debug.log`/`scratch/` from disk (README: Node not required; all gitignored except package.json which is now `D`). Full-suite 300s timeout diagnosed as port-5005 orphan + browser first-launch; per-file runs green. Verification: adversarial **26 passed in 1.65s**, dummy 3 passed in 4.65s.

### 2026-09-09 — Financials + SEC Yahoo Level
- **2b7da9f** `financials+SEC Yahoo level` — Data was rich (47-row income, 68-row balance, quarterly, 8 SEC filings) but rendering was thin. Dashboard FINANCIALS tab rebuilt: curated Yahoo-order rows (Revenue first, not Tax Effects), `$B/$M` formatting, red negatives, YoY column, Annual/Quarterly toggle (`q_financials` etc.), `stmt-note` provenance line (`app/static/js/dashboard.js:155`, `app/templates/dashboard.html:153`). Filings intel page rebuilt: parallel intel+stock fetch, XBRL company-facts panel (revenue/NI/assets/equity/OCF/EPS w/ form+filed), form badges (10-K/10-Q/8-K), OPEN doc links, watch-forms, red-flags side (`app/static/js/intel_pages.js:52`). Verification: `/dashboard/CRM` 200 has freq-toggle, `/filings` 200, `/api/stock/CRM/financials` 47 rows, live filings tape 8 docs.

### 2026-09-09 — Context Timeline (This File)


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
| 2026-09-08 | muse-spark-1.2 | Context timeline creation | ddd93b8 | docs/PROJECT_TIMELINE.md + mirror |
| 2026-09-09 | muse-spark-1.3 | A-Z overhaul plan (4-subagent audit) | no commit | audit reports |
| 2026-09-09 | muse-spark-1.3 | Phase 0 triage commit | 279765b | 62 files, local_db migration |
| 2026-09-09 | muse-spark-1.3 | Phase A backend reliability | 9afb935 | app/server.py, terminal_commands.py, intelligence_terminal.py |
| 2026-09-09 | muse-spark-1.3 | Phase B frontend fixes | 1d37f5a | compare.html, intel_page.html, guide.html, index.html, terminal_shell.js, pro_pages.js, dashboard_new.css |
| 2026-09-09 | muse-spark-1.3 | Phase C data/AI/Notion | d2ce9f3 | app/config.py, ai_engine.py, data_fetcher.py, notion_integrator.py |
| 2026-09-09 | muse-spark-1.3 | Phase D infra/tests/docs | ecaa00b | .gitignore, requirements-dev.txt, pytest.ini, start/kill cmds, TEST_INFRA.md |
| 2026-09-09 | muse-spark-1.3 | Financials+SEC Yahoo level | 2b7da9f | dashboard.js/html, intel_pages.js |

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
