import asyncio

import os

import time

from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
import json
import ssl
import logging
import yaml
from datetime import datetime
from typing import Dict, Any, Optional, Sequence, Set, List, cast
import paho.mqtt.client as mqtt
from sqlmodel import select
from app.database import get_session
from services.printer_service import PrinterService

import sqlalchemy as sa

from app.services import mqtt_runtime
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel
from fastapi import Request

from app.services.mqtt_payload_processor import process_mqtt_payload
from app.services.ams_parser import parse_ams
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

# ...existing code...

mqtt_ws_clients = set()



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
                    pass
            # setze Startposition auf Dateiende, damit keine Historie erneut gesendet wird
            try:
                last_size = os.path.getsize(log_file)
            except Exception:
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

                    pass

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        return
from app.models.job import Job, JobSpoolUsage

from sqlmodel import select

from app.models.spool import Spool

from app.models.material import Material

from services.printer_service import PrinterService



# Wichtig: KEINE zweite Router-Initialisierung  wir verwenden den oben definierten `router`.



# === MQTT LOGGER SETUP ===

def get_mqtt_logger():

    """Erstellt/holt MQTT Logger mit Rotation"""

    logger = logging.getLogger("MQTT_Messages")

    

    # Nur einmal initialisieren

    if logger.handlers:

        return logger

    

    # Lese Config

    try:

        with open("config.yaml", "r", encoding="utf-8") as f:

            config = yaml.safe_load(f)

        max_size_mb = config.get("logging", {}).get("max_size_mb", 10)

        backup_count = config.get("logging", {}).get("backup_count", 3)

    except Exception as exc:

        logging.getLogger("app.routes.mqtt").warning("Failed to read config.yaml for MQTT logger: %s", exc)

        max_size_mb = 10

        backup_count = 3

    

    # Erstelle Handler

    os.makedirs("logs/mqtt", exist_ok=True)

    handler = RotatingFileHandler(

        "logs/mqtt/mqtt_messages.log",

        maxBytes=max_size_mb * 1024 * 1024,

        backupCount=backup_count,

        encoding="utf-8"

    )

    

    # Setze Flush sofort (kein Buffering)

    handler.flush = lambda: handler.stream.flush() if handler.stream else None

    

    formatter = logging.Formatter("%(asctime)s | %(message)s")

    handler.setFormatter(formatter)

    

    logger.setLevel(logging.INFO)

    logger.addHandler(handler)

    logger.propagate = False  # Verhindere doppelte Logs

    

    return logger



mqtt_message_logger = get_mqtt_logger()



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

        if not subscribed_topics:

            default_topic = None

            try:

                cserial = userdata.get('cloud_serial') if userdata else None

                if cserial:

                    default_topic = f"device/{cserial}/report"

            except Exception:

                default_topic = None

            if default_topic:

                print(f"Abonniere Default-Topic: {default_topic}")

                client.subscribe(default_topic)

                subscribed_topics.add(default_topic)
                try:
                    mqtt_runtime.register_subscription(default_topic)
                except Exception:
                    pass

        else:

            for topic in subscribed_topics:

                print(f"Abonniere MQTT-Topic: {topic}")

                client.subscribe(topic)
                try:
                    mqtt_runtime.register_subscription(topic)
                except Exception:
                    pass

    else:

        last_connect_error = rc

        print(f"[MQTT] Connection failed (rc={rc})")

        # Fehlschlag: vorhandene Subscriptions leeren, damit Status korrekt ist

        subscribed_topics.clear()
        try:
            mqtt_runtime.clear_subscriptions()
        except Exception:
            pass

        try:

            client.disconnect()

            client.loop_stop()

        except Exception:

            pass

        try:

            cid = userdata.get('connection_id') if userdata else None

            if cid and cid in mqtt_clients:

                del mqtt_clients[cid]

        except Exception:

            pass





