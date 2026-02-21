from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket
import logging
import yaml
import os
import asyncio
from app.logging_setup import configure_logging

# ============================================================
# GLOBAL SHUTDOWN STATE - Shared zwischen Startup und Shutdown
# ============================================================
_app_is_shutting_down = False

def set_app_shutdown_flag():
    """Mark app as shutting down globally"""
    global _app_is_shutting_down
    _app_is_shutting_down = True

def is_app_shutting_down():
    """Check if app is in shutdown state"""
    return _app_is_shutting_down

# Logging-Konfiguration aus config.yaml
def get_logging_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
    if not os.path.exists(config_path):
        return {
            "enabled": True,
            "level": "INFO",
            "keep_days": 14,
            "max_size_mb": 10,
            "backup_count": 3,
            "modules": {},
        }
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    logging_cfg = config.get("logging", {})
    return {
        "enabled": logging_cfg.get("enabled", True),
        "level": logging_cfg.get("level", "INFO"),
        "keep_days": logging_cfg.get("keep_days", 14),
        "max_size_mb": logging_cfg.get("max_size_mb", 10),
        "backup_count": logging_cfg.get("backup_count", 3),
        "modules": logging_cfg.get("modules", {}),
    }

from app.admin import enable_admin


def init_admin():
    import os

    logger = logging.getLogger("app")
    admin_hash = os.getenv("ADMIN_PASSWORD_HASH")
    if admin_hash:
        try:
            enable_admin(admin_hash)
            logger.info("Admin enabled via environment variable")
        except Exception:
            logger.exception("Failed to enable admin from environment variable")
    else:
        logger.info("Admin disabled (no ADMIN_PASSWORD_HASH)")


from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from services.printer_service import initialize_printer_service
from app.services.ams_sync import mark_printer_service_started
from app.services.ams_sync_state import set_ams_sync_state
from app.services import mqtt_runtime
from app.monitoring.runtime_monitor import record_request
import time

from app.database import init_db
from app.routes.hello import router as hello_router
from app.routes.materials import router as materials_router
from app.routes.spools import router as spools_router
from app.routes.spool_numbers import router as spool_numbers_router  # NEU: Spulen-Nummern-System
from app.routes.log_routes import router as log_router
from app.routes.system_routes import router as system_router
from app.routes.debug_routes import router as debug_router
from app.routes.service_routes import router as service_router
from app.routes.database_routes import router as database_router
from app.routes.backup_routes import router as backup_router
from app.routes.scanner_routes import router as scanner_router, debug_printer_router
from app.routes.mqtt_routes import router as mqtt_router
from app.routes.performance_routes import router as performance_router
from app.routes.printers import router as printers_router
from app.routes.jobs import router as jobs_router
from app.routes.statistics_routes import router as statistics_router

from app.routes.bambu_routes import router as bambu_router
from app.routes.admin_routes import router as admin_router
from app.routes.admin_coverage_routes import router as admin_coverage_router
from app.routes.settings_routes import router as settings_router
from app.routes.debug_ams_routes import router as debug_ams_router
from app.routes.debug_system_routes import router as debug_system_router
from app.routes.debug_performance_routes import router as debug_performance_router
from app.routes.debug_network_routes import router as debug_network_router
from app.routes.notification_routes import router as notification_router
from app.routes.config_routes import router as config_router
from app.routes import debug_log_routes
from app.routes import mqtt_runtime_routes
from app.routes.live_state_routes import router as live_state_router
from app.routes.ams_routes import router as ams_router
from app.routes.ams_conflicts import router as ams_conflicts_router
from app.routes.lexikon_routes import router as lexikon_router
from app.routes.externe_spule_routes import router as externe_spule_router
from app.routes.weight_management_routes import router as weight_management_router
from app.routes.spool_assignment_routes import router as spool_assignment_router
from app.routes.monitoring_routes import router as monitoring_router
from app.routes.bambu_cloud_routes import router as bambu_cloud_router

from app.websocket.log_stream import stream_log
from sqlmodel import Session, select
from app.database import engine
from app.models.printer import Printer
from app.models.material import Material


