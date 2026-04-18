# Architecture

## High-Level Shape
- The application is a monolithic FastAPI server that combines HTML page rendering, JSON APIs, background startup tasks, and device runtime management in one process.
- `run.py` is the operational entrypoint. It loads `.env`, configures logging, validates a required multipart dependency, and launches `uvicorn`.
- `app/main.py` owns the application composition: FastAPI app creation, startup/shutdown lifecycle, router registration, template setup, static mounts, middleware, and page routes.

## Main Layers
- Presentation layer: Jinja templates in `frontend/templates/` and `app/templates/`, plus static JS/CSS in `frontend/static/` and `app/static/`.
- API layer: route modules under `app/routes/` grouped by domain such as printers, jobs, AMS, settings, cloud sync, admin, debug, and monitoring.
- Domain/service layer: business logic in `app/services/`, `services/`, and `app/services/printers/`.
- Persistence layer: SQLModel models under `app/models/`, global engine/session helpers in `app/database.py` and `app/db/session.py`, and Alembic migrations in `alembic/`.

## Data Flow
- HTTP requests enter FastAPI in `app/main.py`, then dispatch to `app/routes/*.py`.
- Routes typically depend on `get_session()` from `app/database.py` and call helper services or raw SQLModel logic directly.
- MQTT messages enter through runtime/client code in `app/services/mqtt_runtime.py` and `app/services/printer_mqtt_client.py`, then update in-memory state, AMS synchronization, and job tracking.
- Live printer payloads are cached in the in-memory store in `app/services/live_state.py`.
- UI pages fetch JSON endpoints from browser JS files such as `frontend/static/js/dashboard.js`.

## Startup and Background Work
- FastAPI lifespan in `app/main.py` initializes admin access, migrations, seed data, printer service, scheduler startup, auto-connect, and reconnect loops.
- Shutdown logic in `app/main.py` is heavy and explicit: stop schedulers, signal shutdown flags, disable MQTT callbacks, stop loops, disconnect clients, and release resources.
- Additional recurring cloud sync behavior lives in `app/services/bambu_cloud_scheduler.py`.

## Key Shared State
- Printer connection status is held in-memory by `services/printer_service.py`.
- MQTT runtime maintains global mutable state in `app/services/mqtt_runtime.py` for clients, subscriptions, message buffers, and connection metadata.
- Live-state payload snapshots are kept in the module-level dict in `app/services/live_state.py`.

## Architectural Style
- This is not a layered-clean architecture. It is a pragmatic monolith with route modules often coordinating persistence and domain logic directly.
- There is visible coexistence of legacy and newer code paths, especially across `services/` versus `app/services/`, and template UI versus small React components.
- The codebase relies on startup side effects and module-level singletons rather than dependency-injected service objects.

## Entry Points
- Server bootstrap: `run.py`.
- App composition: `app/main.py`.
- Container bootstrap: `entrypoint.sh`.
- DB migration runtime: `app/database.py` plus `alembic/env.py`.
