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

### 2026-09-09 — Financials Yahoo Stats Block
- **be9c106** `financials Yahoo stats` — Added Key Statistics grid (Valuation: mcap/EV/P/E fwd/PEG/P/S/P/B/EV; Profitability: margins/ROE/ROA; Balance: cash/debt/D-E/current/quick/book; Cash flow: OCF/FCF/EBITDA/dividend; Price history: beta/52W/consensus; Shares: out/insiders/short/analysts), peer P/E compare table (you vs 5 peers vs 5Y median), growth rates (revenue/earnings/quarterly) + revenue-vs-net-income bar chart (`app/static/js/dashboard.js` renderFinExtra, `app/templates/dashboard.html` panel-financials). Verification: `/dashboard/CRM` 200 has keystats/pe-compare/revChart, all helpers present.

### 2026-09-09 — Financials Mega (Dividends/Earnings/Peers)
- **b0df0c9** `financials mega` — New `GET /api/stock/<t>/dividends` (live yfinance history: yearly totals, recent payouts, frequency + local yield/rate/payout) and `GET /api/peers/sector/<t>` (sector P/E median + mates from local catalog, no LLM). Dashboard: Dividends card + annual bars (CRM: quarterly, $1.76 rate), Analyst Target range bar (low-mean-high + price/mean markers, 54 analysts for CRM), Quarterly Earnings Trend chart (revenue bars + NI/EPS lines), full peers table (margin/growth cols, best/worst highlight) + P/E bar chart + sector median row (Tech 25 tracked, median 42.3x), 50/200D MA filled from weekly compact. Verification: DIV/SECTOR/DASH all 200 live.

### 2026-09-09 — Compare Page Rebuild (was 100% broken)
- **6f34200** `compare rebuild` — Root cause: JS read `data.results`/`data.status`, API sends `{stocks}` → page ALWAYS error-toasted, plus purple PREMIUM theme + `dY"` mojibake buttons + hand-drawn canvas radar. Rebuilt dashboard-native (green StockerAI, `dashboard_new.css`): ticker chips + add/remove (max 6) + URL sync, grouped matrix (Valuation/Multiples incl. live trail+fwd P/E via `/api/stock` enrich/Quality+Growth/Risk) with green winner-highlight per row, Chart.js quality radar (normalized), fair-vs-price bars, missing-ticker chips with hub guidance, showToast guard. Verification: `/compare?tickers=AAPL,MSFT,CRM` 200, no PREMIUM, radar present.

### 2026-09-09 — Yahoo Gaps Batch (Options/Insiders/Holders/Earnings/ESG/Movers)
- **7383882** `yahoo gaps batch` — New endpoints: `/api/stock/<t>/insiders` (live top-15, schema-proof, Start-Date fix), `/holders` (institutions/funds/major), `/earnings` (calendar + surprise history), `/esg` (scores or empty), `/api/market/movers` (live gainers/losers/actives across catalog). New FLOWS tab (options put/call+IV read, earnings surprise table, insiders table, holders, ESG bars). Screener +4 criteria (ROA/rev-growth/op-margin/current-ratio, backend + UI wired). Hub movers upgraded to 3-way split (append-only script). Fixed NaN closes (dropna, was breaking JSON.parse) in live-quotes + movers. Skipped per user: daily OHLCV history, transcripts. Verification: all endpoints 200 live (insiders Conway/Harris sales, Vanguard holders, CRM earnings 2026-12-02, movers no NaN).

### 2026-09-09 — UI Batch (Freshness/Jump/Shortcuts/Deeplinks)
- **38aa059** `UI batch` — Stale-data banner (age from `generated_at`, shows at 85d+) with one-click SSE re-analyze + auto-reload; ticker jump box in dashboard nav (`/` focuses it anywhere); number keys 1-8 switch tabs; URL hash deep-links (`#financials` shareable, back-button safe, `aria-current` kept); compare COPY LINK button (URL already synced). Also repaired a mid-edit regex cut that nested the copylink handler inside clear. Verification: served HTML contains stale/jump/hash (disk grep + live 200).