def on_message(client, userdata, msg):

    """Callback when message received"""

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
            pass

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
                except Exception as e:
                    print(f"[MQTT] ERROR in set_live_state: {e}")
                    import traceback
                    traceback.print_exc()

        except Exception:

            parsed_json = None



                # Schreibe die Nachricht in MQTT-Log (RotatingFileHandler ?bernimmt Rotation)

        try:

            mqtt_message_logger.info(f"Topic={msg.topic} | Payload={payload}")

        except Exception as logerr:

            print(f"? Fehler beim Schreiben in MQTT-Logdatei: {logerr}")



        # Sende empfangene MQTT-Nachricht an alle verbundenen WebSocket-Clients (Text-Log)

        if event_loop:

            for ws in list(mqtt_ws_clients):

                try:

                    asyncio.run_coroutine_threadsafe(

                        ws.send_text(f"{datetime.now().isoformat()} | Topic={msg.topic} | Payload={payload}"),

                        event_loop

                    )

                except Exception:

                    pass



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

            except Exception:

                printer_id_for_ams = None

        if parsed_json:

            try:

                # Modell-Autoerkennung

                detected_model = PrinterAutoDetector.detect_model_from_payload(parsed_json) or PrinterAutoDetector.detect_model_from_serial(getattr(printer_obj, "cloud_serial", None))

                final_model = detected_model or printer_model_for_mapper or "UNKNOWN"

                if printer_obj and final_model != printer_obj.model:

                    printer_obj.model = final_model

                    try:

                        with next(get_session()) as session:

                            session.add(printer_obj)

                            session.commit()

                    except Exception:

                        pass

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

                mapped_dict = None

        # AMS Sync vor Job-Tracking, damit Tag/Slot-Daten in DB stehen

        if not ams_data and mapped_dict and mapped_dict.get("ams") is not None:

            ams_data = mapped_dict.get("ams")

        if ams_data:

            try:

                mqtt_message_logger.info(f"[AMS SYNC] printer_id={printer_id_for_ams} ams_count={len(ams_data) if isinstance(ams_data, list) else 0}")

                sync_ams_slots(

                    [dict(unit) for unit in ams_data] if isinstance(ams_data, list) else [],

                    printer_id=printer_id_for_ams,

                    auto_create=True

                ) if ams_data else None

                mqtt_message_logger.info(f"[AMS SYNC] done printer_id={printer_id_for_ams}")

            except Exception as sync_err:

                mqtt_message_logger.error(f"AMS Sync failed: {sync_err}")

                print(f"AMS Sync failed: {sync_err}")




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
                print(f"Job tracking error: {job_err}")
        # Add to buffer

        message_buffer.append(message)

        if len(message_buffer) > MAX_BUFFER_SIZE:

            message_buffer.pop(0)

        # Broadcast to all connected WebSocket clients

        asyncio.run_coroutine_threadsafe(

            broadcast_message(

                message,

                ams_data=ams_data,

                job_data=job_data,

                printer_data=mapped_dict,

                raw_payload=parsed_json,

            ),

            event_loop,

        ) if event_loop else None

    except Exception as e:

        print(f"Error processing MQTT message: {e}")



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

            print(f"❌ WebSocket send error: {e}")

            disconnected.add(websocket)

    

    # Remove disconnected clients

    active_connections.difference_update(disconnected)



# === ENDPOINTS ===



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
                print(f"[MQTT] Auto-Detection fehlgeschlagen: {e}")
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

        raise HTTPException(status_code=500, detail=str(e))



@router.post("/disconnect")

async def disconnect_mqtt(broker: str, port: int = 1883):

    """Disconnect from MQTT broker"""

    try:

        connection_id = f"{broker}:{port}"

        

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
                pass

        

        return {

            "success": True,

            "message": f"Disconnected from {connection_id}"

        }

        

    except HTTPException:

        raise

    except Exception as e:

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
            pass

        

        return {

            "success": True,

            "message": f"Subscribed to {topic}",

            "topic": topic

        }

        

    except HTTPException:

        raise

    except Exception as e:

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
            pass

        

        return {

            "success": True,

            "message": f"Unsubscribed from {topic}",

            "topic": topic

        }

        

    except HTTPException:

        raise

    except Exception as e:

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
    except WebSocketDisconnect:
        active_connections.discard(websocket)
        mqtt_ws_clients.discard(websocket)
    except Exception as e:
        print(f"WS WebSocket error: {e}")
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

        raise HTTPException(status_code=500, detail=str(e))



@router.get("/topics/suggest")

async def suggest_topics(session=Depends(get_session)):

    """Get suggested topics for Bambu Lab printers with real serial numbers"""

    bambu_serials = [
        p.cloud_serial
        for p in session.query(Printer).filter(
            Printer.printer_type == "bambu",
            Printer.cloud_serial != None
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

        return "Noch keine MQTT-Nachrichten empfangen."

    except Exception as e:

        return f"Fehler beim Lesen der Logdatei: {e}"
