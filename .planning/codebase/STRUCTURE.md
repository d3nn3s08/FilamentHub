# Structure

## Root Layout
- `app/`: primary backend package containing routes, models, services, monitoring, websocket support, templates, and static assets.
- `services/`: older or shared service modules, especially printer/cloud/Klipper related runtime helpers.
- `frontend/`: server-rendered UI assets including templates, CSS, JS, and a small `react/` subtree.
- `alembic/`: migration environment and versioned schema changes.
- `data/`: runtime state and SQLite database location in local setups.
- `logs/`: application and MQTT logs.
- `utils/`: small helper scripts such as `utils/dummy_logger.py`.
- `ANLEITUNG/`: documentation and HTML manual artifacts.

## Backend Substructure
- `app/routes/`: domain routers such as `printers.py`, `jobs.py`, `bambu_cloud_routes.py`, `settings_routes.py`, `monitoring_routes.py`, and various debug/admin routes.
- `app/models/`: SQLModel and Pydantic schema definitions such as `printer.py`, `spool.py`, `job.py`, `settings.py`, `weight_history.py`, `bambu_cloud_config.py`, and conflict models.
- `app/services/`: domain logic for AMS parsing/sync, cloud auth, runtime MQTT, job tracking, token encryption, ETA logic, and reconciliation.
- `app/services/printers/`: printer-family-specific adapters, currently Klipper oriented.
- `app/monitoring/`: request/runtime monitoring.
- `app/websocket/`: log stream websocket support.
- `app/static/` and `app/templates/`: app-local assets for debug/logs/admin style pages.

## Frontend Substructure
- `frontend/templates/`: page templates such as `dashboard.html`, `printers.html`, `spools.html`, `settings.html`, `monitoring.html`, and admin pages.
- `frontend/static/js/`: page controllers such as `dashboard.js`, `jobs.js`, `printers.js`, `settings.js`, and conflict listeners.
- `frontend/static/css/`: main shared styles and page-level styles.
- `frontend/react/`: limited React components at `components/PrintProgressCard.jsx` and `containers/ActiveJobsPanel.jsx`.

## Naming and Organization Notes
- Route files follow `*_routes.py` or domain-name patterns, but not perfectly consistently, for example `jobs.py`, `materials.py`, `printers.py`.
- The codebase contains backup and temporary files in tracked source directories, such as `frontend/templates/*.bak*`, `frontend/static/spools.js.bak*`, and `app/routes/printers.py.tmp`.
- There is duplication between `app/templates/layout.html` and `frontend/templates/layout.html`, and both `app/static/` and `frontend/static/` are mounted.
- Legacy/transition boundaries are visible in the split between `services/` and `app/services/`.

## Operational Files
- `requirements.txt`: Python dependency manifest.
- `config.yaml`: app configuration.
- `.env` and `.env.example`: environment configuration.
- `docker-compose.yml` and `Dockerfile`: deployment setup.
- `.github/workflows/docker-publish.yml`: image publishing workflow.
- `README.md`, `CHANGELOG.md`, `CLAUDE.md`: project/operator docs.