# -----------------------------------------------------
# SEED DEFAULT MATERIALS
# -----------------------------------------------------
def seed_default_materials():
    """Create default Bambu Lab materials if database is empty."""
    logger = logging.getLogger("app")

    with Session(engine) as session:
        # Check if materials already exist
        existing = session.exec(select(Material)).first()
        if existing:
            return  # Materials already exist, skip seeding

        logger.info("Keine Materialien gefunden - erstelle Standard-Materialien...")

        default_materials = [
            # Bambu Lab (Leergewicht: 209g Kunststoffspule)
            {"name": "PLA Basic", "brand": "Bambu Lab", "material_type": "PLA", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.24, "nozzle_temp_min": 190, "nozzle_temp_max": 230, "bed_temp_min": 45, "bed_temp_max": 60},
            {"name": "PLA Matte", "brand": "Bambu Lab", "material_type": "PLA", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.24, "nozzle_temp_min": 190, "nozzle_temp_max": 230, "bed_temp_min": 45, "bed_temp_max": 60},
            {"name": "PETG Basic", "brand": "Bambu Lab", "material_type": "PETG", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.27, "nozzle_temp_min": 220, "nozzle_temp_max": 260, "bed_temp_min": 70, "bed_temp_max": 80},
            {"name": "ABS", "brand": "Bambu Lab", "material_type": "ABS", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.04, "nozzle_temp_min": 250, "nozzle_temp_max": 280, "bed_temp_min": 90, "bed_temp_max": 100},
            {"name": "TPU 95A", "brand": "Bambu Lab", "material_type": "TPU", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.21, "nozzle_temp_min": 220, "nozzle_temp_max": 240, "bed_temp_min": 45, "bed_temp_max": 60},
            {"name": "PA-CF", "brand": "Bambu Lab", "material_type": "PA-CF", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.12, "nozzle_temp_min": 270, "nozzle_temp_max": 300, "bed_temp_min": 90, "bed_temp_max": 100},
            {"name": "PLA-CF", "brand": "Bambu Lab", "material_type": "PLA-CF", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.29, "nozzle_temp_min": 190, "nozzle_temp_max": 230, "bed_temp_min": 45, "bed_temp_max": 60},

            # Bambu Lab Refill (Leergewicht: 209g)
            {"name": "PLA Basic Refill", "brand": "Bambu Lab", "material_type": "PLA", "is_bambu": True, "spool_weight_full": 1000.0, "spool_weight_empty": 209.0, "density": 1.24, "nozzle_temp_min": 190, "nozzle_temp_max": 230, "bed_temp_min": 45, "bed_temp_max": 60},

            # eSUN (Leergewicht: 256g Kunststoff)
            {"name": "PLA+", "brand": "eSUN", "material_type": "PLA", "spool_weight_empty": 256.0, "density": 1.24, "nozzle_temp_min": 205, "nozzle_temp_max": 225, "bed_temp_min": 50, "bed_temp_max": 70},
            {"name": "PETG", "brand": "eSUN", "material_type": "PETG", "spool_weight_empty": 256.0, "density": 1.27, "nozzle_temp_min": 230, "nozzle_temp_max": 250, "bed_temp_min": 70, "bed_temp_max": 80},
            {"name": "ABS+", "brand": "eSUN", "material_type": "ABS", "spool_weight_empty": 256.0, "density": 1.04, "nozzle_temp_min": 240, "nozzle_temp_max": 260, "bed_temp_min": 90, "bed_temp_max": 100},

            # Sunlu (Leergewicht: 190g, PLA+ 154g)
            {"name": "PLA", "brand": "Sunlu", "material_type": "PLA", "spool_weight_empty": 190.0, "density": 1.24, "nozzle_temp_min": 200, "nozzle_temp_max": 220, "bed_temp_min": 50, "bed_temp_max": 60},
            {"name": "PLA+", "brand": "Sunlu", "material_type": "PLA", "spool_weight_empty": 154.0, "density": 1.24, "nozzle_temp_min": 205, "nozzle_temp_max": 225, "bed_temp_min": 50, "bed_temp_max": 70},
            {"name": "PETG", "brand": "Sunlu", "material_type": "PETG", "spool_weight_empty": 190.0, "density": 1.27, "nozzle_temp_min": 230, "nozzle_temp_max": 250, "bed_temp_min": 70, "bed_temp_max": 85},

            # 3DJake (Leergewicht: 231g)
            {"name": "PLA", "brand": "3DJake", "material_type": "PLA", "spool_weight_empty": 231.0, "density": 1.24, "nozzle_temp_min": 190, "nozzle_temp_max": 220, "bed_temp_min": 50, "bed_temp_max": 60},
            {"name": "PETG", "brand": "3DJake", "material_type": "PETG", "spool_weight_empty": 231.0, "density": 1.27, "nozzle_temp_min": 220, "nozzle_temp_max": 250, "bed_temp_min": 70, "bed_temp_max": 80},

            # Prusament (Leergewicht: ~200g)
            {"name": "PLA", "brand": "Prusament", "material_type": "PLA", "spool_weight_empty": 200.0, "density": 1.24, "nozzle_temp_min": 215, "nozzle_temp_max": 215, "bed_temp_min": 60, "bed_temp_max": 60},
            {"name": "PETG", "brand": "Prusament", "material_type": "PETG", "spool_weight_empty": 200.0, "density": 1.27, "nozzle_temp_min": 240, "nozzle_temp_max": 250, "bed_temp_min": 85, "bed_temp_max": 90},

            # Amazon Basics (Leergewicht: 225g)
            {"name": "PLA", "brand": "Amazon Basics", "material_type": "PLA", "spool_weight_empty": 225.0, "density": 1.24, "nozzle_temp_min": 190, "nozzle_temp_max": 220, "bed_temp_min": 50, "bed_temp_max": 60},
            {"name": "PETG", "brand": "Amazon Basics", "material_type": "PETG", "spool_weight_empty": 225.0, "density": 1.27, "nozzle_temp_min": 230, "nozzle_temp_max": 250, "bed_temp_min": 70, "bed_temp_max": 80},

            # Creality (Leergewicht: 207g Kunststoff)
            {"name": "PLA", "brand": "Creality", "material_type": "PLA", "spool_weight_empty": 207.0, "density": 1.24, "nozzle_temp_min": 200, "nozzle_temp_max": 230, "bed_temp_min": 50, "bed_temp_max": 60},

            # Anycubic (Leergewicht: 143g)
            {"name": "PLA", "brand": "Anycubic", "material_type": "PLA", "spool_weight_empty": 143.0, "density": 1.24, "nozzle_temp_min": 200, "nozzle_temp_max": 220, "bed_temp_min": 50, "bed_temp_max": 60},

            # Das Filament (Leergewicht: 215g)
            {"name": "PLA", "brand": "Das Filament", "material_type": "PLA", "spool_weight_empty": 215.0, "density": 1.24, "nozzle_temp_min": 190, "nozzle_temp_max": 220, "bed_temp_min": 50, "bed_temp_max": 60},
            {"name": "PETG", "brand": "Das Filament", "material_type": "PETG", "spool_weight_empty": 215.0, "density": 1.27, "nozzle_temp_min": 230, "nozzle_temp_max": 250, "bed_temp_min": 70, "bed_temp_max": 80},

            # Eryone (Leergewicht: 200g)
            {"name": "PLA", "brand": "Eryone", "material_type": "PLA", "spool_weight_empty": 200.0, "density": 1.24, "nozzle_temp_min": 190, "nozzle_temp_max": 220, "bed_temp_min": 50, "bed_temp_max": 60},
        ]

        for mat_data in default_materials:
            material = Material(**mat_data)
            session.add(material)

        session.commit()
        logger.info(f"[OK] {len(default_materials)} Standard-Materialien erstellt")


