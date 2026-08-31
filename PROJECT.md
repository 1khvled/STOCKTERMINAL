# Project: Stock Terminal AI Polish

## Architecture
- Backend: Flask Server (app/server.py), AI Engine (app/ai_engine.py), Data Fetcher (app/data_fetcher.py)
- Frontend: HTML/CSS/JS in app/templates and app/static
- Database/Artifacts: JSON and Excel models generated from app/excel_generator.py etc.
- External Integrations: Notion, Yahoo Finance, AI API (assumed based on context).

## Code Layout
- `app/`
  - `server.py`: Flask entrypoint.
  - `ai_engine.py`, `data_fetcher.py`, etc.: Backend logical components.
  - `templates/`: HTML templates.
  - `static/css/`, `static/js/`: Frontend assets.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Frontend UI/UX | Fix CSS visual glitches, JS errors (zero syntax/runtime errors on dashboard), graceful handling of missing data ("undefined"). Ensure all 8 tabs work perfectly. | none | IN_PROGRESS (51cbd6f2-40b0-4bdf-86a2-054d7867b459) |
| 2 | Backend Reliability | Robustness of the AI pipeline and Data Fetcher. Graceful degradation on API rate limits/failures. Prevent unhandled exceptions during compilation (e.g. for AAPL). | none | IN_PROGRESS (b4286bf5-3211-4bdc-9ced-ea9ecac36478) |
| 3 | Final E2E Suite Pass | Pass 100% of E2E test suite (Tiers 1-4). | M1, M2 | PLANNED |
| 4 | Adversarial Hardening | Tier 5 adversarial testing of the application. | M3 | PLANNED |

## Interface Contracts
### Frontend ↔ Backend
- The frontend expects structured JSON or HTML fragments from the backend APIs. 
- The backend must return consistent error responses (e.g., 500/503) instead of crashing, and the frontend must display user-friendly error boundaries/messages.

### Backend ↔ External APIs
- Backend data fetchers must wrap external API calls in try/catch and handle rate-limits (HTTP 429) gracefully, yielding partial results or fallback data instead of bubbling up fatal exceptions.
