from fastapi import APIRouter, HTTPException, Depends
import logging
from pydantic import BaseModel
from sqlalchemy import text
from app.db.session import session_scope
import yaml
import os
import logging
import inspect
from sqlmodel import Session
from app.database import get_session
from app.models.settings import Setting
from typing import List, Dict, Any

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
    logger = logging.getLogger("app")
    error_logger = logging.getLogger("errors")
    caller = "unknown"
    try:
        fr = inspect.stack()[1]
        caller = f"{fr.filename}:{fr.lineno} in {fr.function}"
    except Exception:
        error_logger.exception("Failed to resolve config save caller")
    try:
        logger.info("Writing config.yaml (debug_routes.save_config) called from %s", caller)
    except Exception:
        error_logger.exception("Failed to log config save call")
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


# -----------------------------
# ROUTES
# -----------------------------
@router.get("/db/tables")
def get_db_tables_new():
    """Neue, vereinfachte Tabellenübersicht - zeigt echte Daten aus der DB."""
    logger = logging.getLogger("app")
    
    try:
        with session_scope() as session:
            # Hole alle Tabellennamen
            res = session.exec(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """))
            table_names = [row[0] for row in res.all()]
            logger.info(f"[DB/Tables] Found {len(table_names)} tables")
            
            tables_list = []
            
            for table_name in table_names:
                try:
                    # Spalten info
                    cols_res = session.exec(text(f"PRAGMA table_info({table_name})"))
                    cols_rows = cols_res.all()
                    columns = []
                    for col_row in cols_rows:
                        col_list = list(col_row)
                        columns.append({
                            "name": col_list[1],
                            "type": col_list[2],
                            "primary_key": bool(col_list[5])
                        })
                    
                    # Zeilenanzahl
                    count_res = session.exec(text(f"SELECT COUNT(*) as cnt FROM {table_name}"))
                    count_row = count_res.first()
                    row_count = int(count_row[0]) if count_row else 0
                    
                    # Preview Daten (alle Zeilen, max 100)
                    preview_rows = []
                    preview_headers = []
                    if row_count > 0:
                        try:
                            preview_res = session.exec(text(f"SELECT * FROM {table_name} LIMIT 100"))
                            preview_rows_raw = preview_res.all()
                            preview_headers = [col["name"] for col in columns]
                            # Konvertiere Row Objekte zu Lists
                            for row in preview_rows_raw:
                                preview_rows.append(list(row))
                            logger.info(f"[DB/Tables] {table_name}: {len(preview_rows)} preview rows")
                        except Exception as e:
                            logger.warning(f"[DB/Tables] Preview for {table_name} failed: {e}")
                    
                    tables_list.append({
                        "name": table_name,
                        "columns": columns,
                        "column_count": len(columns),
                        "row_count": row_count,
                        "preview": {
                            "headers": preview_headers,
                            "rows": preview_rows
                        }
                    })
                    
                except Exception as e:
                    logger.warning(f"[DB/Tables] Error processing {table_name}: {e}")
                    continue
            
            return {
                "success": True,
                "tables": tables_list,
                "count": len(tables_list)
            }
            
    except Exception as e:
        logger.exception(f"[DB/Tables] Fatal error: {e}")
        return {
            "success": False,
            "error": str(e),
            "tables": []
        }


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
    Gibt Log-Eintraege zurueck.
    Query-Parameter: module (app|mqtt|bambu|services|database|errors), limit (default: 100)
    """
    import glob
    import re
    from datetime import datetime

    requested_module = (module or "app").lower()
    module_map = {
        "app": "app",
        "mqtt": "mqtt",
        "errors": "errors",
        "bambu": "app",
        "services": "app",
        "database": "app",
    }
    module_filter = None
    if requested_module in {"bambu", "services", "database"}:
        module_filter = requested_module
    module_key = module_map.get(requested_module, requested_module)
    config = load_config()
    logs_root = config.get("paths", {}).get("logs", "./logs")

    # Versuche mehrere Log-Pfade:
    # 1. logs/{module_key}/{module_key}.log (neue Struktur)
    # 2. logs/{module_key}/*.log (alte Struktur mit Datum-Dateien)
    # 3. logs/{module_key}*.log (direkt im logs-Ordner)
    
    log_files = []
    main_log = os.path.join(logs_root, module_key, f"{module_key}.log")
    if os.path.isfile(main_log):
        log_files.append(main_log)
    
    if not log_files:
        log_pattern_sub = os.path.join(logs_root, module_key, "*.log")
        log_files = glob.glob(log_pattern_sub)

    if not log_files:
        log_pattern = os.path.join(logs_root, f"{module_key}*.log")
        log_files = glob.glob(log_pattern)

    if not log_files:
        return {
            "logs": [],
            "count": 0,
            "module": requested_module,
            "debug": {
                "logs_root": logs_root,
                "pattern_1": log_pattern,
                "pattern_2": os.path.join(logs_root, module_key, "*.log"),
                "cwd": os.getcwd(),
            },
        }

    log_file = max(log_files, key=os.path.getmtime)

    logs = []
    total_lines_read = 0
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            total_lines_read = len(lines)
            # Wenn wir filtern, lesen wir die ganze Datei, sonst nur die letzten Zeilen
            if not module_filter:
                lines = lines[-limit:]

            log_pattern = re.compile(
                r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+\[(\w+)\]\s+([\w\.]+)\s+[\u2013\u2014\-]?\s*(.+)$'
            )

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                match = log_pattern.match(line)
                if match:
                    timestamp, level, log_module, message = match.groups()
                    if module_filter and log_module != module_filter:
                        continue
                    logs.append({
                        "timestamp": timestamp,
                        "module": log_module,
                        "level": level,
                        "message": message,
                    })
                else:
                    timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)', line)
                    if timestamp_match:
                        timestamp = timestamp_match.group(1)
                        message = line[len(timestamp):].strip()
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        message = line

                    if module_filter:
                        continue

                    logs.append({
                        "timestamp": timestamp,
                        "module": module_key,
                        "level": "INFO",
                        "message": message,
                    })

    except Exception as exc:
        logging.getLogger("errors").exception("Failed to read logs for module %s", requested_module)
        return {
            "error": str(exc),
            "logs": [],
            "count": 0,
            "module": requested_module,
            "file": log_file if "log_file" in locals() else None,
        }

    # Limit anwenden NACH dem Filtern (wenn module_filter gesetzt ist)
    if module_filter and len(logs) > limit:
        logs = logs[-limit:]

    return {
        "logs": logs,
        "count": len(logs),
        "module": requested_module,
        "file": os.path.basename(log_file),
        "debug": {
            "total_lines_read": total_lines_read,
            "file_path": log_file,
            "limit": limit,
        },
    }


