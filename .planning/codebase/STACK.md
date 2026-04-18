# Stack

## Runtime
- Primary language: Python 3.12 in Docker via `Dockerfile`, with README badges/documentation also referencing Python 3.13 for local use.
- Web framework: FastAPI application bootstrapped in `run.py` and `app/main.py`.
- ASGI server: `uvicorn` with `websockets` transport configured in `run.py`.
- ORM/data layer: `sqlmodel` on top of SQLAlchemy in `app/database.py` and `app/db/session.py`.
- Templating: Jinja2 templates under `frontend/templates/` and `app/templates/`.
- Frontend delivery model: server-rendered HTML plus vanilla JS/CSS in `frontend/static/` and `app/static/`.

## Persistence
- Database: SQLite file configured through `FILAMENTHUB_DB_PATH` in `app/database.py`.
- Schema management: Alembic with migration history in `alembic/versions/`.
- Startup migration flow: `init_db()` runs migrations and schema verification on app boot in `app/database.py`.
- Runtime storage folders: `data/` for DB and app state, `logs/` for log output, plus `app/static/uploads/printers/` for printer images.

## Dependencies
- HTTP/API stack: `fastapi`, `uvicorn[standard]`, `httpx`, `aiohttp`, `requests`, `websockets`, `wsproto`.
- Data/config: `sqlmodel`, `alembic`, `pyyaml`, `python-dotenv`, `python-multipart`.
- Messaging/device integration: `paho-mqtt`, `paramiko`.
- Security/auth: `bcrypt`, `cryptography` usage in `app/services/token_encryption.py` even though it is not pinned in `requirements.txt`.
- Testing packages present: `pytest`, `pytest-cov`.

## Configuration
- Environment variables live in `.env` and `.env.example`.
- YAML config lives in `config.yaml` and controls logging, integration mode, server port, and MQTT logging.
- Docker settings are split across `Dockerfile`, `docker-compose.yml`, and `entrypoint.sh`.
- App versioning is surfaced through `VERSION`, `.env`, and template globals in `app/main.py`.

## Frontend Tech
- Main UI: Jinja pages such as `frontend/templates/dashboard.html`, `frontend/templates/printers.html`, and `frontend/templates/settings.html`.
- Client scripts: page-level JS like `frontend/static/js/dashboard.js`, `frontend/static/js/printers.js`, `frontend/static/js/settings.js`.
- Styling: shared and page-specific CSS under `frontend/static/css/` and `frontend/static/`.
- Small React island: `frontend/react/components/PrintProgressCard.jsx` and `frontend/react/containers/ActiveJobsPanel.jsx`.

## Logging and Monitoring
- Central logging setup: `app/logging_setup.py` and `app/logging/runtime.py`.
- Runtime/performance monitoring: `app/monitoring/runtime_monitor.py` and `app/services/performance_monitoring.py`.
- MQTT log shaping and smart logging: `app/services/mqtt_runtime.py`.

## Delivery
- Local run entrypoint: `python run.py`.
- Container health endpoint: `/health` from `app/main.py`.
- CI/CD footprint is minimal: `.github/workflows/docker-publish.yml` builds and pushes a Docker image on `beta` branch pushes.
