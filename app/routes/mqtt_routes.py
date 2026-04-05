import asyncio

import os

import time
import threading

from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
import json
import ssl
import logging
import yaml
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Sequence, Set, List, cast
import paho.mqtt.client as mqtt
from sqlmodel import select, Session
from app.database import get_session
from services.printer_service import PrinterService

import sqlalchemy as sa

from app.services import mqtt_runtime
 
from pydantic import BaseModel
from fastapi import Request

from app.services.mqtt_payload_processor import process_mqtt_payload
from app.services.ams_parser import parse_ams, _to_int
from app.services.job_parser import parse_job
from app.services.universal_mapper import UniversalMapper
from app.services.printer_auto_detector import PrinterAutoDetector
from app.services.live_state import set_live_state
from app.services.ams_sync import sync_ams_slots
from app.services.job_tracking_service import job_tracking_service

from app.models.printer import Printer
from app.services.spool_number_service import assign_spool_number
from services.mqtt_protocol_detector import MQTTProtocolDetector

# ...existing code...

router = APIRouter(prefix="/api/mqtt", tags=["MQTT"])

# === AUTO-CONNECT STARTUP HELPER (Multi-Printer Support) ===
def startup_connect_printer(printer) -> bool:
    """
    Synchrone Funktion zum Verbinden eines Druckers beim Server-Start.
    Verwendet für auto_connect Drucker. Multi-Printer-fähig!
    Returns: True bei Erfolg, False bei Fehler
    """
    global printer_service_ref
    logger = logging.getLogger("mqtt")
    
    # Ensure printer_service_ref is available
    if printer_service_ref is None:
        from services.printer_service import get_printer_service
        printer_service_ref = get_printer_service()
        if printer_service_ref:
            logger.info("[MQTT] printer_service_ref initialized from get_printer_service()")
    
    try:
        from app.services.printer_auto_detector import PrinterAutoDetector
        
        # Verbindungs-Parameter
        connection_id = f"{printer.ip_address}:8883_{printer.id}"
        
        # Protokoll-Erkennung basierend auf Modell
        mqtt_protocol = mqtt.MQTTv311  # Default
        if printer.cloud_serial:
            model = PrinterAutoDetector.detect_model_from_serial(printer.cloud_serial)
            if model and model.upper() in PrinterAutoDetector.MODEL_MQTT_PROTOCOL:
                protocol_str = PrinterAutoDetector.MODEL_MQTT_PROTOCOL[model.upper()]
                if protocol_str == "5":
                    mqtt_protocol = mqtt.MQTTv5
                    logger.info(f"[MQTT] Drucker {printer.name} → MQTT v5")
                elif protocol_str == "311":
                    mqtt_protocol = mqtt.MQTTv311
                    logger.info(f"[MQTT] Drucker {printer.name} → MQTT v3.1.1")
        
        # Neuen Client erstellen
        client = mqtt.Client(
            client_id=f"filamenthub_{printer.name}_{str(printer.id)[:6]}",
            protocol=mqtt_protocol
        )
        
        # Callbacks setzen - MQTTv5 hat andere Signatur!
        def on_connect_startup(client, userdata, flags, rc_or_reason, properties=None):
            # rc_or_reason: bei v3.1.1 ist es int, bei v5 ist es ReasonCode object
            rc_value = rc_or_reason if isinstance(rc_or_reason, int) else rc_or_reason.value
            if rc_value == 0:
                logger.info(f"✓ Auto-connect: {printer.name} verbunden (protocol={'v5' if mqtt_protocol == mqtt.MQTTv5 else 'v3.1.1'})")
                # Subscribe zum device topic
                topic = f"device/{printer.cloud_serial}/report"
                result = client.subscribe(topic, qos=1)
                logger.info(f"[MQTT] Subscribe to {topic} → result={result}")
                
                # ✅ CRITICAL: Send pushall to get all data (AMS, job status, temps, etc.)
                try:
                    request_topic = f"device/{printer.cloud_serial}/request"
                    pushall_cmd = json.dumps({"pushing": {"sequence_id": "1", "command": "pushall"}})
                    client.publish(request_topic, pushall_cmd)
                    logger.info(f"[MQTT] Sent pushall to {request_topic} for {printer.name}")
                except Exception as e:
                    logger.exception(f"[MQTT] Failed to send pushall for {printer.name}: {e}")
            else:
                logger.error(f"✗ Auto-connect: {printer.name} fehlgeschlagen (rc={rc_value})")
        
        client.on_connect = on_connect_startup
        client.on_message = lambda c, u, msg: on_message(c, u, msg)  # Forward to global handler
        client.on_disconnect = lambda c, u, rc, props=None: on_disconnect(c, u, rc, props)
        
        # User data setzen
        client.user_data_set({
            "connection_id": connection_id,
            "client_id": client._client_id.decode() if isinstance(client._client_id, bytes) else client._client_id,
            "cloud_serial": printer.cloud_serial,
        })
        
        # TLS konfigurieren
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        
        # Credentials
        client.username_pw_set("bblp", printer.api_key)
        
        # Register printer in service (needed for set_connected to work)
        # Note: printer_service_ref is initialized during app startup
        # At this point it should be available, so we can use it directly
        print(f"[DEBUG] printer_service_ref = {printer_service_ref}, cloud_serial = {printer.cloud_serial}")
        if printer_service_ref and printer.cloud_serial:
            try:
                printer_service_ref.register_printer(
                    key=printer.cloud_serial,
                    name=printer.name,
                    model=printer.model or "X1C",
                    printer_id=str(printer.id),
                    source="startup_auto_connect"
                )
                print(f"[DEBUG] ✓ Registered {printer.name} in service")
                logger.info(f"[MQTT] Drucker {printer.name} im Service registriert (cloud_serial={printer.cloud_serial})")
            except Exception as e:
                print(f"[DEBUG] ✗ Failed to register: {e}")
                logger.warning(f"Could not register printer {printer.name} in service: {e}")
        else:
            print(f"[DEBUG] ✗ Cannot register: printer_service_ref={printer_service_ref is not None}, has cloud_serial={printer.cloud_serial is not None}")
        
        # Verbinden
        logger.info(f"[MQTT] Connecting {printer.name} ({printer.ip_address}:8883)...")
        client.connect(printer.ip_address, 8883, 60)
        
        # Loop starten
        client.loop_start()
        
        # Client speichern - WICHTIG: Dadurch Multi-Printer-fähig!
        mqtt_clients[connection_id] = client
        
        # Update mqtt_runtime state for Debug UI
        try:
            from app.services import mqtt_runtime
            now = datetime.now(timezone.utc)
            ts = now.isoformat()
            mqtt_runtime._runtime_state.update({
                "connected": True,
                "connected_since": ts,
                "last_seen": ts,
                "broker": printer.ip_address,
                "port": 8883,
                "client_id": client._client_id.decode() if isinstance(client._client_id, bytes) else str(client._client_id),
                "cloud_serial": printer.cloud_serial,
                "protocol": "311" if mqtt_protocol == mqtt.MQTTv311 else "5",
                "qos": 1,
            })
            mqtt_runtime._client_instance = client
            mqtt_runtime._transport_connected_since = now
            logger.info(f"[MQTT] Runtime state updated for {printer.name}")
        except Exception as e:
            logger.warning(f"[MQTT] Could not update runtime state: {e}")
        
        logger.info(f"✓ {printer.name} MQTT-Client gestartet (ID: {connection_id})")
        return True
        
    except Exception as e:
        logger.exception(f"Auto-connect fehlgeschlagen für {printer.name}: {e}")
        return False

