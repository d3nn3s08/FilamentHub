import asyncio
import os
from collections import deque
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
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
        "mqtt": "logs/mqtt/mqtt_messages.log"
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
        pass
"""
MQTT Viewer Routes
Live monitoring and debugging of MQTT messages
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Set, Any, Sequence
import ssl
from app.database import get_session
from app.models.printer import Printer
import json
import asyncio
import paho.mqtt.client as mqtt
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import yaml
from app.services.ams_parser import parse_ams
from app.services.job_parser import parse_job
from app.services.ams_sync import sync_ams_slots
from app.models.job import Job
from sqlmodel import select
from app.models.spool import Spool
from app.models.material import Material

# Wichtig: KEINE zweite Router-Initialisierung – wir verwenden den oben definierten `router`.

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
    except:
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
message_buffer: List[MQTTMessage] = []
MAX_BUFFER_SIZE = 1000
serial_number = "00M09A372601070"  # <-- ggf. dynamisch machen
DEFAULT_TOPIC = f"device/{serial_number}/report"
subscribed_topics: Set[str] = set()
event_loop: Optional[asyncio.AbstractEventLoop] = None
active_jobs: Dict[str, Dict[str, Any]] = {}


def _find_tray(ams_units: Sequence[Any], slot: Optional[int]) -> Optional[Dict[str, Any]]:
    if slot is None:
        return None
    for unit in ams_units or []:
        trays = unit.get("trays") or []
        for tray in trays:
            tid = tray.get("tray_id") if isinstance(tray, dict) else None
            tid = tid if tid is not None else (tray.get("id") if isinstance(tray, dict) else None)
            if tid is not None and int(tid) == int(slot):
                return tray
    return None

# === MQTT CALLBACKS ===
def on_connect(client, userdata, flags, rc, properties=None):
    """Callback when connected to MQTT broker"""
    connection_id = userdata.get('connection_id', 'unknown')
    if rc == 0:
        print(f"✅ MQTT Connected: {connection_id}")
        # Default-Topic nach Connect abonnieren, falls leer
        if not subscribed_topics:
            print(f"Abonniere Default-Topic: {DEFAULT_TOPIC}")
            client.subscribe(DEFAULT_TOPIC)
            subscribed_topics.add(DEFAULT_TOPIC)
        # Sonstige Topics resubscriben
        else:
            for topic in subscribed_topics:
                print(f"Abonniere MQTT-Topic: {topic}")
                client.subscribe(topic)
    else:
        print(f"âŒ MQTT Connection failed: {rc}")

def on_message(client, userdata, msg):
    """Callback when message received"""
    try:
        payload = msg.payload.decode('utf-8', errors='replace')
        ams_data = []
        job_data = {}
        serial_from_topic = None
        try:
            parts = msg.topic.split("/")
            if len(parts) >= 2 and parts[0] == "device":
                serial_from_topic = parts[1]
        except Exception:
            pass
        try:
            parsed_json = json.loads(payload)
            if msg.topic.endswith("/report"):
                ams_data = parse_ams(parsed_json)
                job_data = parse_job(parsed_json) or {}
        except Exception:
            parsed_json = None

        # Schreibe die Nachricht in MQTT-Log mit manueller Rotation
        try:
            log_file = "logs/mqtt/mqtt_messages.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # Prüfe Dateigröße und rotiere wenn nötig
            try:
                with open("config.yaml", "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                max_size_mb = config.get("logging", {}).get("max_size_mb", 10)
            except:
                max_size_mb = 10
            
            # Rotiere wenn Datei zu groß
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                if file_size > max_size_mb * 1024 * 1024:
                    # Verschiebe alte Dateien
                    for i in range(2, 0, -1):
                        old = f"{log_file}.{i}"
                        new = f"{log_file}.{i+1}"
                        if os.path.exists(old):
                            if os.path.exists(new):
                                os.remove(new)
                            os.rename(old, new)
                    # Verschiebe aktuelle zu .1
                    if os.path.exists(f"{log_file}.1"):
                        os.remove(f"{log_file}.1")
                    os.rename(log_file, f"{log_file}.1")
            
            # Schreibe Log-Eintrag
            with open(log_file, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                f.write(f"{timestamp} | Topic={msg.topic} | Payload={payload}\n")
                f.flush()
                
        except Exception as logerr:
            print(f"❌ Fehler beim Schreiben in MQTT-Logdatei: {logerr}")

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
        if serial_from_topic:
            try:
                with next(get_session()) as session:
                    p = session.exec(select(Printer).where(Printer.cloud_serial == serial_from_topic)).first()
                    if p:
                        printer_id_for_ams = p.id
            except Exception:
                printer_id_for_ams = None
        # AMS Sync vor Job-Tracking, damit Tag/Slot-Daten in DB stehen
        if ams_data:
            try:
                sync_ams_slots(
                    [dict(unit) for unit in ams_data] if isinstance(ams_data, list) else [],
                    printer_id=printer_id_for_ams,
                    auto_create=True
                ) if ams_data else None
            except Exception as sync_err:
                print(f"AMS Sync failed: {sync_err}")

        # Job-Tracking (einfach): Start/Finish auf Basis gcode_state
        if parsed_json and msg.topic.endswith("/report"):
            gstate = parsed_json.get("print", {}).get("gcode_state") or parsed_json.get("gcode_state")
            if gstate:
                try:
                    with next(get_session()) as session:
                        printer_id = printer_id_for_ams
                        if not printer_id and serial_from_topic:
                            p = session.exec(select(Printer).where(Printer.cloud_serial == serial_from_topic)).first()
                            if p:
                                printer_id = p.id

                        default_material_id = None

                        def ensure_material(tray_type: Optional[str], tray_color: Optional[str]) -> Optional[str]:
                            nonlocal default_material_id
                            # wenn schon gesetzt, zuerst versuchen
                            if default_material_id:
                                return default_material_id
                            name = tray_type or "Unknown"
                            brand = "Bambu Lab"
                            existing = session.exec(
                                select(Material).where(Material.name == name, Material.brand == brand)
                            ).first()
                            if existing:
                                default_material_id = existing.id
                                return existing.id
                            # fallback: erster Eintrag
                            fallback = session.exec(select(Material)).first()
                            try:
                                mat = Material(
                                    name=name,
                                    brand=brand,
                                    color=f"#{tray_color[:6]}" if tray_color else None,
                                    density=1.24,
                                    diameter=1.75,
                                )
                                session.add(mat)
                                session.commit()
                                session.refresh(mat)
                                default_material_id = mat.id
                                return mat.id
                            except Exception:
                                session.rollback()
                                return fallback.id if fallback else None

                        def match_spool(slot: Optional[int], tray: Optional[Dict[str, Any]]) -> Optional[Spool]:
                            tag_uid = tray.get("tag_uid") if tray else None
                            tray_uuid = tray.get("tray_uuid") if tray else None
                            stmt = select(Spool)
                            if printer_id:
                                stmt = stmt.where(Spool.printer_id == printer_id)
                            if tag_uid:
                                stmt = stmt.where(Spool.tag_uid == tag_uid)
                            elif tray_uuid:
                                stmt = stmt.where(Spool.tray_uuid == tray_uuid)
                            elif slot is not None:
                                stmt = stmt.where(Spool.ams_slot == slot)
                            else:
                                return None
                            return session.exec(stmt).first()

                        def create_spool_from_tray(slot: Optional[int], tray: Optional[Dict[str, Any]]) -> Optional[Spool]:
                            if not tray:
                                return None
                            tray_type = tray.get("tray_type") or tray.get("material")
                            tray_color = tray.get("tray_color") or tray.get("color")
                            if slot is None:
                                raw_slot = tray.get("tray_id")
                                if raw_slot is None:
                                    raw_slot = tray.get("id")
                                if raw_slot is None:
                                    raw_slot = tray.get("slot") or tray.get("tray")
                                if raw_slot is not None:
                                    try:
                                        slot = int(raw_slot)
                                    except Exception:
                                        slot = None
                                if slot is None:
                                    name_hint = tray.get("tray_id_name") or tray.get("name")
                                    if name_hint and isinstance(name_hint, str):
                                        digits = "".join(filter(str.isdigit, name_hint))
                                        if digits:
                                            try:
                                                slot = int(digits[-1])
                                            except Exception:
                                                slot = None
                            mat_id = ensure_material(tray_type, tray_color)
                            if not mat_id:
                                return None
                            remain = tray.get("remain") or tray.get("remain_percent")
                            tray_uuid = tray.get("tray_uuid")
                            tag_uid = tray.get("tag_uid") or tray.get("tag")
                            label = tray.get("tray_id_name") or (f"AMS Slot {slot}" if slot is not None else "AMS Spool")
                            sp = Spool(
                                material_id=mat_id,
                                printer_id=printer_id,
                                ams_slot=slot,
                                tag_uid=tag_uid,
                                tray_uuid=tray_uuid,
                                tray_color=tray_color,
                                tray_type=tray_type,
                                remain_percent=float(remain) if remain is not None else 0.0,
                                weight_current=None,
                                last_seen=datetime.utcnow().isoformat(),
                                label=label
                            )
                            # Gewicht ableiten, falls Daten vorhanden
                            try:
                                wf = tray.get("weight_full")
                                we = tray.get("weight_empty")
                                if sp.remain_percent is not None and wf is not None and we is not None:
                                    sp.weight_current = float(we) + (sp.remain_percent / 100.0) * (float(wf) - float(we))
                            except Exception:
                                pass
                            session.add(sp)
                            session.commit()
                            session.refresh(sp)
                            return sp

                        # START
                        if gstate.upper() in ("RUNNING", "START", "PRINTING") and printer_id:
                            if serial_from_topic and serial_from_topic not in active_jobs:
                                slot = job_data.get("tray_target") if isinstance(job_data, dict) else None
                                if slot is None:
                                    slot = job_data.get("tray_current") if isinstance(job_data, dict) else None
                                slot_int = int(slot) if slot is not None else None
                                tray_info = _find_tray(ams_data if isinstance(ams_data, list) else [], slot_int)
                                start_remain = None
                                total_len = None
                                if tray_info and isinstance(tray_info, dict):
                                    start_remain = tray_info.get("remain")
                                    total_len = tray_info.get("total_len")
                                spool_obj = match_spool(slot_int, tray_info)
                                if not spool_obj:
                                    spool_obj = create_spool_from_tray(slot_int, tray_info)

                                # Job-Name ableiten: Subtask-Name > G-Code-Dateiname (ohne Pfad) > Default
                                raw_name = None
                                if isinstance(job_data, dict):
                                    raw_name = job_data.get("subtask_name")
                                if not raw_name:
                                    raw_name = parsed_json.get("subtask_name") if isinstance(parsed_json, dict) else None
                                if not raw_name:
                                    raw_name = parsed_json.get("gcode_file") or parsed_json.get("file") or "Unnamed Job"
                                # ggf. Pfad abschneiden
                                if raw_name and "/" in raw_name:
                                    raw_name = raw_name.split("/")[-1]
                                job = Job(
                                    printer_id=printer_id,
                                    spool_id=spool_obj.id if spool_obj else None,
                                    name=raw_name or "Unnamed Job",
                                    filament_used_mm=0,
                                    filament_used_g=0,
                                )
                                session.add(job)
                                session.commit()
                                session.refresh(job)
                                active_jobs[serial_from_topic] = {
                                    "job_id": job.id,
                                    "start_remain": start_remain,
                                    "start_total_len": total_len,
                                    "slot": slot_int,
                                    "spool_id": spool_obj.id if spool_obj else None,
                                }
                        # LIVE UPDATE während aktivem Job: Verbrauch/Spoolgewicht nachführen
                        if serial_from_topic and serial_from_topic in active_jobs:
                            info = active_jobs.get(serial_from_topic, {})
                            job_id = info.get("job_id")
                            if job_id:
                                job = session.get(Job, job_id)
                                if job:
                                    slot_int = info.get("slot")
                                    tray_info_now = _find_tray(ams_data if isinstance(ams_data, list) else [], slot_int)
                                    current_remain = None
                                    if tray_info_now and isinstance(tray_info_now, dict):
                                        current_remain = tray_info_now.get("remain")
                                    used_percent = None
                                    if info.get("start_remain") is not None and current_remain is not None:
                                        used_percent = max(0.0, float(info["start_remain"]) - float(current_remain))
                                    used_mm = None
                                    if used_percent is not None and info.get("start_total_len"):
                                        used_mm = (used_percent / 100.0) * float(info["start_total_len"])
                                    used_g = None
                                    if used_percent is not None:
                                        target_spool_id = job.spool_id or info.get("spool_id")
                                        if target_spool_id:
                                            sp = session.get(Spool, target_spool_id)
                                            if sp and sp.weight_full is not None and sp.weight_empty is not None:
                                                used_g = (used_percent / 100.0) * (float(sp.weight_full) - float(sp.weight_empty))
                                                # Live-Gewicht auf Spule nachführen
                                                try:
                                                    sp.weight_current = float(sp.weight_full) - used_g
                                                    session.add(sp)
                                                except Exception:
                                                    pass
                                    if used_mm is not None:
                                        job.filament_used_mm = used_mm
                                    if used_g is not None:
                                        job.filament_used_g = used_g
                                    session.add(job)
                                    session.commit()
                        # FINISH
                        if gstate.upper() in ("FINISH", "IDLE", "COMPLETED") and serial_from_topic and serial_from_topic in active_jobs:
                            info = active_jobs.pop(serial_from_topic, {})
                            job_id = info.get("job_id")
                            if job_id:
                                job = session.get(Job, job_id)
                                if job:
                                    slot_int = info.get("slot")
                                    tray_info_end = _find_tray(ams_data if isinstance(ams_data, list) else [], slot_int)
                                    end_remain = None
                                    if tray_info_end and isinstance(tray_info_end, dict):
                                        end_remain = tray_info_end.get("remain")
                                    used_percent = None
                                    if info.get("start_remain") is not None and end_remain is not None:
                                        used_percent = max(0.0, float(info["start_remain"]) - float(end_remain))
                                    used_mm = None
                                    if used_percent is not None and info.get("start_total_len"):
                                        used_mm = (used_percent / 100.0) * float(info["start_total_len"])
                                    # set spool if not set
                                    if not job.spool_id:
                                        spool_obj = match_spool(slot_int, tray_info_end)
                                        if not spool_obj and tray_info_end:
                                            spool_obj = create_spool_from_tray(slot_int, tray_info_end)
                                        job.spool_id = spool_obj.id if spool_obj else None
                                    used_g = None
                                    if used_percent is not None and job.spool_id:
                                        sp = session.get(Spool, job.spool_id)
                                        if sp and sp.weight_full is not None and sp.weight_empty is not None:
                                            used_g = (used_percent / 100.0) * (float(sp.weight_full) - float(sp.weight_empty))
                                    if used_mm is not None:
                                        job.filament_used_mm = used_mm
                                    if used_g is not None:
                                        job.filament_used_g = used_g
                                    job.finished_at = datetime.utcnow()
                                    session.add(job)
                                    session.commit()
                except Exception as job_err:
                    print(f"Job tracking error: {job_err}")
        # Add to buffer
        message_buffer.append(message)
        if len(message_buffer) > MAX_BUFFER_SIZE:
            message_buffer.pop(0)
        # Broadcast to all connected WebSocket clients
        asyncio.run_coroutine_threadsafe(broadcast_message(message, ams_data=ams_data, job_data=job_data), event_loop) if event_loop else None
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

def on_disconnect(client, userdata, rc, properties=None):
    """Callback when disconnected (MQTT v5 signature)"""
    connection_id = userdata.get('connection_id', 'unknown')
    print(f"ðŸ”Œ MQTT Disconnected: {connection_id} (rc={rc})")

async def broadcast_message(message: MQTTMessage, ams_data=None, job_data=None):
    """Send message to all connected WebSocket clients"""
    disconnected = set()
    msg_dict = message.dict()
    if ams_data:
        msg_dict["ams"] = ams_data
    if job_data:
        msg_dict["job"] = job_data
    for websocket in active_connections:
        try:
            await websocket.send_json(msg_dict)
        except Exception as e:
            print(f"âŒ WebSocket send error: {e}")
            disconnected.add(websocket)
    
    # Remove disconnected clients
    active_connections.difference_update(disconnected)

# === ENDPOINTS ===

@router.post("/connect")
async def connect_mqtt(connection: MQTTConnection):
    """Connect to MQTT broker"""
    try:
        global event_loop
        # Merke den aktiven Event-Loop für thread-sichere Broadcasts
        event_loop = asyncio.get_running_loop()

        connection_id = f"{connection.broker}:{connection.port}"
        
        # Disconnect existing connection
        if connection_id in mqtt_clients:
            mqtt_clients[connection_id].disconnect()
            mqtt_clients[connection_id].loop_stop()
            del mqtt_clients[connection_id]
        
        # Create new client
        client = mqtt.Client(
            client_id=connection.client_id or "filamenthub_debug",
            protocol=mqtt.MQTTv5
        )
        
        # Set callbacks
        client.user_data_set({'connection_id': connection_id})
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect

        # TLS optional aktivieren (Bambu nutzt meist 8883 mit TLS)
        use_tls = connection.use_tls or connection.port == 8883
        if use_tls:
            # Zertifikatsprüfung bei Bedarf deaktivieren (Drucker nutzt Self-Signed)
            if connection.tls_insecure:
                client.tls_set(
                    tls_version=ssl.PROTOCOL_TLS_CLIENT,
                    cert_reqs=ssl.CERT_NONE
                )
                client.tls_insecure_set(True)
            else:
                client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
        
        # Set credentials if provided
        if connection.username and connection.password:
            client.username_pw_set(connection.username, connection.password)
        
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
        "connections": connections
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
    try:
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "connected": len(mqtt_clients) > 0,
            "topics": list(subscribed_topics)
        })
        # Keep connection alive
        while True:
            # Wait for client messages (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_connections.discard(websocket)
        mqtt_ws_clients.discard(websocket)
    except Exception as e:
        print(f"âŒ WebSocket error: {e}")
        active_connections.discard(websocket)
        mqtt_ws_clients.discard(websocket)

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
    bambu_serials = [p.cloud_serial for p in session.query(Printer).filter(Printer.printer_type == "bambu", Printer.cloud_serial != None).all()]
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
    """Gibt die empfangenen MQTT-Nachrichten als Text zurück"""
    try:
        with open("logs/mqtt/mqtt_messages.log", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Noch keine MQTT-Nachrichten empfangen."
    except Exception as e:
        return f"Fehler beim Lesen der Logdatei: {e}"

