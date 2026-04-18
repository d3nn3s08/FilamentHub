# Integrations

## Printer Protocols
- Bambu LAN/MQTT is a core integration path, with runtime handling in `app/services/mqtt_runtime.py`, message client code in `app/services/printer_mqtt_client.py`, and route wiring in `app/routes/mqtt_routes.py`.
- Bambu Cloud is implemented through `app/routes/bambu_cloud_routes.py`, `app/services/bambu_cloud_service.py`, `app/services/bambu_auth_service.py`, and `services/cloud_mqtt_client.py`.
- Klipper support exists through route/service adapters such as `services/klipper_service.py`, `services/klipper_polling_service.py`, `app/services/printers/klipper_adapter.py`, and `app/services/printers/klipper_file_adapter.py`.
- Manual or standalone printers are modeled in `app/models/printer.py` and supported in route logic like `app/routes/printers.py`.

## External APIs and Network Dependencies
- Bambu Cloud REST endpoints are called from `app/services/bambu_cloud_service.py` using `aiohttp`.
- Moonraker/Klipper HTTP endpoints are probed in `app/routes/printers.py` and related Klipper services.
- MQTT broker communication for printers uses TLS and device credentials through `paho-mqtt` wrappers.
- FTP/file transfer support appears in `app/services/gcode_ftp_service.py`.
- SSH/SFTP style capability is implied by the `paramiko` dependency, though this scan did not find a dominant adapter using it directly.

## Authentication and Secrets
- Admin enablement depends on `ADMIN_PASSWORD_HASH` loaded in `run.py` and applied through `app/admin.py`.
- Bambu Cloud access and refresh tokens are encrypted before persistence via `app/services/token_encryption.py`.
- Encryption key storage uses either `FILAMENTHUB_ENCRYPTION_KEY` or a generated file at `data/.encryption_key`.
- Docker publish uses GitHub Actions secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` in `.github/workflows/docker-publish.yml`.

## Database and Filesystem Touchpoints
- SQLite is the only database backend currently wired, via `app/database.py` and `alembic.ini`.
- Uploaded printer images are stored under `app/static/uploads/printers/`.
- Coverage history is written to `data/coverage_history.json` by `app/routes/admin_coverage_routes.py`.
- Logs are written to `logs/` and specialized MQTT files defined in `config.yaml`.

## Frontend/Backend Interfaces
- Server-rendered pages fetch JSON APIs from `app/routes/*.py`, for example dashboard calls to `/api/printers/`, `/api/jobs/active`, `/api/live-state/`, and `/api/statistics/heatmap`.
- Log streaming is exposed through `app/websocket/log_stream.py`.
- Version checking endpoints are surfaced through `app/routes/version_routes.py`.

## Integration Risks
- Several integrations depend on local network topology; `docker-compose.yml` explicitly requires `network_mode: host` for scanning.
- Cloud support mixes REST plus MQTT and stores long-lived credentials locally.
- Missing automated tests make integration regressions likely, especially around MQTT, AMS sync, and startup migration behavior.