def delete_logs(module: str = "app"):
    """
    Loescht Log-Dateien fuer das angegebene Modul.
    Unterstuetzt Unterordnerstruktur.
    """
    import glob
    module_map = {
        "app": "app",
        "mqtt": "mqtt",
        "errors": "errors",
        "bambu": "app",
        "services": "app",
        "database": "app",
    }
    module_key = module_map.get(module.lower(), module)
    cfg = load_config()
    logs_root = cfg.get("paths", {}).get("logs", "./logs")

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
                logging.getLogger("errors").exception("Failed to delete log file %s", fp)
    try:
        logger = logging.getLogger("app")
        logger.info("Log-Dateien geloescht: module=%s, count=%s", module_key, len(deleted))
    except Exception:
        logging.getLogger("errors").exception("Failed to log deleted files for module %s", module_key)
    return {"deleted": deleted, "module": module_key}


@router.post("/logs/clear")
def clear_logs_post(payload: dict):
    """
    Leert Logdateien fuer ein Modul (sichere Behandlung von FileHandlers).
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
            "errors": "errors",
            "bambu": "app",
            "services": "app",
            "database": "app",
        }
        module_key = module_map.get(module.lower(), module)
        cfg = load_config()
        logs_root = cfg.get("paths", {}).get("logs", "./logs")
        logs_root_path = Path(logs_root).resolve()

        patterns = [str(logs_root_path / f"{module_key}*.log"), str(logs_root_path / module_key / "*.log")]
        files = sorted({fp for pat in patterns for fp in glob.glob(pat)})

        if not files:
            logging.getLogger("app").info("Keine Logdatei zum Leeren gefunden: module=%s", module_key)
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
                logging.getLogger("errors").exception("Failed to resolve log handler path %s", base)
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
                        logger.exception("Fehler beim Leeren des FileHandlers fuer %s: %s", file_path, exc)
                if not handler_success:
                    raise RuntimeError(f"FileHandler konnte nicht geleert werden: {file_path}")
            else:
                with open(file_path, "w", encoding="utf-8"):
                    logging.getLogger("app").info("Logdatei geleert: %s", file_path)
            cleared.append(str(file_path))

        logger.info("Logdateien geleert: module=%s, count=%s", module_key, len(cleared))
        return {"status": "ok", "message": "Logdatei wurde geleert"}

    except Exception as exc:
        logging.getLogger("app").exception("Log-Clear fehlgeschlagen: module=%s, error=%s", module, exc)
        return {"status": "fail", "message": "Logdatei konnte nicht geleert werden", "details": str(exc)}

# -----------------------------
# PRO MODE CONFIRMATION
# -----------------------------
@router.get("/pro-mode/status")
def get_pro_mode_status(session: Session = Depends(get_session)):
    """Prüft ob User Pro-Mode bereits bestätigt hat"""
    setting = session.get(Setting, "debug.pro_mode_accepted")
    accepted = setting.value.lower() in ("true", "1", "yes") if setting and setting.value else False
    return {"accepted": accepted}


@router.post("/pro-mode/accept")
def accept_pro_mode(session: Session = Depends(get_session)):
    """Speichert dass User Pro-Mode bestätigt hat (nur einmal)"""
    setting = session.get(Setting, "debug.pro_mode_accepted")
    if setting:
        setting.value = "true"
    else:
        setting = Setting(key="debug.pro_mode_accepted", value="true")
        session.add(setting)
    session.commit()
    logging.getLogger("app").info("Pro-Mode wurde vom User bestätigt")
    return {"success": True, "accepted": True}


# ============================================================
# MQTT INJECT ENDPOINT (für Tests / Log-Replay)
# ============================================================

class MqttInjectRequest(BaseModel):
    topic: str
    payload: Dict[str, Any]


@router.post("/mqtt/inject")
async def inject_mqtt_message(req: MqttInjectRequest):
    """
    Injiziert eine MQTT-Nachricht direkt in die FilamentHub-Verarbeitungs-Pipeline.
    Nützlich für Tests und das Replay von aufgezeichneten MQTT-Logs.

    POST /api/debug/mqtt/inject
    Body: { "topic": "device/SERIAL/report", "payload": { "print": { ... } } }
    """
    import json
    logger = logging.getLogger("debug")

    try:
        from app.services.mqtt_payload_processor import process_mqtt_payload
        from app.routes.mqtt_routes import printer_service_ref, broadcast_message
        from app.services.job_tracking_service import job_tracking_service
        from app.models.printer import Printer
        from sqlmodel import select

        payload_str = json.dumps(req.payload)

        # Verarbeite wie echter MQTT-Empfang
        proc = process_mqtt_payload(req.topic, payload_str, printer_service_ref)

        ams_data = proc.get("ams") or []
        job_data = proc.get("job") or {}
        mapped_dict = proc.get("mapped_dict")

        # Serial aus Topic extrahieren (device/SERIAL/report)
        serial = proc.get("serial") or ""
        try:
            parts = req.topic.split("/")
            if len(parts) >= 2 and parts[0] == "device":
                serial = parts[1]
        except Exception:
            pass

        logger.info(f"[MQTT INJECT] topic={req.topic} serial={serial} state={job_data.get('gcode_state','?')}")

        # Printer-ID aus DB holen (für Job-Tracking nötig)
        printer_id = None
        if serial:
            try:
                with next(get_session()) as _sess:
                    p = _sess.exec(select(Printer).where(Printer.cloud_serial == serial)).first()
                    if p:
                        printer_id = p.id
            except Exception as pe:
                logger.debug(f"[MQTT INJECT] Printer lookup failed: {pe}")

        # ============================================================
        # JOB-TRACKING (identisch zur normalen MQTT-Pipeline)
        # Läuft im Thread-Pool um den async Event-Loop nicht zu blockieren
        # ============================================================
        job_tracking_result = None
        if req.topic.endswith("/report") and serial:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                ams_list = [dict(u) for u in ams_data] if ams_data else None

                def _run_job_tracking():
                    return job_tracking_service.process_message(
                        cloud_serial=serial,
                        parsed_payload=req.payload,
                        printer_id=printer_id,
                        ams_data=ams_list,
                    )

                job_tracking_result = await loop.run_in_executor(None, _run_job_tracking)
                if job_tracking_result:
                    logger.info(f"[MQTT INJECT] Job-Tracking: {job_tracking_result}")
            except Exception as jt_err:
                logger.exception(f"[MQTT INJECT] Job-Tracking fehlgeschlagen: {jt_err}")

        # Broadcast an WebSocket-Clients (Dashboard-Updates)
        try:
            class FakeMsg:
                topic = req.topic
                payload_str = json.dumps(req.payload)
            await broadcast_message(
                FakeMsg(),
                ams_data=ams_data,
                job_data=job_data,
                printer_data=mapped_dict,
                raw_payload=payload_str
            )
        except Exception as bc_err:
            logger.debug(f"[MQTT INJECT] broadcast failed (non-critical): {bc_err}")

        return {
            "success": True,
            "serial": serial,
            "printer_id": printer_id,
            "gcode_state": job_data.get("gcode_state"),
            "layer": job_data.get("layer_num"),
            "total_layers": job_data.get("total_layer_num"),
            "ams_slots": len(ams_data),
            "job_tracking": job_tracking_result,
        }

    except Exception as e:
        logger.exception("[MQTT INJECT] Fehler beim Verarbeiten")
        raise HTTPException(status_code=500, detail=str(e))