# ...existing code...

mqtt_ws_clients = set()

# ============================================================
# SHUTDOWN SIGNAL - für graceful shutdown aller Background-Tasks
# ============================================================
_shutdown_event: Optional[asyncio.Event] = None
_shutdown_lock = threading.Lock()  # Thread-safe Flag-Zugriff
_is_shutting_down: bool = False  # Flag um on_message() zu stoppen

def set_shutdown_event(event: asyncio.Event):
    """Called by main.py lifespan to signal shutdown."""
    global _shutdown_event, _is_shutting_down
    with _shutdown_lock:
        _shutdown_event = event
        _is_shutting_down = True  # SOFORT: Stoppe MQTT Verarbeitung!

# ...alle bisherigen Routen und Funktionen...



@router.websocket("/ws/logs/{module}")

async def websocket_logs(websocket: WebSocket, module: str):

    await websocket.accept()

    log_file_map = {
        "app": "logs/app/app.log",
        "bambu": "logs/bambu/bambu.log",
        "klipper": "logs/klipper/klipper.log",
        "errors": "logs/errors/errors.log",
        "mqtt": "logs/mqtt/mqtt_messages.log",
    }

    log_file = log_file_map.get(module)

    try:
        # Optional: nur die letzten N Zeilen senden (tail). Default: 0 = keine Historie
        tail_param = websocket.query_params.get("tail", "0") if hasattr(websocket, "query_params") else "0"
        try:
            tail = int(tail_param)
        except Exception:
            logging.getLogger("mqtt").exception("Invalid tail parameter for log websocket: %s", tail_param)
            tail = 0

        last_size = 0
        if log_file and os.path.exists(log_file):
            # Falls tail > 0 angefordert wurde, sende letzte N Zeilen; ansonsten überspringe Historie
            if tail > 0:
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        dq = deque(f, maxlen=tail)
                    for line in dq:
                        await websocket.send_text(line.strip())
                except Exception:
                    logging.getLogger("mqtt").exception("Failed to send initial log tail for module=%s", module)
            # setze Startposition auf Dateiende, damit keine Historie erneut gesendet wird
            try:
                last_size = os.path.getsize(log_file)
            except Exception:
                logging.getLogger("mqtt").exception("Failed to get log file size for module=%s", module)
                last_size = 0

        while True:

            if log_file:

                try:

                    with open(log_file, "r", encoding="utf-8") as f:

                        f.seek(last_size)

                        new_lines = f.readlines()

                        last_size = f.tell()

                        for line in new_lines:

                            await websocket.send_text(line.strip())

                except FileNotFoundError:

                    logging.getLogger("mqtt").exception("Log file not found for module=%s during websocket stream", module)

            # ✅ Shutdown-Signal prüfen (beende Schleife bei Shutdown)
            if _shutdown_event and _shutdown_event.is_set():
                logging.getLogger("mqtt").info("Websocket logs shutdown signal received for module=%s", module)
                break
            
            await asyncio.sleep(1)

    except WebSocketDisconnect as exc:
        logging.getLogger("mqtt").info("Log websocket disconnected for module=%s: %s", module, exc)
        return
from app.models.job import Job, JobSpoolUsage

from sqlmodel import select

from app.models.spool import Spool

from app.models.material import Material

from services.printer_service import PrinterService



# Wichtig: KEINE zweite Router-Initialisierung  wir verwenden den oben definierten `router`.



# === MQTT LOGGER SETUP ===

def get_mqtt_logger():
    """Gibt den zentralen MQTT-Logger zurück (Handler wird zentral konfiguriert)."""
    return logging.getLogger("mqtt")



