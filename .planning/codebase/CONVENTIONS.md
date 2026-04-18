# Conventions

## Language and Style
- Python code mixes German and English naming/comments. Public API details and operator messaging are often German, while framework/library names remain English.
- Type hints are used often but not uniformly. Representative typed files include `services/printer_service.py`, `app/services/bambu_cloud_service.py`, and model schemas in `app/models/`.
- Logging is preferred over raising in many runtime paths, especially network and background-task code.
- Inline comments are frequent and often explain operational history or bug fixes, for example the shutdown and security notes in `app/main.py`.

## Route Patterns
- Routes commonly use `APIRouter(prefix=..., tags=[...])` and `Depends(get_session)` for DB access.
- Route handlers often contain domain logic directly instead of delegating to thin services only; `app/routes/printers.py` is a clear example.
- Response models are used in many places but not all endpoints are strongly normalized.

## Model and Schema Patterns
- SQLModel table classes usually inherit from a `*Base` class, with separate read/create/update schemas where needed.
- IDs are UUID strings via `uuid4()` rather than integer autoincrement keys.
- Pydantic validators normalize permissive inputs, especially in `app/models/spool.py`.

## Runtime Patterns
- Global mutable singleton state is a recurring pattern in `app/services/mqtt_runtime.py`, `services/printer_service.py`, and `app/services/live_state.py`.
- Startup logic is centralized in the FastAPI lifespan rather than external workers/process managers.
- Defensive `try/except` blocks are common, sometimes broad, to keep the app running during unstable printer or cloud conditions.

## Frontend Patterns
- Templates extend a shared layout and include page-local inline styles or scripts when needed.
- Frontend JS is mostly page-scoped and imperative, using `fetch()` and DOM updates rather than a full SPA structure.
- CSS and JS files are organized by page names, for example `frontend/static/js/dashboard.js` and `frontend/static/css/weight_history.css`.

## Operational Conventions
- The app favors visible operator output during startup, including stdout banners and status prints in `app/database.py` and `run.py`.
- Host networking is treated as a deployment requirement for printer discovery in `docker-compose.yml`.
- Dev-only tooling is guarded with environment checks, for example coverage execution in `app/routes/admin_coverage_routes.py`.

## Notable Inconsistencies
- Mixed asset roots (`app/static` vs `frontend/static`) and template roots (`app/templates` vs `frontend/templates`).
- Mixed service namespaces (`services/` vs `app/services/`) increase ambiguity about ownership.
- Source tree contains backup files and temp files, which weakens the convention boundary between source and artifact.