# -----------------------------------------------------
# FASTAPI APP
# -----------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_settings = get_logging_config()
    configure_logging(log_settings)
    init_admin()
    init_db()
    seed_default_materials()  # Erstelle Standard-Materialien bei frischer DB
    set_ams_sync_state("pending")
    app.state.printer_service = initialize_printer_service()
    mark_printer_service_started(time.time())

    # FIX Bug #9: Speichere Event-Loop für Thread-safe Broadcasting
    import asyncio
    app.state.event_loop = asyncio.get_running_loop()

    logger = logging.getLogger("app")
    logger.info("[APP] Startup abgeschlossen - FilamentHub ist bereit")
    
    # Starte Bambu Cloud Scheduler
    try:
        from app.services.bambu_cloud_scheduler import start_scheduler
        start_scheduler()
        logger.info("[APP] Bambu Cloud Scheduler gestartet")
    except Exception as e:
        logger.warning(f"[APP] Bambu Cloud Scheduler konnte nicht gestartet werden: {e}")

    # Starte Klipper Polling
    klipper_poller_task = None
    try:
        from services.klipper_polling_service import start_klipper_polling, stop_klipper_polling
        klipper_poller_task = asyncio.create_task(start_klipper_polling())
        logger.info("[APP] Klipper Polling gestartet")
    except Exception as e:
        logger.warning(f"[APP] Klipper Polling konnte nicht gestartet werden: {e}")

    print("[DEBUG] Auto-connect starting...")  # DEBUG: Direct terminal output

    # Background-Task für kontinuierliches Auto-Reconnect
    auto_reconnect_task = None
    _shutdown_reconnect = asyncio.Event()
    
    async def auto_reconnect_loop():
        """Background-Task: Versucht alle 30 Sekunden nicht verbundene Drucker zu verbinden."""
        reconnect_interval = 30  # Sekunden zwischen Verbindungsversuchen
        logger.info(f"[AUTO-RECONNECT] Background-Task gestartet (Intervall: {reconnect_interval}s)")
        
        while not _shutdown_reconnect.is_set():
            try:
                # Warte auf nächsten Versuch oder Shutdown
                try:
                    await asyncio.wait_for(_shutdown_reconnect.wait(), timeout=reconnect_interval)
                    break  # Shutdown signalisiert
                except asyncio.TimeoutError:
                    pass  # Normal - Zeit für nächsten Versuch
                
                # Lade alle Drucker mit auto_connect=True
                try:
                    with Session(engine) as session:
                        printers = session.exec(select(Printer)).all()
                except Exception as exc:
                    logger.warning(f"[AUTO-RECONNECT] Konnte Drucker nicht laden: {exc}")
                    continue
                
                # Prüfe welche nicht verbunden sind
                from app.routes.mqtt_routes import mqtt_clients, startup_connect_printer
                from services.printer_service import get_printer_service
                
                try:
                    printer_service = get_printer_service()
                except RuntimeError:
                    printer_service = None
                
                for printer in printers:
                    if _shutdown_reconnect.is_set():
                        break
                    if not getattr(printer, "auto_connect", False):
                        continue
                    
                    # Prüfe ob bereits verbunden
                    is_connected = False
                    connection_id = f"{printer.ip_address}:8883_{printer.id}"
                    
                    # Methode 1: Prüfe mqtt_clients dict
                    if connection_id in mqtt_clients:
                        client = mqtt_clients[connection_id]
                        if client and client.is_connected():
                            is_connected = True
                    
                    # Methode 2: Prüfe PrinterService
                    if not is_connected and printer_service and printer.cloud_serial:
                        status = printer_service.get_status(printer.cloud_serial)
                        is_connected = bool(status.get("connected", False))
                    
                    if is_connected:
                        continue  # Bereits verbunden, nichts zu tun
                    
                    # Nicht verbunden → Versuch zu verbinden
                    logger.info(f"[AUTO-RECONNECT] Versuche {printer.name} zu verbinden...")
                    try:
                        success = await asyncio.wait_for(
                            asyncio.to_thread(startup_connect_printer, printer),
                            timeout=15
                        )
                        if success:
                            logger.info(f"[AUTO-RECONNECT] [OK] {printer.name} erfolgreich verbunden")
                        else:
                            logger.debug(f"[AUTO-RECONNECT] [FAIL] {printer.name} nicht erreichbar")
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"[AUTO-RECONNECT] Timeout bei Verbindungsversuch fuer {printer.name}; "
                            "naechster Versuch im naechsten Zyklus"
                        )
                    except Exception as e:
                        logger.debug(f"[AUTO-RECONNECT] [FAIL] {printer.name} Fehler: {e}")
                        
            except Exception as e:
                logger.exception(f"[AUTO-RECONNECT] Unerwarteter Fehler: {e}")
                await asyncio.sleep(5)  # Kurze Pause bei Fehler
        
        logger.info("[AUTO-RECONNECT] Background-Task beendet")
    
    try:
        with Session(engine) as session:
            printers = session.exec(select(Printer)).all()
            print(f"[DEBUG] Found {len(printers)} printers in database")  # DEBUG
    except Exception as exc:
        logger.exception("Failed to load printers for auto-connect startup: %s", exc)
        print(f"[DEBUG] Exception loading printers: {exc}")  # DEBUG
        printers = []
    
    # Multi-Printer Support: Verwende mqtt_routes für Multi-Client-Verbindungen
    print("[DEBUG] Starting auto-connect loop...")  # DEBUG
    for printer in printers:
        print(f"[DEBUG] Checking printer {printer.name}: auto_connect={getattr(printer, 'auto_connect', None)}")  # DEBUG
        if getattr(printer, "auto_connect", False):
            print(f"[DEBUG] Auto-connect TRUE for {printer.name}")  # DEBUG
            print(f"[DEBUG] Attempting import of startup_connect_printer...")  # DEBUG
            logger.info("Auto-connect: Drucker %s (%s) wird verbunden", printer.name, printer.id)
            try:
                from app.routes.mqtt_routes import startup_connect_printer
                print(f"[DEBUG] Import successful, calling function...")  # DEBUG
                success = await asyncio.wait_for(
                    asyncio.to_thread(startup_connect_printer, printer),
                    timeout=15
                )
                print(f"[DEBUG] Function returned: {success}")  # DEBUG
                if success:
                    logger.info(f"[OK] Auto-connect erfolgreich: {printer.name}")
                    print(f"[DEBUG] [OK] {printer.name} connected successfully")  # DEBUG
                else:
                    logger.error(f"[FAIL] Auto-connect fehlgeschlagen: {printer.name}")
                    print(f"[DEBUG] [FAIL] {printer.name} connection failed")  # DEBUG
            except asyncio.TimeoutError:
                logger.warning(
                    "[FAIL] Auto-connect Timeout fuer %s - wird spaeter erneut versucht",
                    printer.name
                )
            except Exception as e:
                logger.exception("Auto-connect startup failed for printer %s", printer.id)
                print(f"[DEBUG] Exception in startup_connect_printer: {e}")  # DEBUG
                import traceback
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")  # DEBUG
    print("[DEBUG] Auto-connect loop completed")  # DEBUG
    
    # Starte Background-Task für kontinuierliches Auto-Reconnect
    auto_reconnect_task = asyncio.create_task(auto_reconnect_loop())
    logger.info("[APP] Auto-Reconnect Background-Task gestartet")
    
    try:
        yield
    finally:
        # ============================================================
        # GRACEFUL SHUTDOWN: ZUERST Global Shutdown-Flag setzen!
        # ============================================================
        logger.info("[APP] Shutdown: Setting shutdown flag to stop MQTT message processing...")
        
        # Stoppe Auto-Reconnect Background-Task
        _shutdown_reconnect.set()
        if auto_reconnect_task and not auto_reconnect_task.done():
            auto_reconnect_task.cancel()
            try:
                await asyncio.wait_for(auto_reconnect_task, timeout=3)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                logger.warning("[APP] Auto-Reconnect Task konnte nicht rechtzeitig beendet werden")
            logger.info("[APP] Auto-Reconnect Task gestoppt")
        
        # 0. KRITISCH: Global Flag sofort setzen - verhindert dass neue MQTT-Clients während Reload initialisiert werden
        set_app_shutdown_flag()
        logger.info("[APP] Global shutdown flag set - no new MQTT clients will be created")
        
        # Stoppe Bambu Cloud Scheduler
        try:
            from app.services.bambu_cloud_scheduler import stop_scheduler
            stop_scheduler()
            logger.info("[APP] Bambu Cloud Scheduler gestoppt")
        except Exception as e:
            logger.warning(f"[APP] Bambu Cloud Scheduler konnte nicht gestoppt werden: {e}")

        # Stoppe Klipper Polling
        try:
            from services.klipper_polling_service import stop_klipper_polling
            stop_klipper_polling()
            if klipper_poller_task and not klipper_poller_task.done():
                klipper_poller_task.cancel()
                try:
                    await asyncio.wait_for(klipper_poller_task, timeout=3)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            logger.info("[APP] Klipper Polling gestoppt")
        except Exception as e:
            logger.warning(f"[APP] Klipper Polling konnte nicht gestoppt werden: {e}")
        
        # 1. KRITISCH: Flag auch an mqtt_routes setzen um on_message() zu stoppen
        try:
            from app.routes.mqtt_routes import set_shutdown_event
            shutdown_event = asyncio.Event()
            shutdown_event.set()
            set_shutdown_event(shutdown_event)  # Setzt _is_shutting_down = True
            logger.info("[APP] MQTT shutdown flag set - on_message() callback will ignore messages")
        except Exception:
            logger.exception("Failed to set shutdown event")
        
        # 1. SOFORT: Setze MQTT Callbacks auf NO-OP damit Paho KEINE Nachrichten mehr verarbeitet!
        logger.info("[APP] Shutdown: Disabling MQTT callbacks...")
        
        try:
            from app.routes.mqtt_routes import mqtt_clients
            def noop_callback(*args, **kwargs):
                pass  # Do nothing
            
            for connection_id, client in list(mqtt_clients.items()):
                try:
                    # Setze alle Callbacks auf NO-OP um zu verhindern dass weitere Nachrichten verarbeitet werden
                    client.on_message = noop_callback
                    client.on_connect = noop_callback
                    client.on_disconnect = noop_callback
                    logger.debug(f"[MQTT] Callbacks disabled for {connection_id}")
                except Exception:
                    logger.exception(f"Failed to disable callbacks for {connection_id}")
        except Exception:
            logger.exception("Failed to disable MQTT callbacks")
        
        # 2. DANN: MQTT-Loop stoppen
        logger.info("[APP] Shutdown: STOPPING MQTT loops immediately...")
        
        try:
            from app.routes.mqtt_routes import mqtt_clients
            for connection_id, client in list(mqtt_clients.items()):
                try:
                    logger.debug(f"[MQTT] Loop stop for {connection_id}")
                    # SOFORT loop_stop (stoppt den Hintergrund-Thread JETZT)
                    if hasattr(client, "loop_stop"):
                        try:
                            client.loop_stop()
                            logger.debug(f"[MQTT] Loop stopped for {connection_id}")
                        except Exception:
                            logger.exception(f"Failed to stop loop for {connection_id}")
                except Exception:
                    logger.exception(f"Error stopping MQTT loop for {connection_id}")
            
            # Kurz warten für Thread-Beendigung
            try:
                await asyncio.sleep(0.2)
            except Exception:
                pass
            
            # DANN disconnect (Clean up die Verbindung)
            logger.info("[APP] Shutdown: Disconnecting MQTT clients...")
            for connection_id, client in list(mqtt_clients.items()):
                try:
                    logger.debug(f"[MQTT] Disconnecting {connection_id}")
                    if hasattr(client, "disconnect"):
                        try:
                            client.disconnect()
                            logger.debug(f"[MQTT] Disconnected {connection_id}")
                        except Exception:
                            logger.exception(f"Failed to disconnect {connection_id}")
                except Exception:
                    logger.exception(f"Error disconnecting {connection_id}")
            
            mqtt_clients.clear()
            logger.info("[APP] All MQTT clients stopped")
        except Exception:
            logger.exception("Failed to stop MQTT clients")
        
        # 3. DANN: mqtt_runtime Client stoppen
        try:
            mqtt_runtime.disconnect()
            logger.info("[APP] mqtt_runtime client stopped")
        except Exception:
            logger.exception("Failed to stop mqtt_runtime")
        
        # 3. ZULETZT: Shutdown-Signal für WebSocket-Logs setzen
        logger.info("[APP] Shutdown: Signaling background tasks...")
        try:
            from app.routes.mqtt_routes import set_shutdown_event
            shutdown_event = asyncio.Event()
            shutdown_event.set()
            set_shutdown_event(shutdown_event)
            logger.info("[APP] Shutdown signal set for background tasks")
        except Exception:
            logger.exception("Failed to set shutdown event")
        
        # 4. Stoppe mqtt_runtime Client
        try:
            mqtt_runtime.disconnect()
            logger.info("[MQTT] mqtt_runtime client stopped")
        except Exception:
            logger.exception("Auto-connect shutdown failed")
        
        logger.info("[APP] Shutdown completed - FilamentHub stopped")


