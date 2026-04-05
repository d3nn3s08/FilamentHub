import sys
import io
import os

# Set UTF-8 encoding für Windows PowerShell/CMD (verhindert Emoji-Crashes)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.dont_write_bytecode = True
import uvicorn
import logging
import yaml
from app.logging_setup import configure_logging

# Load .env early so environment variables from a .env file are available
# to modules that are imported later (e.g. admin password hash).
try:
    from dotenv import load_dotenv  # type: ignore
    # Force override so values in .env replace any existing OS environment variables.
    load_dotenv(override=True)
except Exception:
    # dotenv not installed or .env missing — continue without failing
    pass


def _ensure_python_multipart_installed() -> None:
    try:
        import multipart  # noqa: F401
    except Exception:
        in_venv = hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix
        hint = (
            "Fehlendes Paket: python-multipart.\n"
            "Installiere es in genau der Python-Umgebung, mit der du startest.\n\n"
            "Empfohlen (Projekt-venv): .\\.venv\\Scripts\\python.exe run.py\n"
            "Oder installiere global: pip install python-multipart\n"
        )
        if in_venv:
            hint += "(Info: Du bist bereits in einer venv, dort fehlt das Paket.)\n"
        else:
            hint += "(Info: Du startest gerade nicht aus der Projekt-venv.)\n"

        print(hint, file=sys.stderr)
        raise SystemExit(1)


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_server_bind(cfg):
    host = os.getenv("HOST") or cfg.get("server", {}).get("host") or "0.0.0.0"
    port_val = os.getenv("PORT") or cfg.get("server", {}).get("port") or 8085
    try:
        port = int(port_val)
    except (TypeError, ValueError):
        port = 8085
    return host, port


_ensure_python_multipart_installed()

config = load_config()

# ---------------------------------------------------------
# LOGGING SYSTEM
# ---------------------------------------------------------
log_config = config.get("logging", {})
configure_logging(log_config)

app_logger = logging.getLogger("app")
bambu_logger = logging.getLogger("bambu")
error_logger = logging.getLogger("errors")
klipper_logger = logging.getLogger("services")
mqtt_logger = logging.getLogger("mqtt")

app_logger.info("FilamentHub Logging-System initialisiert.")
app_logger.info("Aktive Log-Module: %s", log_config.get("modules", {}))
# Register a minimal health endpoint so external systems can verify readiness
# Note: Health router registration happens during app startup via include_router in main.py
# We don't import app.main here to avoid potential circular import issues


# Development reload is CLI-only to keep Windows start stable:
# uvicorn app.main:app --reload --port 8085
def start():
    host, port = get_server_bind(config)
    app_logger.info(f"Starting FilamentHub on {host}:{port}")
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=False,  # Auto-reload deaktiviert für stabiles Shutdown
            log_level="info",
            loop="asyncio",
            ws="websockets",
            timeout_graceful_shutdown=5,  # Max 5s warten beim Shutdown, dann force-close
        )
    except OSError as exc:
        if exc.errno in (98, 10048):
            app_logger.error(f"Port {port} already in use. Set PORT env to a free port or stop the other process.")
            return
        raise


if __name__ == "__main__":
    start()


