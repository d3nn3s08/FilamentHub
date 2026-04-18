# Testing

## Current State
- `requirements.txt` includes `pytest` and `pytest-cov`.
- `app/routes/admin_coverage_routes.py` can run `pytest --cov=app --cov-report=html` from within the application when `FILAMENTHUB_DEV_FEATURES=1`.
- This scan did not find committed test files under the repository using common names such as `test_*.py`, `*_test.py`, `*.test.js`, or `*.spec.js`.
- The project therefore appears to have test tooling installed but little or no checked-in automated test coverage.

## Existing Verification Paths
- Startup validation is partly operational rather than test-based: `app/database.py` runs migrations and verifies critical schema fields at boot.
- Health endpoints `/ping` and `/health` in `app/main.py` provide runtime readiness checks.
- Docker publishing workflow in `.github/workflows/docker-publish.yml` builds and pushes images, but does not run linting or tests.
- Coverage history/report serving exists, which suggests ad hoc local validation, but not a formal CI test gate.

## High-Risk Areas Lacking Test Protection
- Migration and schema-compatibility logic in `app/database.py`.
- MQTT runtime connection handling and message processing in `app/services/mqtt_runtime.py`.
- AMS parsing and synchronization in `app/services/ams_parser.py`, `app/services/ams_sync.py`, and related routes.
- Job tracking and printer/cloud reconciliation paths in `app/services/job_tracking_service.py` and `app/services/bambu_cloud_service.py`.
- Route-level business logic in large handlers such as `app/routes/printers.py` and `app/routes/bambu_cloud_routes.py`.

## Implied Testing Strategy
- Manual browser and device validation is likely the dominant quality loop.
- Coverage seems intended for local developer inspection rather than enforced metrics.
- The code shape would support targeted pytest tests around route handlers, schema validators, and pure helper services first.

## Useful First Tests
- Model/schema validation tests for `app/models/spool.py` and `app/models/printer.py`.
- Integration-style DB tests for `init_db()` and selected Alembic migration expectations.
- Route tests for printer CRUD and Bambu Cloud config endpoints using FastAPI test clients.
- Service tests around live-state merge behavior in `app/services/live_state.py` and token encryption round trips in `app/services/token_encryption.py`.