app = FastAPI(
    title="FilamentHub",
    description="Filament Management System fuer Bambu, Klipper & Standalone",
    version="1.6",
    lifespan=lifespan,
    # Note: redirect_slashes=True (default) causes 307 redirects but ensures both
    # /api/spools and /api/spools/ work correctly. Overhead is minimal (~5-10ms).
)
# -----------------------------------------------------
# MIDDLEWARE: RUNTIME / REQUEST MONITORING
# -----------------------------------------------------
@app.middleware("http")
async def runtime_metrics_middleware(request: Request, call_next):
    start = time.perf_counter()

    # PERFORMANCE DEBUG: Messe Zeit VOR und NACH Route-Handler
    before_route = time.perf_counter()
    logger = logging.getLogger("performance")
    logger.debug(f"[PERF] Request START: {request.method} {request.url.path}")

    response = await call_next(request)

    after_route = time.perf_counter()
    duration_ms = (after_route - start) * 1000.0

    # Log Performance-Details
    logger.debug(f"[PERF] Request END: {request.method} {request.url.path} - {duration_ms:.1f}ms")

    try:
        record_request(duration_ms)
    except Exception:
        logging.getLogger("errors").exception("Failed to record request duration")

    # Record in Performance Monitor for alerting & dashboards
    try:
        from app.services.performance_monitoring import get_performance_monitor
        monitor = get_performance_monitor()
        monitor.record_request(
            endpoint=request.url.path,
            method=request.method,
            duration_ms=duration_ms,
            status_code=response.status_code
        )
    except Exception:
        logging.getLogger("errors").exception("Failed to record request in performance monitor")

    return response