mqtt_message_logger = get_mqtt_logger()


def _truncate_payload(payload: str, limit: int) -> str:
    if payload is None:
        return ""
    if len(payload) <= limit:
        return payload
    return payload[:limit] + "...[truncated]"


def _payload_preview(payload: str, limit: int = 300) -> str:
    return _truncate_payload(payload, limit)


def _preview_obj(value, limit: int = 300) -> str:
    return _truncate_payload(str(value), limit)



# === MODELS ===

class MQTTConnection(BaseModel):

    broker: str

    port: int = 1

    username: Optional[str] = None

    password: Optional[str] = None

    client_id: Optional[str] = "filamenthub_debug"

    cloud_serial: Optional[str] = None  # bevorzugte Serial f�r Default-Topic

    use_tls: bool = False

    tls_insecure: bool = True  # Self-signed / printer certs erlauben



class MQTTSubscription(BaseModel):

    topic: str



class MQTTMessage(BaseModel):

    topic: str

    payload: str

    timestamp: str

    qos: int = 0



# === GLOBAL STATE ===

mqtt_clients: Dict[str, mqtt.Client] = {}

active_connections: Set[WebSocket] = set()

active_ws_clients: int = 0

last_ws_activity_ts: Optional[float] = None

message_buffer: List[MQTTMessage] = []

MAX_BUFFER_SIZE = 1000

# Default-Topic nicht mehr statisch hinterlegen; wird dynamisch aus client_id abgeleitet

DEFAULT_TOPIC = None

subscribed_topics: Set[str] = set()

event_loop: Optional[asyncio.AbstractEventLoop] = None

# Job-Tracking wird zentral über job_tracking_service verwaltet (siehe app/services/job_tracking_service.py)

last_connect_error: Optional[int] = None  # letzter RC bei fehlgeschlagener Verbindung

printer_service_ref: Optional[PrinterService] = None


# === MQTT CALLBACKS ===

def on_connect(client, userdata, flags, rc, properties=None):

    """Callback when connected to MQTT broker"""

    connection_id = userdata.get('connection_id', 'unknown')

    global last_connect_error

    if rc == 0:

        last_connect_error = None

        print(f"[MQTT] Connected: {connection_id}")

        # Default-Topic: bei Bambu ausschließlich cloud_serial verwenden.
        # Kein Fallback auf client_id, um falsche Topics zu vermeiden.

        default_topic = None
        cserial = None  # Initialisiere außerhalb try-Block

        try:

            cserial = userdata.get('cloud_serial') if userdata else None

            if cserial:

                default_topic = f"device/{cserial}/report"

        except Exception:

            logging.getLogger("mqtt").exception("Failed to resolve default MQTT topic from userdata")
            default_topic = None

        if not subscribed_topics and default_topic:

            print(f"Abonniere Default-Topic: {default_topic}")

            client.subscribe(default_topic)

            subscribed_topics.add(default_topic)
            try:
                mqtt_runtime.register_subscription(default_topic)
            except Exception:
                logging.getLogger("mqtt").exception("Failed to register default subscription %s", default_topic)

        elif subscribed_topics:

            for topic in subscribed_topics:

                print(f"Abonniere MQTT-Topic: {topic}")

                client.subscribe(topic)
                try:
                    mqtt_runtime.register_subscription(topic)
                except Exception:
                    logging.getLogger("mqtt").exception("Failed to register subscription %s", topic)

        # ✅ CRITICAL: Send pushall on EVERY connect/reconnect to refresh all data
        # This is essential for job tracking - if disconnected during a print,
        # we need all current state (progress, temps, layers, etc.) to resume tracking
        if default_topic and cserial:
            try:
                request_topic = f"device/{cserial}/request"
                pushall_cmd = json.dumps({"pushing": {"sequence_id": "1", "command": "pushall"}})
                client.publish(request_topic, pushall_cmd)
                print(f"[MQTT] Sent pushall command to {request_topic} (connect/reconnect)")
                mqtt_message_logger.info(f"[MQTT] pushall sent for reconnect: serial={cserial}")
            except Exception:
                logging.getLogger("mqtt").exception("Failed to send pushall command for serial=%s", cserial)

    else:

        last_connect_error = rc

        print(f"[MQTT] Connection failed (rc={rc})")

        # Fehlschlag: vorhandene Subscriptions leeren, damit Status korrekt ist

        subscribed_topics.clear()
        try:
            mqtt_runtime.clear_subscriptions()
        except Exception:
            logging.getLogger("mqtt").exception("Failed to clear MQTT runtime subscriptions after connect failure")

        try:

            client.disconnect()

            client.loop_stop()

        except Exception:

            logging.getLogger("mqtt").exception("Failed to disconnect MQTT client after connect failure")

        try:

            cid = userdata.get('connection_id') if userdata else None

            if cid and cid in mqtt_clients:

                del mqtt_clients[cid]

        except Exception:

            logging.getLogger("mqtt").exception("Failed to remove MQTT client after connect failure")