### 2026-09-09 — Fiscal.ai Copy (Ratios + Facts)
- **7f292ce** `fiscal.ai copy` — Read fiscal.ai dashboard + MSFT overview (tab structure, stats grid sections). Copied what our data supports: new `GET /api/stock/<t>/profile` (live officers/website/employees; CRM: Benioff/Washington/Harris), new RATIOS tab (button + panel, keys 1-9 updated) with Company Facts box (name/sector/website/leadership) and 8-section stats grid: Profile, Margins, Returns-avg (ROA/ROE/ROIC from annual statements), Valuation TTM (+P/FCF, EV/GP), Valuation NTM (target/fwd P-E/PEG), Health (+EBIT/interest coverage), Growth CAGR (3Y/span rev+EPS+FCF + fwd), Dividends. Skipped: Segments/KPIs + Research tabs (no data source). Verification: PROFILE 200 live officers, dashboard has ratios tab + ratio-grid + fact-box.

### 2026-09-09 — Macro Fundamentals x4 Subagents
- **a4a96b9** `macro fundamentals x4 agents` — 4 parallel agents with strict file ownership: (1) data created `app/macro_fetcher.py` (yfinance-only: ^IRX/^FVX/^TNX/^TYX curve, VIX/DXY/gold/oil/HYG/TLT, Fed heuristic labeled NOT-FOMC, regime scorer, 1h atomic cache, TEST_MODE mocks); (2) AI appended `SYSTEM_PROMPT_MACRO` + `get_macro_impact` with sector-bucket rules fallback to `app/ai_engine.py` (+232/-0); (3) UI created `app/templates/macro.html` + `app/static/js/macro.js` (regime banner, curve chart, gauges, ticker impact, ?ticker= link) + nav links; (4) QA verified all 12 Yahoo symbols LIVE + wrote `tests/e2e/test_macro.py` (10 cases). I wired 5 routes (`/macro`, `/api/macro/snapshot|yields|regime`, `/api/intel/macro/<t>` with dict normalization) + fixed `macro.js` [object Object] dict rendering. Reconciled 3 contract dialects (fetcher keys vs page keys vs test keys) in the route adapters. Verification: live TIGHTENING regime, real yields, AAPL macro intel 200.
- **conftest PIPE deadlock (same commit)** — Full suite hung mid-run (ReadTimeout cascade): `stdout=PIPE` never drained. Fixed to temp-file logging + kill fallback. Result: **39 passed in 10.22s** (was: 23 failed). Also fixed macro test 400-vs-404 for multi-segment payloads (repo convention).
- **4a3a8fb** `notion reader` — NOTION RESEARCH tab upgraded from raw HTML dump: auto-TOC from h2s with smooth scroll, in-doc search (300-mark cap, Enter=next, `mark.cur` highlight), doc stats (sections/words/tables), full `.statement-table` styling (sticky thead, zebra, hover) + missing block styles (indented/todo/details/hr/img/callout). (Note: CSS+HTML chrome rode in a4a96b9, JS helpers in 4a3a8fb — content complete across both.)

### 2026-09-09 — Macro Perf x5 (Groq-First, Regime, Speed, 15s Hub)
- **c1c946b** `macro perf x5` — (1) GROQ WORKS + FIRST: chain order was OpenCode->OpenRouter->Anthropic->Groq so Groq never fired; moved Groq primary w/ key rotation + browser UA (0.9s answers, verified `'{'ok': True'}'`). (2) REGIME FIXED: RISK_ON-into-TIGHTENING was nonsense; added Fed cap + oil>=85 stagflation overlay + fed in inputs (now STAGFLATION_WATCH with vote trail). (3) SPEED: 5 agents — macro.html skeletons/countdown/hierarchy, macro.js parallel+abort+stale-while-revalidate+countdown, macro_fetcher ThreadPoolExecutor (forced 8.4s->2.8s, cached 0.006s), CSS banner/gauge art, holdings widget + perf tests. I wired: concurrent live-quotes/movers helper (5.2s->3.1s cold, 0.15s cached; 8.7s->1.2s), hub poll 30s->15s + cache 15s, macro_holdings card+script. Fixed NaN-close JSON breakage + insiders date. Verification: 43 passed (39+4 perf), live quotes yfinance, movers no NaN.

### 2026-09-09 — OpenCode Muse Spark 1.3 (Subagent)
- **cff32e4** `opencode muse-spark-1.3 primary` — User supplied new Zen key (stored ONLY in gitignored `.env`, never in repo/logs; leak scan clean). Subagent probed live: `GET /zen/v1/models` = 70 ids; verified id **`muse-spark-1.3`** (recognized; stale ids `north-mini-code-free`, `muse-spark-1.3-free`, `opencode/...` all 401 ModelError). Thinking `reasoning_effort` medium|high accepted (no 400s); default **medium**, env-overridable to high. Wired: `OPENCODE_MODEL` default + `OPENCODE_REASONING_EFFORT`/`OPENCODE_TIMEOUT` in config, thinking + json_object + Mozilla UA (endpoint 403s urllib UA) in ai_engine OpenCode route; Groq stays fallback. Mock e2e proves payload + parsing; collect 43 unchanged. HONEST CAVEAT: live 200 not obtainable today — paid id needs workspace payment method (401 CreditsError), free-tier id backend-500s. Add billing and OpenCode answers for real; Groq serves live meanwhile.