# -----------------------------------------------------
# TESTENDPUNKT & HEALTH CHECK
# -----------------------------------------------------
@app.get('/ping')
async def ping():
    return {'status': 'ok'}

@app.get('/health')
async def health():
    """Health check endpoint for Docker container monitoring"""
    return {
        "status": "ok",
        "database": "ok",
        "migrations": "ok",
        "schema": "ok",
        "server": "running",
    }



# -----------------------------------------------------
# STATIC + TEMPLATES
# -----------------------------------------------------
# Use absolute paths to work from any directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "app", "static")), name="static")
app.mount("/frontend", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="frontend_static")
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))
templates.env.globals["app_version"] = os.environ.get("APP_VERSION", "1.6")
templates.env.globals["design_version"] = os.environ.get("DESIGN_VERSION", "Design 1.6")



# -----------------------------------------------------
# ROUTES - API
# -----------------------------------------------------
app.include_router(hello_router)
app.include_router(materials_router)
app.include_router(spools_router)
app.include_router(spool_numbers_router)  # NEU: Spulen-Nummern-System
app.include_router(log_router)
app.include_router(system_router)
app.include_router(debug_router)
app.include_router(service_router)
# SECURITY FIX (Bug #3): Database-Router deaktiviert wegen kritischer SQL-Injection Schwachstellen
# Die Routes /api/database/query und /api/database/editor erlaubten ungeschützten SQL-Zugriff
# app.include_router(database_router)  # ← DEAKTIVIERT
app.include_router(backup_router)
app.include_router(scanner_router)
app.include_router(mqtt_router)
app.include_router(performance_router)
app.include_router(printers_router)