def on_message(client, userdata, msg):

    """Callback when message received"""
    
    # ⚠️ KRITISCH: Während Shutdown KEINE Nachrichten verarbeiten
    global _is_shutting_down
    with _shutdown_lock:
        if _is_shutting_down:
            return  # Abbrechen ohne zu verarbeiten

    # Update mqtt_runtime statistics for Debug UI
    try:
        from app.services import mqtt_runtime
        ts = datetime.now(timezone.utc).isoformat()
        
        # Increment message count
        current_count = mqtt_runtime._runtime_state.get("message_count", 0)
        mqtt_runtime._runtime_state["message_count"] = current_count + 1
        mqtt_runtime._runtime_state["last_message_time"] = ts
        mqtt_runtime._runtime_state["last_seen"] = ts
        mqtt_runtime._runtime_state["connected"] = True
        
        # Track subscriptions (unique topics)
        topic = msg.topic
        if "subscribed_topics" not in mqtt_runtime._runtime_state:
            mqtt_runtime._runtime_state["subscribed_topics"] = set()
        mqtt_runtime._runtime_state["subscribed_topics"].add(topic)
        mqtt_runtime._runtime_state["subscriptions_count"] = len(mqtt_runtime._runtime_state["subscribed_topics"])
    except Exception:
        pass  # Don't let stats tracking break message processing

    try:
        # Ensure variables are always defined for static analysis
        cloud_serial_from_topic = None
        printer_model_for_mapper = None
        printer_name_for_service = None
        # raw payload text
        payload = msg.payload.decode('utf-8', errors='replace')
        # Delegate payload parsing and mapping to dedicated processor
        try:
            proc = process_mqtt_payload(msg.topic, payload, printer_service_ref)
            parsed_json = proc.get("raw")
            ams_data = proc.get("ams") or []
            job_data = proc.get("job") or {}
            mapped_obj = proc.get("mapped")
            mapped_dict = proc.get("mapped_dict")
            caps = proc.get("capabilities")
            if proc.get("serial"):
                cloud_serial_from_topic = proc.get("serial")
        except Exception:
            logging.getLogger("mqtt").exception("Failed to process MQTT payload for topic=%s", msg.topic)
            parsed_json = None
            ams_data = []
            job_data = {}
            mapped_obj = None
            mapped_dict = None
            caps = None

        try:
            parts = msg.topic.split("/")
            if len(parts) >= 2 and parts[0] == "device":
                cloud_serial_from_topic = parts[1]
        except Exception:
            logging.getLogger("mqtt").exception("Failed to parse MQTT topic for serial: %s", msg.topic)

        try:

            parsed_json = json.loads(payload)

            if msg.topic.endswith("/report"):

                ams_data = parse_ams(parsed_json)

                job_data = parse_job(parsed_json) or {}

                # Update in-memory live-state for this device if we have a cloud_serial
                try:
                    if cloud_serial_from_topic:
                        set_live_state(cloud_serial_from_topic, parsed_json)
                    else:
                        print(f"[MQTT] WARNING: No cloud_serial_from_topic for {msg.topic}")
                except Exception:
                    logging.getLogger("mqtt").exception("set_live_state failed for topic=%s", msg.topic)

        except Exception:
            logging.getLogger("mqtt").exception("Failed to parse MQTT JSON payload for topic=%s", msg.topic)
            parsed_json = None



                # Schreibe die Nachricht in MQTT-Log (RotatingFileHandler ?bernimmt Rotation)

        try:
            payload_len = len(payload) if payload is not None else 0
            preview = _payload_preview(payload, limit=300)
            mqtt_message_logger.info(
                "Topic=%s | PayloadLen=%s | Preview=%s",
                msg.topic,
                payload_len,
                preview,
            )

        except Exception as logerr:
            logging.getLogger("mqtt").exception("Failed to write MQTT message log for topic=%s", msg.topic)



        # Sende empfangene MQTT-Nachricht an alle verbundenen WebSocket-Clients (Text-Log)

        if event_loop:
            for ws in list(mqtt_ws_clients):
                try:
                    payload_len = len(payload) if payload is not None else 0
                    preview = _truncate_payload(payload, limit=1000)
                    _safe_schedule(
                        ws.send_text(
                            f"{datetime.now().isoformat()} | Topic={msg.topic} | PayloadLen={payload_len} | Payload={preview}"
                        ),
                        event_loop,
                    )
                except Exception:
                    logging.getLogger("mqtt").exception("Failed to forward MQTT message to websocket client")



        message = MQTTMessage(

            topic=msg.topic,

            payload=payload,

            timestamp=datetime.now().isoformat(),

            qos=msg.qos

        )

        printer_id_for_ams = None

        printer_obj = None

        caps = None

        if cloud_serial_from_topic:

            try:

                with next(get_session()) as session:

                    p = session.exec(select(Printer).where(Printer.cloud_serial == cloud_serial_from_topic)).first()

                    if p:

                        printer_obj = p

                        printer_id_for_ams = p.id

                        printer_name_for_service = p.name

                        printer_model_for_mapper = p.model or "X1C"
                        if printer_service_ref and cloud_serial_from_topic not in printer_service_ref.printers:
                            try:
                                printer_service_ref.register_printer(
                                    key=cloud_serial_from_topic,
                                    name=p.name,
                                    model=p.model or "X1C",
                                    printer_id=p.id,
                                    source="mqtt_message",
                                )
                            except Exception:
                                logging.getLogger("mqtt").exception(
                                    "Failed to register printer in service for serial=%s",
                                    cloud_serial_from_topic,
                                )

            except Exception:

                logging.getLogger("mqtt").exception("Failed to load printer by cloud_serial=%s", cloud_serial_from_topic)
                printer_id_for_ams = None

        if cloud_serial_from_topic and printer_service_ref:
            try:
                ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                # Mark printer as connected when receiving MQTT messages
                print(f"[DEBUG] Calling set_connected for {cloud_serial_from_topic}")
                printer_service_ref.set_connected(cloud_serial_from_topic, True, ts)
                printer_service_ref.mark_seen(cloud_serial_from_topic, ts)
                print(f"[DEBUG] ✓ set_connected successful for {cloud_serial_from_topic}")
            except Exception as e:
                print(f"[DEBUG] ✗ set_connected failed: {e}")
                logging.getLogger("mqtt").exception(
                    "Failed to mark printer as seen/connected for serial=%s",
                    cloud_serial_from_topic,
                )
        else:
            if not cloud_serial_from_topic:
                print(f"[DEBUG] ✗ No cloud_serial_from_topic in message")
            if not printer_service_ref:
                print(f"[DEBUG] ✗ printer_service_ref is None in on_message")

        if parsed_json:

            try:

                # Modell-Determination (PRIORITÄT):
                # 1. Aus DB wenn Drucker bereits bekannt (Single Source of Truth!)
                # 2. Autoerkennung nur als Fallback
                if printer_obj and printer_obj.model:
                    final_model = printer_obj.model.upper()
                    print(f"[MQTT] Using model from DB: {final_model}")
                else:
                    # Fallback: Autoerkennung
                    detected_model = PrinterAutoDetector.detect_model_from_payload(parsed_json) or PrinterAutoDetector.detect_model_from_serial(getattr(printer_obj, "cloud_serial", None))
                    final_model = detected_model or printer_model_for_mapper or "UNKNOWN"
                    print(f"[MQTT] Auto-detected model: {final_model}")

                # Update nur wenn sich Modell changed und Drucker noch registriert ist
                if printer_obj and final_model != (printer_obj.model or "").upper():


                    printer_obj.model = final_model

                    try:

                        with next(get_session()) as session:

                            session.add(printer_obj)

                            session.commit()

                    except Exception:
                        logging.getLogger("mqtt").exception(
                            "Failed to persist printer model update for serial=%s",
                            cloud_serial_from_topic,
                        )

                printer_model_for_mapper = final_model

                caps = PrinterAutoDetector.detect_capabilities(parsed_json)

                mapper = UniversalMapper(printer_model_for_mapper)

                mapped_obj = mapper.map(parsed_json)

                mapped_dict = mapped_obj.to_dict()

                if mapped_dict and mapped_dict.get("job"):

                    job_data = mapped_dict.get("job")

                if printer_service_ref:
                    # Prefer cloud_serial as key. If no serial is present, ignore updates.
                    if cloud_serial_from_topic:
                        printer_service_ref.update_printer(cloud_serial_from_topic, mapped_obj)
                        if caps:
                            printer_service_ref.update_capabilities(cloud_serial_from_topic, caps)
                    else:
                        print("[MQTT] Received mapped data without cloud_serial; update skipped")

                if caps and isinstance(mapped_dict, dict):

                    mapped_dict["capabilities"] = caps

            except Exception:
                logging.getLogger("mqtt").exception("Failed to map MQTT payload for serial=%s", cloud_serial_from_topic)
                mapped_dict = None

        # AMS Sync vor Job-Tracking, damit Tag/Slot-Daten in DB stehen

        if not ams_data and mapped_dict and mapped_dict.get("ams") is not None:

            ams_data = mapped_dict.get("ams")

        if ams_data:

            try:

                mqtt_message_logger.info(f"[AMS SYNC] printer_id={printer_id_for_ams} ams_count={len(ams_data) if isinstance(ams_data, list) else 0}")

                # Debug: log raw ams_data for test visibility
                try:
                    mqtt_message_logger.info(f"[AMS SYNC] payload_preview={_preview_obj(ams_data, limit=300)}")
                except Exception:
                    logging.getLogger("mqtt").exception("Failed to log AMS payload for printer_id=%s", printer_id_for_ams)

                sync_ams_slots(
                    [dict(unit) for unit in ams_data] if isinstance(ams_data, list) else [],
                    printer_id=printer_id_for_ams,
                    auto_create=True
                ) if ams_data else None

                mqtt_message_logger.info(f"[AMS SYNC] done printer_id={printer_id_for_ams}")

            except Exception as sync_err:

                logging.getLogger("mqtt").exception("AMS sync failed for printer_id=%s", printer_id_for_ams)

            # Fallback for tests/environments where sync_ams_slots didn't create records:
            # If we still have no Material rows, create a minimal Material + Spool
            try:
                from app.database import get_session as _get_session
                from app.models.material import Material as _Material
                from app.models.spool import Spool as _Spool
                created = False
                with next(_get_session()) as _session:
                    existing_mat = _session.exec(select(_Material)).first()
                    if not existing_mat and isinstance(ams_data, list) and ams_data:
                        # Try to construct from first tray
                        first_unit = ams_data[0]
                        trays = first_unit.get("trays") or first_unit.get("tray") or []
                        if trays and isinstance(trays, list):
                            t = trays[0]
                            tray_type = t.get("tray_type") or t.get("material")
                            tray_color = t.get("tray_color") or t.get("color")
                            mat = _Material(
                                name=tray_type or "Unknown",
                                brand="Bambu Lab",
                                density=1.24,
                                diameter=1.75,
                            )
                            _session.add(mat)
                            _session.commit()
                            _session.refresh(mat)
                            # create spool
                            ams_slot = None
                            try:
                                ams_slot = _to_int(t.get("tray_id"))
                            except Exception:
                                logging.getLogger("mqtt").exception("Failed to parse AMS tray_id into slot")
                                ams_slot = None
                            now = datetime.now().isoformat()
                            sp = _Spool(
                                material_id=mat.id,
                                printer_id=printer_id_for_ams,
                                ams_id=None,
                                ams_slot=ams_slot,
                                last_slot=ams_slot,
                                tag_uid=t.get("tag_uid"),
                                tray_uuid=t.get("tray_uuid"),
                                tray_color=tray_color,
                                tray_type=tray_type,
                                remain_percent=float(t.get("remain_percent") or t.get("remain") or 0.0),
                                weight_current=None,
                                last_seen=now,
                                first_seen=now,
                                used_count=0,
                                label=f"AMS Slot {ams_slot}" if ams_slot is not None else None,
                                status="Aktiv",
                                is_open=True,
                                ams_source="rfid",
                                assigned=True,
                                is_active=True,
                            )
                            _session.add(sp)
                            _session.commit()
                            created = True
                if created:
                    mqtt_message_logger.info("[AMS SYNC] fallback created material+spool")
            except Exception:
                logging.getLogger("mqtt").exception("Failed to run AMS fallback material/spool creation")




        # ============================================================
        # JOB-TRACKING SYSTEM (Zentral über job_tracking_service)
        # ============================================================
        if parsed_json and msg.topic.endswith("/report") and cloud_serial_from_topic:
            try:
                result = job_tracking_service.process_message(
                    cloud_serial=cloud_serial_from_topic,
                    parsed_payload=parsed_json,
                    printer_id=printer_id_for_ams,
                    ams_data=[dict(unit) for unit in ams_data] if ams_data else None
                )
                if result:
                    mqtt_message_logger.info(f"[JOB TRACKING] {result}")
            except Exception as job_err:
                logging.getLogger("mqtt").exception("Job tracking failed for serial=%s", cloud_serial_from_topic)
        # Add to buffer

        message_buffer.append(message)

        if len(message_buffer) > MAX_BUFFER_SIZE:

            message_buffer.pop(0)

        # Broadcast to all connected WebSocket clients

        if event_loop:
            _safe_schedule(broadcast_message(
                message,
                ams_data=ams_data,
                job_data=job_data,
                printer_data=mapped_dict,
                raw_payload=parsed_json,
            ), event_loop)

    except Exception as e:

        logging.getLogger("mqtt").exception("Error processing MQTT message for topic=%s", getattr(msg, "topic", None))



