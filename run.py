import sys

import uvicorn
import logging
import yaml
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from utils.dummy_logger import DummyLogger

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
LOG_ROOT = "logs"
os.makedirs(LOG_ROOT, exist_ok=True)

log_config = config.get("logging", {})
module_config = log_config.get("modules", {})
global_level = getattr(logging, log_config.get("level", "INFO").upper(), logging.INFO)


def create_logger(name: str, subfolder: str, level=logging.INFO, enabled=True):
    if not enabled:
        return DummyLogger()

    folder = os.path.join(LOG_ROOT, subfolder)
    os.makedirs(folder, exist_ok=True)
    logfile = os.path.join(folder, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    handler = TimedRotatingFileHandler(
        logfile,
        when="midnight",
        backupCount=log_config.get("keep_days", 7),
        encoding="utf-8",
        utc=False
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.addHandler(console)
    return logger


app_logger = create_logger("App", "app", level=global_level, enabled=module_config.get("app", {}).get("enabled", True))
bambu_logger = create_logger("Bambu", "bambu", level=global_level, enabled=module_config.get("bambu", {}).get("enabled", True))
error_logger = create_logger("Error", "errors", level=logging.ERROR, enabled=module_config.get("errors", {}).get("enabled", True))
klipper_logger = create_logger("Klipper", "klipper", level=global_level, enabled=module_config.get("klipper", {}).get("enabled", False))


def create_mqtt_logger():
    folder = os.path.join(LOG_ROOT, "3d_drucker")
    os.makedirs(folder, exist_ok=True)
    logfile = os.path.join(folder, "3d_drucker.log")
    max_size_mb = log_config.get("max_size_mb", 10)
    backup_count = log_config.get("backup_count", 3)
    handler = RotatingFileHandler(
        logfile,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s | %(message)s")
    handler.setFormatter(formatter)
    logger = logging.getLogger("3D_drucker")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger


mqtt_logger = create_mqtt_logger()

app_logger.info("FilamentHub Logging-System initialisiert.")
app_logger.info(f"Aktive Log-Module: {module_config}")


# Development reload is CLI-only to keep Windows start stable:
# uvicorn app.main:app --reload --port 8085
def start():
    host, port = get_server_bind(config)
    app_logger.info(f"Starting FilamentHub on {host}:{port} (reload disabled)")
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=False,
            log_level="info",
            loop="asyncio",
            ws="websockets"
        )
    except OSError as exc:
        if exc.errno in (98, 10048):
            app_logger.error(f"Port {port} already in use. Set PORT env to a free port or stop the other process.")
            return
        raise


if __name__ == "__main__":
    start()
