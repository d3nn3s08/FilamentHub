from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
import yaml
import os

router = APIRouter(prefix="/api/debug", tags=["Debug & Config"])


# -----------------------------
# MODELS
# -----------------------------
class LogModuleToggle(BaseModel):
    module: str
    enabled: bool


class LogLevelUpdate(BaseModel):
    level: str


class LogRotationUpdate(BaseModel):
    max_size_mb: int
    backup_count: int


# -----------------------------
# CONFIG HELPERS
# -----------------------------
CONFIG_PATH = "config.yaml"


def load_config() -> dict:
    """Lädt die config.yaml"""
    if not os.path.exists(CONFIG_PATH):
        raise HTTPException(status_code=404, detail="config.yaml nicht gefunden")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    """Speichert die config.yaml"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


# -----------------------------
# ROUTES
# -----------------------------
@router.get("/db/tables")
def get_db_tables():
    """Tabellenübersicht für Admin-Panel (SQLite)."""
    db_path = "data/filamenthub.db"
    tables = []
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        for (table_name,) in cursor.fetchall():
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [{"name": col[1], "type": col[2], "primary_key": bool(col[5])} for col in cursor.fetchall()]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            tables.append({"name": table_name, "columns": columns, "count": count})
    return {"tables": tables}


@router.get("/config/logging")
def get_logging_config():
    """Gibt die Logging-Konfiguration zurück."""
    config = load_config()
    return config.get("logging", {})


@router.get("/config")
def get_full_config():
    """Gibt die gesamte config.yaml zurück (alias zu /config/raw)."""
    return load_config()


@router.post("/config/logging/toggle")
def toggle_logging_module(data: LogModuleToggle):
    """Schaltet ein Logging-Modul an/aus."""
    config = load_config()
    if "logging" not in config or "modules" not in config["logging"]:
        raise HTTPException(status_code=400, detail="Logging-Konfiguration fehlt")

    modules = config["logging"]["modules"]
    if data.module not in modules:
        raise HTTPException(status_code=404, detail=f"Modul '{data.module}' nicht gefunden")

    modules[data.module]["enabled"] = data.enabled
    save_config(config)
    return {
        "success": True,
        "module": data.module,
        "enabled": data.enabled,
        "message": f"Modul '{data.module}' wurde {'aktiviert' if data.enabled else 'deaktiviert'}",
    }


@router.post("/config/logging/level")
def update_log_level(data: LogLevelUpdate):
    """Setzt das globale Log-Level (DEBUG/INFO/WARNING/ERROR/CRITICAL)."""
    allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level = data.level.upper()
    if level not in allowed:
        raise HTTPException(status_code=400, detail=f"Ungültiges Log-Level. Erlaubt: {', '.join(allowed)}")

    config = load_config()
    config["logging"]["level"] = level
    save_config(config)
    return {"success": True, "level": level, "message": f"Log-Level auf '{level}' gesetzt. Neustart empfohlen."}


@router.post("/config/logging/rotation")
def update_log_rotation(data: LogRotationUpdate):
    """Aktualisiert Logrotation (max_size_mb, backup_count) und passt MQTT-Logger an."""
    config = load_config()
    if "logging" not in config:
        config["logging"] = {}
    config["logging"]["max_size_mb"] = data.max_size_mb
    config["logging"]["backup_count"] = data.backup_count
    save_config(config)

    try:
        import logging
        from logging.handlers import RotatingFileHandler
        from app.routes.mqtt_routes import mqtt_message_logger

        for handler in mqtt_message_logger.handlers[:]:
            mqtt_message_logger.removeHandler(handler)
            handler.close()

        logfile = "logs/mqtt/mqtt_messages.log"
        os.makedirs(os.path.dirname(logfile), exist_ok=True)
        new_handler = RotatingFileHandler(
            logfile,
            maxBytes=data.max_size_mb * 1024 * 1024,
            backupCount=data.backup_count,
            encoding="utf-8",
        )
        formatter = logging.Formatter("%(asctime)s | %(message)s")
        new_handler.setFormatter(formatter)
        mqtt_message_logger.addHandler(new_handler)
        return {
            "success": True,
            "max_size_mb": data.max_size_mb,
            "backup_count": data.backup_count,
            "message": f"Logger aktualisiert: max {data.max_size_mb} MB, {data.backup_count} Backups",
        }
    except Exception as e:
        return {
            "success": True,
            "max_size_mb": data.max_size_mb,
            "backup_count": data.backup_count,
            "message": f"Config gespeichert, aber Logger-Update fehlgeschlagen: {e}. Neustart empfohlen.",
        }


@router.get("/modules/status")
def get_modules_status():
    """Status aller Logging-Module zurückgeben."""
    config = load_config()
    modules = config.get("logging", {}).get("modules", {})
    result = {}
    for name, cfg in modules.items():
        result[name] = {"enabled": cfg.get("enabled", False), "has_logs": os.path.exists(f"logs/{name}")}

    return {"global_level": config.get("logging", {}).get("level", "INFO"), "modules": result}


@router.get("/environment")
def get_environment_info():
    """Infos zur Python-Umgebung."""
    import sys
    import platform

    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


@router.get("/paths")
def get_project_paths():
    """Wichtige Projektpfade."""
    config = load_config()
    return {
        "project_root": os.getcwd(),
        "config_file": os.path.abspath(CONFIG_PATH),
        "logs_root": os.path.abspath(config.get("paths", {}).get("logs", "./logs")),
        "database": os.path.abspath("data/filamenthub.db"),
        "templates": os.path.abspath("frontend/templates"),
        "static": os.path.abspath("app/static"),
    }


@router.get("/config/raw")
def get_raw_config():
    """Gibt die komplette config.yaml zurück."""
    return load_config()


@router.post("/config/raw")
def save_raw_config(data: dict):
    """Speichert die komplette config.yaml (Rohinhalt)."""
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Config muss ein Objekt sein")
    save_config(data)
    return {"success": True}


@router.post("/restart-required")
def check_restart_required():
    """Dummy-Endpunkt: meldet Neustart empfohlen (falls Config geändert)."""
    return {
        "restart_required": True,
        "reason": "Config-Änderungen wurden vorgenommen",
        "recommendation": "Server neu starten für Änderungen",
    }