def on_disconnect(client, userdata, rc, properties=None):

    """Callback when disconnected (MQTT v5 signature)"""

    connection_id = userdata.get('connection_id', 'unknown')

    print(f"🔌 MQTT Disconnected: {connection_id} (rc={rc})")



async def broadcast_message(message: MQTTMessage, ams_data=None, job_data=None, printer_data=None, raw_payload=None):

    """Send message to all connected WebSocket clients"""

    disconnected = set()

    msg_dict = {

        "topic": message.topic,

        "payload": message.payload,

        "timestamp": message.timestamp,

        "qos": message.qos,

        "printer": printer_data,

        "raw": raw_payload,

    }

    if ams_data:

        msg_dict["ams"] = ams_data

    if job_data:

        msg_dict["job"] = job_data

    for websocket in active_connections:

        try:

            await websocket.send_json(msg_dict)

        except Exception as e:

            logging.getLogger("mqtt").exception("Failed to send MQTT update to websocket client")

            disconnected.add(websocket)

    

    # Remove disconnected clients

    active_connections.difference_update(disconnected)


def _safe_schedule(coro, loop: Optional[asyncio.AbstractEventLoop]):
    """Schedule a coroutine thread-safe only if loop exists and is running/not closed."""
    try:
        if not loop:
            return None
        # is_running is True for running loops; we must also ensure not closed
        if getattr(loop, "is_closed", lambda: False)():
            return None
        return asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:
        logging.getLogger("mqtt").exception("Failed to schedule MQTT websocket coroutine")
        return None



