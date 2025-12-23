from fastapi import APIRouter, HTTPException
import logging
from pydantic import BaseModel
import sqlite3
import yaml
import os
import logging
import inspect

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
    try:
        logger = logging.getLogger('app')
        caller = None
        try:
            fr = inspect.stack()[1]
            caller = f"{fr.filename}:{fr.lineno} in {fr.function}"
        except Exception:
            caller = "unknown"
        logger.info(f"Writing config.yaml (debug_routes.save_config) called from {caller}")
    except Exception:
        pass
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


@router.get("/logs")
def get_logs(module: str = "app", limit: int = 100):
    """
    Gibt Log-Einträge zurück.
    Query-Parameter: module (app|mqtt|bambu|klipper|errors), limit (default: 100)
    """
    import glob
    import re
    from datetime import datetime
    
    # Map module names to folder names
    module_map = {
        "app": "app",
        "mqtt": "mqtt",
        "3d_drucker": "3d_drucker",
        "3d-drucker": "3d_drucker",
        "3d_printer": "3d_drucker",
        "printer": "3d_drucker",
        "bambu": "3d_drucker",
        "klipper": "klipper",
        "errors": "errors"
    }
    
    module = module_map.get(module.lower(), module)
    config = load_config()
    logs_root = config.get("paths", {}).get("logs", "./logs")
    
    # Suche nach Log-Dateien - auch in Unterordnern
    log_pattern = os.path.join(logs_root, f"{module}*.log")
    log_files = glob.glob(log_pattern)
    
    # Falls nicht gefunden, suche in Unterordner mit gleichem Namen
    if not log_files:
        log_pattern_sub = os.path.join(logs_root, module, "*.log")
        log_files = glob.glob(log_pattern_sub)
    
    if not log_files:
        return {
            "logs": [], 
            "count": 0, 
            "module": module, 
            "debug": {
                "logs_root": logs_root,
                "pattern_1": log_pattern,
                "pattern_2": os.path.join(logs_root, module, "*.log"),
                "cwd": os.getcwd()
            }
        }
    
    # Neueste Log-Datei verwenden
    log_file = max(log_files, key=os.path.getmtime)
    
    logs = []
    total_lines_read = 0
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            total_lines_read = len(lines)
            
            # Nimm die letzten 'limit' Zeilen
            lines = lines[-limit:]
            
            # Parse Log-Zeilen (Format: 2025-11-24 21:47:48,910 [INFO] uvicorn.error – Message)
            # Unterstützt verschiedene Dash-Zeichen: - – —
            log_pattern = re.compile(
                r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+\[(\w+)\]\s+([\w\.]+)\s+[\u2013\u2014\-–—]+\s+(.+)$'
            )
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                match = log_pattern.match(line)
                if match:
                    timestamp, level, log_module, message = match.groups()
                    logs.append({
                        "timestamp": timestamp,
                        "module": log_module,
                        "level": level,
                        "message": message
                    })
                else:
                    # Fallback: unformatierte Zeile - versuche trotzdem Timestamp zu extrahieren
                    timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)', line)
                    if timestamp_match:
                        timestamp = timestamp_match.group(1)
                        message = line[len(timestamp):].strip()
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        message = line
                    
                    logs.append({
                        "timestamp": timestamp,
                        "module": module,
                        "level": "INFO",
                        "message": message
                    })
    
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "logs": [],
            "count": 0,
            "module": module,
            "file": log_file if 'log_file' in locals() else None
        }
    
    return {
        "logs": logs,
        "count": len(logs),
        "module": module,
        "file": os.path.basename(log_file),
        "debug": {
            "total_lines_read": total_lines_read,
            "file_path": log_file,
            "limit": limit
        }
    }


def delete_logs(module: str = "app"):
    """
    Löscht Log-Dateien für das angegebene Modul.
    Unterstützt Unterordnerstruktur.
    """
    import glob
    module_map = {
        "app": "app",
        "mqtt": "mqtt",
        "3d_drucker": "3d_drucker",
        "3d-drucker": "3d_drucker",
        "3d_printer": "3d_drucker",
        "printer": "3d_drucker",
        "klipper": "klipper",
        "errors": "errors"
    }
    module_key = module_map.get(module.lower(), module)
    cfg = load_config()
    logs_root = cfg.get("paths", {}).get("logs", "./logs")

    # Muster: Root/app*.log und Root/app/*.log
    patterns = [
        os.path.join(logs_root, f"{module_key}*.log"),
        os.path.join(logs_root, module_key, "*.log"),
    ]

    deleted = []
    for pat in patterns:
        for fp in glob.glob(pat):
            try:
                os.remove(fp)
                deleted.append(fp)
            except Exception:
                pass
    # Server-Log: Löschvorgang protokollieren
    try:
        logger = logging.getLogger("app")
        logger.info(f"Log-Dateien gelöscht: module={module_key}, count={len(deleted)}")
    except Exception:
        pass
    return {"deleted": deleted, "module": module_key}