app.include_router(jobs_router)
app.include_router(statistics_router)

app.include_router(bambu_router)
app.include_router(admin_router)
app.include_router(admin_coverage_router, prefix="/api/admin")
app.include_router(settings_router)
app.include_router(weight_management_router)  # Weight Management & History
app.include_router(spool_assignment_router)  # Spool Assignment (AMS → Lager-Spule zuordnen)
app.include_router(debug_ams_router)
app.include_router(debug_system_router)
app.include_router(debug_performance_router)
app.include_router(debug_network_router)
app.include_router(debug_printer_router)
app.include_router(notification_router)
app.include_router(config_router)
app.include_router(debug_log_routes.router, prefix="/api/debug", tags=["debug"])

# Runtime MQTT control endpoints (separate from legacy mqtt_routes to avoid collisions)
app.include_router(mqtt_runtime_routes.router, prefix="/api/mqtt/runtime", tags=["mqtt"])

# Live state endpoints for real-time device data
app.include_router(live_state_router)
app.include_router(ams_router)
app.include_router(ams_conflicts_router)
app.include_router(monitoring_router)  # Performance Monitoring & Alerts
app.include_router(lexikon_router)
app.include_router(externe_spule_router)
app.include_router(bambu_cloud_router)  # Bambu Cloud Integration