# === ENDPOINTS ===


@router.post("/pushall/{printer_id}")
async def send_pushall(printer_id: str, session: Session = Depends(get_session)):
    """Send pushall command to a printer to request full status update.
    
    This is useful to force a printer to send all AMS data, job status, etc.
    """
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    
    if not printer.cloud_serial:
        raise HTTPException(status_code=400, detail="Printer has no cloud_serial")
    
    # Find the client for this printer
    connection_id = f"{printer.ip_address}:8883_{printer.id}"
    client = mqtt_clients.get(connection_id)
    
    if not client or not client.is_connected():
        raise HTTPException(status_code=400, detail="Printer not connected via MQTT")
    
    try:
        request_topic = f"device/{printer.cloud_serial}/request"
        pushall_cmd = json.dumps({"pushing": {"sequence_id": "1", "command": "pushall"}})
        client.publish(request_topic, pushall_cmd)
        logging.getLogger("mqtt").info(f"[MQTT] Manual pushall sent to {printer.name} ({request_topic})")
        return {"success": True, "message": f"pushall sent to {printer.name}"}
    except Exception as e:
        logging.getLogger("mqtt").exception(f"Failed to send pushall to {printer.name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect")

async def connect_mqtt(connection: MQTTConnection, request: Request):

    """Connect to MQTT broker"""

    try:

        global event_loop, printer_service_ref

        # Merke den aktiven Event-Loop f�r thread-sichere Broadcasts

        printer_service_ref = getattr(request.app.state, "printer_service", None)

        event_loop = asyncio.get_running_loop()



        connection_id = f"{connection.broker}:{connection.port}"

        # Modell-basierte MQTT-Protokoll-Erkennung (PRIORITÄT!)
        from app.services.printer_auto_detector import PrinterAutoDetector

        mqtt_protocol = mqtt.MQTTv311  # Default
        detected_protocol = None

        # 1. Priorität: Modell aus cloud_serial ermitteln
        if connection.cloud_serial:
            model = PrinterAutoDetector.detect_model_from_serial(connection.cloud_serial)
            if model and model.upper() in PrinterAutoDetector.MODEL_MQTT_PROTOCOL:
                protocol_str = PrinterAutoDetector.MODEL_MQTT_PROTOCOL[model.upper()]
                if protocol_str == "5":
                    mqtt_protocol = mqtt.MQTTv5
                    detected_protocol = "5"
                    print(f"[MQTT] Modell {model} (Serial {connection.cloud_serial}) → MQTT v5")
                elif protocol_str == "311":
                    mqtt_protocol = mqtt.MQTTv311
                    detected_protocol = "311"
                    print(f"[MQTT] Modell {model} (Serial {connection.cloud_serial}) → MQTT v3.1.1")

        # 2. Fallback: Auto-Detection (nur wenn kein Modell erkannt)
        if detected_protocol is None:
            try:
                detector = MQTTProtocolDetector()
                detection = detector.detect(connection.broker, connection.password or '', connection.port)
                if detection.get('detected'):
                    detected_protocol = detection.get('protocol')
                    if detected_protocol == "5":
                        mqtt_protocol = mqtt.MQTTv5
                    print(f"[MQTT] Auto-Detection → Protokoll {detected_protocol}")
            except Exception as e:
                logging.getLogger("mqtt").exception("MQTT protocol auto-detection failed for broker=%s", connection.broker)
                detected_protocol = None



        # Disconnect existing connection

        if connection_id in mqtt_clients:

            mqtt_clients[connection_id].disconnect()

            mqtt_clients[connection_id].loop_stop()

            del mqtt_clients[connection_id]

        

        # Create new client (MQTT-Protokoll basierend auf Modell oder Auto-Detection)

        client = mqtt.Client(

            client_id=connection.client_id or "filamenthub_debug",

            protocol=mqtt_protocol

        )

        

        # Set callbacks

        client.user_data_set({

            'connection_id': connection_id,

            'client_id': connection.client_id,

            'cloud_serial': connection.cloud_serial

        })

        client.on_connect = on_connect

        client.on_message = on_message

        client.on_disconnect = on_disconnect

        

        # Auto-Reconnect mit exponential backoff (1-32s)

        client.reconnect_delay_set(min_delay=1, max_delay=32)



        # TLS optional aktivieren (Bambu nutzt meist 8883 mit TLS)

        use_tls = connection.use_tls or connection.port == 8883

        if use_tls:

            # Zertifikatspr�fung bei Bedarf deaktivieren (Drucker nutzt Self-Signed)

            if connection.tls_insecure:

                client.tls_set(

                    tls_version=ssl.PROTOCOL_TLS_CLIENT,

                    cert_reqs=ssl.CERT_NONE

                )

                client.tls_insecure_set(True)

            else:

                client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

        

        # Set credentials if provided (default: Bambu bblp + API Key)

        username = connection.username or "bblp"

        password = connection.password

        if username or password:

            client.username_pw_set(username, password)

        

        # Connect

        client.connect(connection.broker, connection.port, keepalive=60)

        client.loop_start()

        

        # Store client

        mqtt_clients[connection_id] = client

        

        return {

            "success": True,

            "message": f"Connected to {connection_id}",

            "connection_id": connection_id

        }

        

    except Exception as e:

        logging.getLogger("mqtt").exception("Failed to establish MQTT connection for broker=%s", connection.broker)
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/disconnect")