### 2026-09-09 — OpenCode Free Tier (Probed 12x, Default Switched)
- **4901a6c** `opencode free tier default` — User demanded the free model. Probed `muse-spark-1.3-contributor-free` 12 ways (minimal/json/temp+tokens/full/referer/sys-prompt/alt-UAs/retries + 1.2-contributor-free): ALL 500 Internal Server Error - their backend is down for these ids, not our payload. Switched default to contributor-free anyway: chain tries free first, auto-falls-back to Groq on 500 (proven: full chain returns parsed JSON in 1.0s). The day OpenCode fixes their backend, free answers flow with zero code change. Groq gpt-oss-120b keeps serving live meanwhile.

### 2026-09-09 — Routing Groq-Easy/Muse-Hard + MU Live Fix
- **4d2a5d8** `routing groq-easy/muse-hard + live-all-catalog` — `_call_llm(route=)`: easy = Groq first (screener parser); hard (default) = Muse Spark first (fundamentals, red-team, macro, intel, notion); `_call_groq` forwards route. Tagged: screener=easy; fundamentals x2, red-team, macro-impact, intel helper, notion=hards. Fixed my own indent break in the reorder before commit (verified compile + easy 1.4s / hard 3.6s both parsed). MU $956 mystery solved: price CORRECT (live $1000.26, Micron really is 1k) - the bug was live coverage: default tickers were first-25-alphabetical so MU never got quotes (stale price + `--` day). Now defaults cover all 39, hub upside computes vs LIVE price, hub+dashboard poll every 15s. Verification: default live-quotes 40 quotes MU yfinance $1000.26.

### 2026-09-09 — Live-Everywhere Fix (All Static Prices)
- **a6b6e1d** `live-everywhere fix` — User: every price static, not just MU. Found: hub loop had undeclared `liveMap` (implicit global), one giant try/catch (any section failure killed price+day+label together), no fetch timeout, and API responses cacheable by browsers. Fixed: declared liveMap, per-section isolation (quotes/tape/movers/render/label fail independently), 12s AbortController, `cache:"no-store"` fetches + server `after_request` no-store on all `/api/*`, offline label instead of silent stale. Also bumped perf-test timeouts 5s->25s to match their own <25s asserts after one load-flake. Verification: 43 passed, MU live $1000.26 yfinance, no-store header present.

### 2026-09-09 — Stuck-Loading Fix + Port Discipline
- **cbb8922** `stuck-loading fix` — FIG page stuck on Loading: record complete + API fast (0.2s), so failure was fetch/render-side with no timeout and weak error surfacing. Fixed: unknown tickers 302-redirect to hub auto-analyze (`/?ticker=X`, no more dead template), 25s AbortController on dashboard fetch, `window.onerror` toast banner, `kill_server.cmd` scoped to `*STOCK_TERMINAL_ALONE*` paths. Test updated to redirect contract (43 green: 42+1 fixed). PORT RULE (user order): restarts touch ONLY the 5001 listener owned by our venv cmdline - never blanket-kill python, never touch 8085/8086/8087. Found venv launcher spawns a same-cmdline worker child (both PIDs match filter; listener socket decides). Verification: ZZZZQ 302 -> /?ticker=ZZZZQ, FIG 200, single listener.

### 2026-09-09 — All-Dashboards Stuck Loading (One Missing Paren)
- **b23307c** `fix all-dashboards stuck loading` — Follow-up: stuck loading hit EVERY ticker, not just FIG. Proved via headless chromium console capture: `PAGEERROR: missing ) after argument list`, zero failed requests. Root cause: dropped `)` in earnings-trend chart datasets (`:[]}` instead of `:[])}`) killed the whole 856-line script at parse time. Fixed (1 char), masked-esprima parse now SYNTAX OK, FIG+AAPL heroes render with zero console errors. Lesson: JS edits need a parse gate (esprima masked for `?.`/`??`) before commit.