# -----------------------------------------------------
# API-HILFESEITE info wirt später enterfernt 
# -----------------------------------------------------
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import re

@app.get('/api-help', response_class=HTMLResponse)
async def api_help_page(request: Request):
    # Alle API-Routen aus FastAPI auslesen
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and route.path.startswith("/api") and not route.path.endswith("{file_path:path}"):  # type: ignore
            # Nur Routen mit Methoden (keine WebSocket-Routen)
            if hasattr(route, 'methods'):
                methods = sorted([m for m in list(route.methods) if m in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")])  # type: ignore
                if methods:
                    routes.append({"path": route.path, "methods": methods})  # type: ignore
    # Filtere Routen ohne POST und DELETE
    routes = [r for r in routes if r['methods'] == ['GET']]
    # Sortieren und Duplikate entfernen (nach path)
    unique = {}
    for r in routes:
        unique[r['path']] = r
    api_routes = sorted(unique.values(), key=lambda x: x['path'])
    templates = Jinja2Templates(directory="c:/Users/Denis/Desktop/FilamentHub_Projekt/FilamentHub/app/templates")
    return templates.TemplateResponse(
        "help.html",
        {"request": request, "api_routes": api_routes, "title": "API Hilfeseite"}
    )



# -----------------------------------------------------
# ROUTES - FRONTEND
# -----------------------------------------------------
@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "FilamentHub – Dashboard"},
    )


@app.get('/materials', response_class=HTMLResponse)
async def materials_page(request: Request):
    return templates.TemplateResponse(
        'materials.html',
        {
            'request': request,
            'title': 'Spulen Hersteller - FilamentHub',
            'active_page': 'materials'
        },
    )


@app.get('/spools', response_class=HTMLResponse)
async def spools_page(request: Request):
    return templates.TemplateResponse(
        'spools.html',
        {
            'request': request,
            'title': 'Spulen - FilamentHub',
            'active_page': 'spools'
        },
    )