async def disconnect_mqtt(broker: str, port: int = 1883):

    """Disconnect from MQTT broker"""

    connection_id = f"{broker}:{port}"

    try:

        

        if connection_id not in mqtt_clients:

            raise HTTPException(status_code=404, detail="Connection not found")

        

        client = mqtt_clients[connection_id]

        client.disconnect()

        client.loop_stop()

        del mqtt_clients[connection_id]

        

        # Clear subscriptions if no more clients

        if not mqtt_clients:

            subscribed_topics.clear()

            message_buffer.clear()

            try:
                mqtt_runtime.clear_subscriptions()
            except Exception:
                logging.getLogger("mqtt").exception("Failed to clear runtime subscriptions on disconnect")

        

        return {

            "success": True,

            "message": f"Disconnected from {connection_id}"

        }

        

    except HTTPException:

        raise

    except Exception as e:

        logging.getLogger("mqtt").exception("Failed to disconnect MQTT client %s", connection_id)
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/subscribe")

async def subscribe_topic(subscription: MQTTSubscription):

    """Subscribe to MQTT topic"""

    try:

        if not mqtt_clients:

            raise HTTPException(status_code=400, detail="No active MQTT connection")

        

        topic = subscription.topic

        

        # Subscribe on all active clients

        for client in mqtt_clients.values():

            result, _ = client.subscribe(topic)

            if result != mqtt.MQTT_ERR_SUCCESS:

                raise HTTPException(status_code=500, detail=f"Subscribe failed ({result})")

        

        subscribed_topics.add(topic)
        try:
            mqtt_runtime.register_subscription(topic)
        except Exception:
            logging.getLogger("mqtt").exception("Failed to register subscription %s in runtime", topic)

        

        return {

            "success": True,

            "message": f"Subscribed to {topic}",

            "topic": topic

        }

        

    except HTTPException:

        raise

    except Exception as e:

        logging.getLogger("mqtt").exception("Failed to subscribe to topic %s", subscription.topic)
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/unsubscribe")

