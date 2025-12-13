import uvicorn
import logging
import yaml
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from utils.dummy_logger import DummyLogger


# ---------------------------------------------------------
# CONFIG LADEN
# ---------------------------------------------------------
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()


# ---------------------------------------------------------
# LOGGING SYSTEM
# ---------------------------------------------------------

# Basis-Ordner (relative Pfade → funktionieren auf Windows, Pi, Docker)
LOG_ROOT = "logs"

# sicherstellen, dass der Hauptordner existiert
os.makedirs(LOG_ROOT, exist_ok=True)

log_config = config["logging"]
module_config = log_config["modules"]

# global log level
global_level = getattr(logging, log_config["level"].upper(), logging.INFO)



def create_logger(name: str, subfolder: str, level=logging.INFO, enabled=True):
    """
    Erzeugt einen Logger mit Tagesrotation.
    Falls disabled → DummyLogger.
    """
    if not enabled:
        return DummyLogger()

    folder = os.path.join(LOG_ROOT, subfolder)
    os.makedirs(folder, exist_ok=True)

    logfile = os.path.join(folder, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    handler = TimedRotatingFileHandler(
        logfile,
        when="midnight",
        backupCount=log_config["keep_days"],
        encoding="utf-8",
        utc=False
    )

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    logger.addHandler(handler)
    logger.addHandler(console)

    return logger


# ---------------------------------------------------------
# MODULE-LOGGER ANLEGEN
# ---------------------------------------------------------

app_logger = create_logger(
    "App",
    "app",
    level=global_level,
    enabled=module_config["app"]["enabled"]
)

bambu_logger = create_logger(
    "Bambu",
    "bambu",
    level=global_level,
    enabled=module_config["bambu"]["enabled"]
)

klipper_logger = create_logger(
    "Klipper",
    "klipper",
    level=global_level,
    enabled=module_config["klipper"]["enabled"]
)

error_logger = create_logger(
    "Error",
    "errors",
    level=logging.ERROR,
    enabled=module_config["errors"]["enabled"]
)

# MQTT Logger mit Größenbegrenzung (aus config.yaml)
def create_mqtt_logger():
    """Erstellt einen Logger für MQTT-Nachrichten mit Rotation nach Größe."""
    folder = os.path.join(LOG_ROOT, "mqtt")
    os.makedirs(folder, exist_ok=True)
    
    logfile = os.path.join(folder, "mqtt_messages.log")
    
    # Lese Konfiguration aus config.yaml
    max_size_mb = log_config.get("max_size_mb", 10)
    backup_count = log_config.get("backup_count", 3)
    
    # RotatingFileHandler mit konfigurierbarer Größe
    handler = RotatingFileHandler(
        logfile,
        maxBytes=max_size_mb * 1024 * 1024,  # MB zu Bytes
        backupCount=backup_count,
        encoding="utf-8"
    )
    
    formatter = logging.Formatter("%(asctime)s | %(message)s")
    handler.setFormatter(formatter)
    
    logger = logging.getLogger("MQTT")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    return logger

mqtt_logger = create_mqtt_logger()

app_logger.info("FilamentHub Logging-System initialisiert.")
app_logger.info(f"Aktive Log-Module: {module_config}")


# ---------------------------------------------------------
# SERVER START
# ---------------------------------------------------------

def start():
    app_logger.info("Starte FilamentHub API Server...")

    uvicorn.run(
        "app.main:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
        reload=True,
    )


if __name__ == "__main__":
    start()