@router.post("/logs/clear")
def clear_logs_post(payload: dict):
    """
    Leert Logdateien für ein Modul (sichere Behandlung von FileHandlers).
    Erwartet JSON-Body: { "module": "<name>" }
    Antwort immer 200 mit Standard-Response.
    """
    module = (payload or {}).get("module") if isinstance(payload, dict) else None
    if not module:
        return {"status": "fail", "message": "Logdatei konnte nicht geleert werden", "details": "missing module"}
    return _clear_logs_impl(module)


@router.delete("/logs")
def clear_logs_delete(module: str = "app"):
    """
    Kompatibler DELETE-Endpunkt: /api/debug/logs?module=app
    Antwort immer 200 mit Standard-Response.
    """
    return _clear_logs_impl(module)


def _clear_logs_impl(module: str):
    """Common implementation for safely clearing log files."""
    from pathlib import Path
    import glob

    try:
        module_map = {
            "app": "app",
            "mqtt": "mqtt",
            "3d_drucker": "3d_drucker",
            "3d-drucker": "3d_drucker",
            "3d_printer": "3d_drucker",
            "printer": "3d_drucker",
            "klipper": "klipper",
            "errors": "errors",
        }
        module_key = module_map.get(module.lower(), module)
        cfg = load_config()
        logs_root = cfg.get("paths", {}).get("logs", "./logs")
        logs_root_path = Path(logs_root).resolve()

        patterns = [str(logs_root_path / f"{module_key}*.log"), str(logs_root_path / module_key / "*.log")]
        files = sorted({fp for pat in patterns for fp in glob.glob(pat)})

        if not files:
            logging.getLogger("app").info(f"Keine Logdatei zum Leeren gefunden: module={module_key}")
            return {"status": "ok", "message": "Logdatei wurde geleert"}

        cleared = []
        logger = logging.getLogger("app")

        def _matches_handler(handler, target_path: Path) -> bool:
            base = getattr(handler, "baseFilename", None)
            if not base:
                return False
            try:
                return Path(base).resolve() == target_path
            except Exception:
                return False

        def _collect_handlers(target_path: Path):
            matched = set()
            for handler in logging.root.handlers:
                if isinstance(handler, logging.FileHandler) and _matches_handler(handler, target_path):
                    matched.add(handler)
            for logger_obj in logging.root.manager.loggerDict.values():
                if isinstance(logger_obj, logging.Logger):
                    for handler in getattr(logger_obj, "handlers", []):
                        if isinstance(handler, logging.FileHandler) and _matches_handler(handler, target_path):
                            matched.add(handler)
            return matched

        def _truncate_handler(handler: logging.FileHandler):
            handler.acquire()
            try:
                stream = getattr(handler, "stream", None)
                if stream:
                    stream.seek(0)
                    stream.truncate(0)
            finally:
                handler.release()

        for fp in files:
            file_path = Path(fp).resolve()
            handlers = _collect_handlers(file_path)
            if handlers:
                handler_success = False
                for handler in handlers:
                    try:
                        _truncate_handler(handler)
                        handler_success = True
                    except Exception as exc:
                        logger.exception(f"Fehler beim Leeren des FileHandlers für {file_path}: {exc}")
                if not handler_success:
                    raise RuntimeError(f"FileHandler konnte nicht geleert werden: {file_path}")
            else:
                with open(file_path, "w", encoding="utf-8"):
                    pass
            cleared.append(str(file_path))

        logger.info(f"Logdateien geleert: module={module_key}, count={len(cleared)}")
        return {"status": "ok", "message": "Logdatei wurde geleert"}

    except Exception as exc:
        logging.getLogger("app").exception(f"Log-Clear fehlgeschlagen: module={module}, error={exc}")
        return {"status": "fail", "message": "Logdatei konnte nicht geleert werden", "details": str(exc)}