async def unsubscribe_topic(subscription: MQTTSubscription):

    """Unsubscribe from MQTT topic"""

    try:

        if not mqtt_clients:

            raise HTTPException(status_code=400, detail="No active MQTT connection")

        

        topic = subscription.topic

        

        # Unsubscribe on all active clients

        for client in mqtt_clients.values():

            client.unsubscribe(topic)

        

        subscribed_topics.discard(topic)
        try:
            mqtt_runtime.unregister_subscription(topic)
        except Exception:
            logging.getLogger("mqtt").exception("Failed to unregister subscription %s in runtime", topic)

        

        return {

            "success": True,

            "message": f"Unsubscribed from {topic}",

            "topic": topic

        }

        

    except HTTPException:

        raise

    except Exception as e:

        logging.getLogger("mqtt").exception("Failed to unsubscribe from topic %s", subscription.topic)
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/status")

async def get_mqtt_status():

    """Get current MQTT connection status"""

    connections = []

    active_count = 0

    for connection_id, client in mqtt_clients.items():

        is_connected = client.is_connected()

        connections.append({

            "connection_id": connection_id,

            "connected": is_connected

        })

        if is_connected:

            active_count += 1

    return {

        "active_connections": active_count,

        "subscribed_topics": list(subscribed_topics),

        "message_buffer_size": len(message_buffer),

        "websocket_clients": len(active_connections),

        "connections": connections,

        "last_connect_error": last_connect_error

    }



@router.get("/messages")

async def get_messages(limit: int = 100, topic_filter: Optional[str] = None):

    """Get recent messages from buffer"""

    messages = message_buffer[-limit:]

    

    if topic_filter:

        messages = [m for m in messages if topic_filter in m.topic]

    

    return {

        "messages": [m.dict() for m in messages],

        "total": len(messages)

    }



@router.post("/clear-buffer")

async def clear_message_buffer():

    """Clear message buffer"""

    message_buffer.clear()

    return {"success": True, "message": "Message buffer cleared"}



@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live message streaming"""
    await websocket.accept()
    active_connections.add(websocket)
    mqtt_ws_clients.add(websocket)
    global active_ws_clients, last_ws_activity_ts
    active_ws_clients = max(0, active_ws_clients + 1)
    last_ws_activity_ts = time.time()
    try:
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "connected": len(mqtt_clients) > 0,
            "topics": list(subscribed_topics)
        })
        while True:
            data = await websocket.receive_text()
            last_ws_activity_ts = time.time()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect as exc:
        logging.getLogger("mqtt").info("MQTT websocket client disconnected: %s", exc)
        active_connections.discard(websocket)
        mqtt_ws_clients.discard(websocket)
    except Exception as e:
        logging.getLogger("mqtt").exception("MQTT websocket stream error")
        active_connections.discard(websocket)
        mqtt_ws_clients.discard(websocket)
    finally:
        active_ws_clients = max(0, active_ws_clients - 1)

@router.post("/publish")


async def publish_message(topic: str, payload: str, qos: int = 0):

    """Publish message to MQTT topic"""

    try:

        if not mqtt_clients:

            raise HTTPException(status_code=400, detail="No active MQTT connection")

        

        # Publish on first available client

        client = list(mqtt_clients.values())[0]

        result = client.publish(topic, payload, qos=qos)

        

        if result.rc == mqtt.MQTT_ERR_SUCCESS:

            return {

                "success": True,

                "message": f"Published to {topic}",

                "topic": topic,

                "payload": payload

            }

        else:

            raise HTTPException(status_code=500, detail=f"Publish failed: {result.rc}")

            

    except HTTPException:

        raise

    except Exception as e:

        logging.getLogger("mqtt").exception("Failed to publish MQTT message to topic %s", topic)
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/topics/suggest")

async def suggest_topics(session=Depends(get_session)):

    """Get suggested topics for Bambu Lab printers with real serial numbers"""

    bambu_serials = [
        p.cloud_serial
        for p in session.exec(
            select(Printer).where(
                Printer.printer_type == "bambu",
                Printer.cloud_serial != None,
            )
        ).all()
    ]
    bambu_topics = []

    for serial in bambu_serials:

        bambu_topics.extend([

            f"device/{serial}/report",

            f"device/{serial}/request",

            f"device/{serial}/print",

            f"device/{serial}/camera",

            f"device/{serial}/ams",

            f"device/{serial}/temperature",

            f"device/{serial}/speed",

            f"device/{serial}/layer",

        ])

    # Fallback: Wenn keine Seriennummern, zeige Platzhalter

    if not bambu_topics:

        bambu_topics = [

            "device/+/report",

            "device/+/request",

            "device/+/print",

            "device/+/camera",

            "device/+/ams",

            "device/+/temperature",

            "device/+/speed",

            "device/+/layer",

        ]

    return {

        "bambu_lab": bambu_topics,

        "klipper": [

            "klipper/status",

            "klipper/printer",

            "klipper/temperature",

            "klipper/gcode/response",

        ],

        "common": [

            "#",  # All topics

            "+/status",  # All status topics

            "device/+/#",  # All device topics

        ]

    }



@router.get("/logs")

async def get_mqtt_logs():

    """Gibt die empfangenen MQTT-Nachrichten als Text zur�ck"""

    try:

        with open("logs/mqtt/mqtt_messages.log", "r", encoding="utf-8") as f:

            return f.read()

    except FileNotFoundError:

        logging.getLogger("mqtt").exception("MQTT log file not found")
        return "Noch keine MQTT-Nachrichten empfangen."

    except Exception as e:

        logging.getLogger("mqtt").exception("Failed to read MQTT log file")
        return f"Fehler beim Lesen der Logdatei: {e}"
