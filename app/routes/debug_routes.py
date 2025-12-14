from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
import yaml
import os

router = APIRouter(prefix="/api/debug", tags=["Debug & Config"])


DEPRECATED_LOGGING_RESPONSE = {"deprecated": True, "use": "/api/config"}

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
    """Gibt die Logging-Konfiguration zur?ck."""
    return DEPRECATED_LOGGING_RESPONSE


@router.get("/config")


@router.get("/config")
def get_full_config():
    """Gibt die gesamte config.yaml zurück (alias zu /config/raw)."""
    return load_config()


@router.post("/config/logging/toggle")
def toggle_logging_module(data: LogModuleToggle):
    """Schaltet ein Logging-Modul an/aus."""
    return DEPRECATED_LOGGING_RESPONSE


@router.post("/config/logging/level")


@router.post("/config/logging/level")
def update_log_level(data: LogLevelUpdate):
    """Setzt das globale Log-Level (DEBUG/INFO/WARNING/ERROR/CRITICAL)."""
    return DEPRECATED_LOGGING_RESPONSE


@router.post("/config/logging/rotation")


@router.post("/config/logging/rotation")
def update_log_rotation(data: LogRotationUpdate):
    """Aktualisiert Logrotation (max_size_mb, backup_count) und passt MQTT-Logger an."""
    return DEPRECATED_LOGGING_RESPONSE


@router.get("/modules/status")


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