### 2026-09-09 — Frozen Prices Were Browser Cache (Proven Live 40/40)
- **58e3ba0** `no-store on HTML pages` — User still saw static prices while headless-chromium proof showed label `live 40/40`, MU $1000.26 live +4.62% day, upside +54.5% vs live, zero page errors. Root cause: no-store hook covered `/api/*` only; hub/dashboard HTML (inline JS, no versioning) was served from browser cache running the OLD top-25-era code. Extended hook to all `text/html` responses (static assets keep caching). Restart used listener-socket discipline (killed 21596 only). Verification: HUB 200 CC:no-store, 43 passed.

### 2026-09-09 — Research Split (Risks Main + 3 Pages)
- **a948f6f** `research split` — Probed notion keys: 33 tickers have all 5 subpages. RISKS tab now leads with Notion Risk Register HTML as main card (AI factors kept below). New `/research/<ticker>/{briefing,earnings,overview}` standalone pages (one shared template: subpage pills, TOC, search, stats; overview resolves price_review->overview; unknown ticker redirects to hub auto-analyze per rule). Tests: research 200/404/302/400 contract. Verification: 3 CRM pages 200, 27 adversarial green.

### 2026-09-09 — Fake-Numbers Purge x24 (2 Subagents)
- **a92a1af** `fake-numbers purge` — 2 subagents (integrity audit found 24 issues MU/CRM/AAPL-traced; peer intel verified memory universe live). Fixed: TRUE day change (was live-vs-stored drift, MU sign flipped to correct -1.61%); live upside recomputed on dashboard poll + hub avg/pick/movers/compare; 52W 100x scale; HYG/TLT ratio key; 13W spread label; votes-not-/100; always as-of chip (button from 7d); pre-tax dup dropped; MA50/200 (10/40-wk) labels; targets as-of; dividend source row; model-score wording; sector universe-median label; gauge day-change backend+UI; MU/SNDK peers -> Samsung/Hynix/SNDK/WDC/STX (peer `.info` wrapped in retry+sleep, None-not-N/A, refreshed MU+SNDK records on disk); compare live join + radar missing->median. Open: revenueGrowth 345% left as upstream data (not edited); q-stats stored-tag + mktcap-live recompute noted for next pass. Verification: headless chromium MU $1000.26 -1.61% +54.5%, compare MU-vs-SNDK live multiples, 44 green.

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
| 2026-09-09 | muse-spark-1.3 | Financials Yahoo stats | be9c106 | dashboard.js/html |
| 2026-09-09 | muse-spark-1.3 | Financials mega div/earn/peers | b0df0c9 | server.py, dashboard.js/html |
| 2026-09-09 | muse-spark-1.3 | Compare rebuild | 6f34200 | compare.html |
| 2026-09-09 | muse-spark-1.3 | Yahoo gaps batch | 7383882 | server.py, dashboard.js/html, index.html, screener.html |
| 2026-09-09 | muse-spark-1.3 | UI batch freshness/jump/keys | 38aa059 | dashboard.js/html, compare.html |
| 2026-09-09 | muse-spark-1.3 | Fiscal.ai ratios copy | 7f292ce | server.py, dashboard.js/html |
| 2026-09-09 | 4 subagents + lead | Macro fundamentals + notion reader | a4a96b9, 4a3a8fb | macro_fetcher.py, ai_engine.py, server.py, macro.html/js, notion reader, conftest, test_macro.py |
| 2026-09-09 | 5 subagents + lead | Macro perf x5 | c1c946b | ai_engine.py, macro_fetcher.py, server.py, macro.html/js/css/holdings, index.html, test_perf.py |
| 2026-09-09 | subagent + lead | OpenCode Muse Spark 1.3 | cff32e4 | config.py, ai_engine.py (key in .env only) |
| 2026-09-09 | lead | OpenCode free-tier default | 4901a6c | config.py |
| 2026-09-09 | lead | Routing + MU live fix | 4d2a5d8 | ai_engine.py, server.py, index.html, dashboard.js, intel/notion |
| 2026-09-09 | lead | Live-everywhere hardening | a6b6e1d | server.py, index.html, test_perf.py |
| 2026-09-09 | lead | Stuck-loading + ports | cbb8922 | server.py, dashboard.js, kill_server.cmd, test_adversarial.py |
| 2026-09-09 | lead | All-dashboards paren fix | b23307c | dashboard.js |
| 2026-09-09 | lead | HTML no-store vs cache | 58e3ba0 | server.py |
| 2026-09-09 | lead | Research split pages | a948f6f | server.py, research.html, dashboard.js/html, test_adversarial.py |
| 2026-09-09 | 2 subagents + lead | Fake-numbers purge x24 | a92a1af | data/macro_fetcher, dashboard.js, macro.js, compare.html, index.html |

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