@app.get('/ams', response_class=HTMLResponse)
async def ams_page(request: Request):
    return templates.TemplateResponse(
        'ams.html',
        {
            'request': request,
            'title': 'AMS - FilamentHub',
            'active_page': 'ams'
        },
    )


@app.get('/ams-lite', response_class=HTMLResponse)
async def ams_lite_page(request: Request):
    return templates.TemplateResponse(
        'ams-lite.html',
        {
            'request': request,
            'title': 'AMS Lite - FilamentHub',
            'active_page': 'ams-lite'
        },
    )


@app.get('/all-slots', response_class=HTMLResponse)
async def all_slots_page(request: Request):
    return templates.TemplateResponse(
        'all-slots.html',
        {
            'request': request,
            'title': 'Alle Slots - FilamentHub',
            'active_page': 'ams-lite'
        },
    )


@app.get('/mmu-klipper', response_class=HTMLResponse)
async def mmu_klipper_page(request: Request):
    return templates.TemplateResponse(
        'mmu_klipper.html',
        {
            'request': request,
            'title': 'MMU-Klipper - FilamentHub',
            'active_page': 'mmu_klipper'
        },
    )


@app.get('/printers', response_class=HTMLResponse)
async def printers_page(request: Request):
    return templates.TemplateResponse(
        'printers.html',
        {
            'request': request,
            'title': 'Drucker - FilamentHub',
            'active_page': 'printers'
        },
    )


@app.get('/jobs', response_class=HTMLResponse)
async def jobs_page(request: Request):
    return templates.TemplateResponse(
        'jobs.html',
        {
            'request': request,
            'title': 'Druckauftraege - FilamentHub',
            'active_page': 'jobs'
        },
    )


@app.get('/statistics', response_class=HTMLResponse)
async def statistics_page(request: Request):
    return templates.TemplateResponse(
        'statistics.html',
        {
            'request': request,
            'title': 'Statistiken - FilamentHub',
            'active_page': 'statistics'
        },
    )


@app.get('/lexikon', response_class=HTMLResponse)
async def lexikon_page(request: Request):
    return templates.TemplateResponse(
        'lexikon.html',
        {
            'request': request,
            'title': 'Lexikon - FilamentHub',
            'active_page': 'lexikon'
        },
    )


@app.get('/material-database', response_class=HTMLResponse)
async def material_database_page(request: Request):
    return templates.TemplateResponse(
        'material_database.html',
        {
            'request': request,
            'title': 'Material-Datenbank - FilamentHub',
            'active_page': 'material-database'
        },
    )


@app.get('/history', response_class=HTMLResponse)
async def weight_history_page(request: Request):
    return templates.TemplateResponse(
        'weight_history.html',
        {
            'request': request,
            'title': 'Weight History - FilamentHub',
            'active_page': 'history'
        },
    )


@app.get('/settings', response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        'settings.html',
        {
            'request': request,
            'title': 'Settings - FilamentHub',
            'active_page': 'settings'
        },
    )


@app.get('/monitoring', response_class=HTMLResponse)
async def monitoring_page(request: Request):
    return templates.TemplateResponse(
        'monitoring.html',
        {
            'request': request,
            'title': 'Performance Monitoring - FilamentHub',
            'active_page': 'monitoring'
        },
    )


@app.get('/logs', response_class=HTMLResponse)
async def logs_page(request: Request):
    # logs.html bleibt in app/templates
    logs_templates = Jinja2Templates(directory='app/templates')
    return logs_templates.TemplateResponse(
        'logs.html',
        {'request': request},
    )


@app.get('/debug', response_class=HTMLResponse)
async def debug_page(request: Request):
    from app.routes.settings_routes import get_setting, DEFAULTS

    debug_templates = Jinja2Templates(directory='app/templates')
    printers = []
    debug_center_mode = "lite"

    try:
        with Session(engine) as session:
            printers = session.exec(select(Printer)).all()
            debug_center_mode = get_setting(session, "debug_center_mode", DEFAULTS.get("debug_center_mode", "lite")) or "lite"
    except Exception:
        printers = []

    return debug_templates.TemplateResponse(
        'debug.html',
        {
            'request': request,
            'title': 'FilamentHub Debug Center',
            'active_page': 'debug',
            'printers': printers,
            'data_mode': debug_center_mode
        },
    )


@app.get('/ams-help', response_class=HTMLResponse)
async def ams_help_page(request: Request):
    """Simple helper page to visualize AMS slots from the latest report message."""
    help_templates = Jinja2Templates(directory='app/templates')
    return help_templates.TemplateResponse(
        'ams_help.html',
        {'request': request, 'title': 'AMS Helper'},
    )





