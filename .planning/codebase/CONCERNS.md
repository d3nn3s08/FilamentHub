# Concerns

## Architectural Risks
- `app/main.py` is very large and owns too many responsibilities: app creation, routing, startup, shutdown, page rendering, and operational logic. This makes changes high-risk and hard to test.
- `app/services/mqtt_runtime.py` is a large global-state module with many responsibilities: connection lifecycle, logging, message buffering, AMS sync, and job tracking. That concentration is fragile.
- The split between `services/` and `app/services/` suggests historical layering drift and makes code ownership ambiguous.

## Quality and Maintenance Risks
- There are no committed automated tests detected despite `pytest` and coverage support being installed.
- Source directories contain backup and temporary files, including `frontend/templates/*.bak*`, `frontend/static/spools.js.bak*`, and `app/routes/printers.py.tmp`. This increases review noise and the chance of stale logic being mistaken for active source.
- Several route modules are large and mix orchestration, DB access, and business rules directly. `app/routes/bambu_cloud_routes.py` and `app/routes/printers.py` are prominent examples.

## Security and Secret Handling
- `.env` is present in the repo root. Even if values are local-only, tracked environment files are an operational risk and should be treated carefully.
- `app/main.py` contains an explicit note that `database_router` was disabled due to critical SQL injection vulnerabilities. That is a strong indicator of prior security debt in admin/debug surfaces.
- Token encryption uses `cryptography` but the dependency was not visible in `requirements.txt` during this scan, which could produce environment drift.

## Operational Risks
- Startup does a lot of work synchronously: migrations, seed data, scheduler start, auto-connect, and reconnect setup. Failures in those paths can affect app availability.
- Deployment depends on Docker host networking for scanner functionality, which reduces portability and may complicate user environments.
- Heavy use of broad exception handling may hide failures until runtime symptoms appear.

## Product/Behavior Risks
- Cloud and LAN printer support are both active, with overlapping concepts like live state, AMS sync, and job tracking. Regressions are likely when changing shared printer state.
- In-memory runtime stores such as `app/services/live_state.py` and `services/printer_service.py` can lose state on restart and complicate reasoning about recovery behavior.
- Some TODO markers remain in live routes and frontend files, for example sync status tracking in `app/routes/bambu_cloud_routes.py` and auth/user attribution in `app/routes/weight_management_routes.py`.

## Recommended Refactor Targets
- Break `app/main.py` into app factory, startup/shutdown orchestration, router registration, and page routes.
- Split `app/services/mqtt_runtime.py` into connection management, metrics/logging, and message-processing units.
- Remove backup/temp artifacts from tracked source directories.
- Add a minimal pytest suite around models, DB bootstrap, and the most business-critical routes before further feature expansion.
