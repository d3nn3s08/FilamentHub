from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import datetime, timezone
import time
from threading import Lock
from typing import Any, Dict, Optional
import yaml
import re
import json
from pathlib import Path

from app.services.printer_mqtt_client import PrinterMQTTClient
from uuid import uuid4
from services.printer_service import PrinterService
from app.models.printer import Printer


@dataclass(frozen=True)
class _RuntimeConfig:
    host: str
    port: int
    username: str
    password: Optional[str]
    client_id: str
    protocol: str
    tls: bool
    model: str
    cloud_serial: Optional[str] = None
    printer_id: Optional[str] = None
    printer_name: Optional[str] = None


def _load_mqtt_logging_config() -> dict:
    """Load mqtt_logging config from config.yaml"""
    try:
        config_path = Path(__file__).resolve().parents[2] / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("mqtt_logging", {})
    except Exception as e:
        # Fallback defaults if config missing
        return {
            "enabled": True,
            "smart_logging": {
                "enabled": False,
                "trigger_type": "command",
                "trigger_value": "RUNNING",
                "max_duration_hours": 4,
                "buffer_minutes": 5
            },
            "limits": {
                "max_size_mb": 100,
                "max_payload_chars": 1000,
                "full_payload_enabled": False,
                "full_payload_file": "logs/mqtt/full_payloads.jsonl"
            },
            "ams_climate": {
                "enabled": True,
                "log_file": "logs/mqtt/ams_climate.jsonl",
                "max_size_mb": 50
            }
        }


_client_instance: Optional[PrinterMQTTClient] = None
_client_config: Optional[_RuntimeConfig] = None
_connected_since: Optional[datetime] = None

# Global runtime state exposed to status endpoint. Updated on connect and on_message.
_runtime_state: Dict[str, Optional[Any]] = {
    "connected": False,
    "cloud_serial": None,
    "connected_since": None,
    "last_seen": None,
    "broker": None,
    "port": None,
    "client_id": None,
    "protocol": None,
    "qos": 1,
}

_topic_stats_lock = Lock()
_topic_stats: Dict[str, Dict[str, Any]] = {}
_transport_connected_since: Optional[datetime] = None

# Explicit runtime subscriptions (independent of received messages)
_subscribed_topics_lock = Lock()
_subscribed_topics: set[str] = set()

# Live message buffer (last 50 messages for UI display)
_messages_lock = Lock()
_messages_buffer: list[Dict[str, Any]] = []
_messages_max_size = 50

# MQTT Logging Config (loaded once at import)
_mqtt_logging_config = _load_mqtt_logging_config()

# Smart Logging State
_smart_logging_active = False  # Ist Smart Logging gerade aktiv?
_smart_logging_start_time: Optional[datetime] = None  # Wann gestartet?
_smart_logging_buffer_timer: Optional[float] = None  # Buffer-Ende Timestamp
_smart_logging_lock = Lock()  # Thread-Safety

# AMS Climate Whitelist System
_ams_climate_logger: Optional[Any] = None
_ams_climate_lock = Lock()

# Full Payload Logger (optional)
_full_payload_logger: Optional[Any] = None
_full_payload_lock = Lock()


# ===================================================================
# SMART LOGGING FUNCTIONS
# ===================================================================

def _should_log_message(topic: str, payload: str) -> bool:
    """Check if message should be logged based on smart logging config"""
    config = _mqtt_logging_config

    # Basic logging disabled?
    if not config.get("enabled", True):
        return False

    # Smart logging disabled? -> Always log
    smart_config = config.get("smart_logging", {})
    if not smart_config.get("enabled", False):
        return True

    # Smart logging enabled -> Check if active
    with _smart_logging_lock:
        # If in buffer period, keep logging
        if _smart_logging_buffer_timer:
            if time.time() < _smart_logging_buffer_timer:
                return True
            else:
                # Buffer expired, stop logging
                return False

        # If actively logging, check max duration
        if _smart_logging_active and _smart_logging_start_time:
            max_hours = smart_config.get("max_duration_hours", 4)
            elapsed = (datetime.now(timezone.utc) - _smart_logging_start_time).total_seconds() / 3600
            if elapsed > max_hours:
                _stop_smart_logging("Max duration reached")
                return False
            return True

        # Not active
        return False


def _check_start_trigger(payload: str) -> bool:
    """Check if payload contains start trigger"""
    smart_config = _mqtt_logging_config.get("smart_logging", {})
    trigger_type = smart_config.get("trigger_type", "command")
    trigger_value = smart_config.get("trigger_value", "RUNNING")

    if trigger_type == "command":
        # Case-insensitive search for command string
        return trigger_value.lower() in str(payload).lower()

    elif trigger_type == "temperature":
        # Search for any temperature >= trigger_value
        # Pattern matches both "nozzle_temp" and "nozzle_temper" variants
        temp_pattern = r'"(?:nozzle_temp(?:er)?|bed_temp(?:er)?|temp)"\s*:\s*"?(\d+\.?\d*)"?'
        matches = re.findall(temp_pattern, str(payload), re.IGNORECASE)

        try:
            trigger_temp = float(trigger_value)
            for match in matches:
                if float(match) >= trigger_temp:
                    return True
        except (ValueError, TypeError):
            pass

    return False


def _check_stop_trigger(payload: str) -> bool:
    """Check if payload contains finish/error/complete indicator"""
    payload_lower = str(payload).lower()

    # Common stop keywords (erweiterbar)
    stop_keywords = [
        "finish", "complete", "done", "error",
        "failed", "cancelled", "aborted", "stopped"
    ]

    return any(kw in payload_lower for kw in stop_keywords)


def _start_smart_logging(reason: str = "trigger detected"):
    """Start smart logging session"""
    global _smart_logging_active, _smart_logging_start_time, _smart_logging_buffer_timer

    from datetime import datetime, timezone
    with _smart_logging_lock:
        if not _smart_logging_active:
            _smart_logging_active = True
            _smart_logging_start_time = datetime.now(timezone.utc)
            _smart_logging_buffer_timer = None

            logger = logging.getLogger("3D_drucker")
            logger.info(f"Smart Logging STARTED: {reason}")
            print(f"[MQTT Smart Logging] STARTED: {reason}")


def _stop_smart_logging(reason: str = "trigger detected"):
    """Stop smart logging with buffer period"""
    global _smart_logging_active, _smart_logging_buffer_timer

    smart_config = _mqtt_logging_config.get("smart_logging", {})
    buffer_minutes = smart_config.get("buffer_minutes", 5)

    from datetime import datetime, timezone
    with _smart_logging_lock:
        if _smart_logging_active:
            _smart_logging_active = False
            # Set buffer timer (keep logging for N more minutes)
            _smart_logging_buffer_timer = time.time() + (buffer_minutes * 60)

            logger = logging.getLogger("3D_drucker")
            logger.info(f"Smart Logging STOPPED: {reason} (buffer: {buffer_minutes}min)")
            print(f"[MQTT Smart Logging] STOPPED: {reason} (buffer: {buffer_minutes}min)")


# ===================================================================
# AMS CLIMATE WHITELIST SYSTEM
# ===================================================================

def _is_ams_climate_data(topic: str, payload: str) -> bool:
    """
    Check if this message contains AMS climate data.
    AMS data is always logged, regardless of smart logging state.
    """
    # Quick check: Must be device report
    if "/report" not in topic:
        return False

    # Check if payload contains AMS structure
    if '"ams"' in payload and ('"temp"' in payload or '"humidity"' in payload):
        return True

    return False


def _extract_ams_climate(payload: str) -> Optional[Dict[str, Any]]:
    """
    Extract AMS climate data from payload.

    Returns dict with:
        - temperature: float
        - humidity: int (processed value)
        - humidity_raw: int (raw sensor value)

    Returns None if extraction fails.
    """
    try:
        data = json.loads(payload)

        # Navigate to AMS data: print.ams.ams[0]
        ams_list = data.get("print", {}).get("ams", {}).get("ams", [])

        if not ams_list or len(ams_list) == 0:
            return None

        # Get first AMS unit
        ams_unit = ams_list[0]

        temp_str = ams_unit.get("temp")
        humidity_str = ams_unit.get("humidity")
        humidity_raw_str = ams_unit.get("humidity_raw")

        # Convert to numbers
        result = {}

        if temp_str:
            result["temperature"] = float(temp_str)

        if humidity_str:
            result["humidity"] = int(humidity_str)

        if humidity_raw_str:
            result["humidity_raw"] = int(humidity_raw_str)

        # Only return if we got at least temp or humidity
        if result:
            return result

        return None

    except (json.JSONDecodeError, ValueError, KeyError, TypeError):
        return None


def _get_ams_climate_logger():
    """Get or create logger for AMS climate data"""
    global _ams_climate_logger

    with _ams_climate_lock:
        if _ams_climate_logger:
            return _ams_climate_logger

        ams_config = _mqtt_logging_config.get("ams_climate", {})

        if not ams_config.get("enabled", True):
            return None

        log_file = ams_config.get("log_file", "logs/mqtt/ams_climate.jsonl")

        # Ensure directory exists
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        from logging.handlers import RotatingFileHandler

        logger = logging.getLogger("AMS_Climate")
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't propagate to root

        # RotatingFileHandler
        max_size_mb = ams_config.get("max_size_mb", 50)
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))  # Just the message (JSONL)
        logger.addHandler(handler)

        _ams_climate_logger = logger
        return logger


def _log_ams_climate(payload: str):
    """
    Log AMS climate data to separate file.
    This always logs, regardless of smart logging state.
    """
    from datetime import datetime, timezone
    try:
        climate_data = _extract_ams_climate(payload)

        if not climate_data:
            return  # No valid data

        logger = _get_ams_climate_logger()

        if not logger:
            return  # AMS logging disabled

        # Create log entry
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **climate_data
        }

        logger.info(json.dumps(log_entry, ensure_ascii=False))

    except Exception:
        # Silent fail - don't break main logging
        pass


# ===================================================================
# FULL PAYLOAD LOGGER (OPTIONAL)
# ===================================================================

def _get_full_payload_logger():
    """Get or create logger for full payloads"""
    global _full_payload_logger

    with _full_payload_lock:
        if _full_payload_logger:
            return _full_payload_logger

        limits = _mqtt_logging_config.get("limits", {})

        if not limits.get("full_payload_enabled", False):
            return None

        log_file = limits.get("full_payload_file", "logs/mqtt/full_payloads.jsonl")

        # Ensure directory exists
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        from logging.handlers import RotatingFileHandler

        logger = logging.getLogger("MQTT_FullPayload")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        max_size_mb = limits.get("max_size_mb", 100)
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

        _full_payload_logger = logger
        return logger


def _write_full_payload(topic: str, payload: str):
    """Write full (untruncated) payload to separate file"""
    try:
        logger = _get_full_payload_logger()

        if not logger:
            return

        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "payload": payload  # FULL payload, no truncation
        }
        logger.info(json.dumps(log_entry, ensure_ascii=False))
    except Exception:
        pass


# ===================================================================
# STATUS HELPER
# ===================================================================

def get_smart_logging_status() -> Dict[str, Any]:
    """
    Get current smart logging status.
    Useful for displaying in UI or API.
    """
    with _smart_logging_lock:
        status = {
            "enabled": _mqtt_logging_config.get("smart_logging", {}).get("enabled", False),
            "active": _smart_logging_active,
            "start_time": _smart_logging_start_time.isoformat() if _smart_logging_start_time else None,
            "in_buffer": _smart_logging_buffer_timer is not None and time.time() < _smart_logging_buffer_timer,
        }

        if _smart_logging_active and _smart_logging_start_time:
            elapsed_seconds = (datetime.now(timezone.utc) - _smart_logging_start_time).total_seconds()
            status["elapsed_hours"] = round(elapsed_seconds / 3600, 2)

        return status


def _build_printer_connect_payload(printer: Printer) -> Optional[Dict[str, Any]]:
    if not printer:
        return None
    if getattr(printer, "printer_type", "") not in ("bambu", "bambu_lab"):
        return None
    ip = getattr(printer, "ip_address", None)
    api_key = getattr(printer, "api_key", None)
    cloud_serial = getattr(printer, "cloud_serial", None)
    if not ip or not api_key or not cloud_serial:
        return None
    port = int(getattr(printer, "port", 0) or 6000)
    protocol = str(getattr(printer, "mqtt_version", "5") or "5")
    client_id = f"filamenthub_{getattr(printer, 'name', 'printer')}_{str(getattr(printer, 'id', ''))[:6]}"
    return {
        "host": ip,
        "port": port,
        "client_id": client_id,
        "username": "bblp",
        "password": api_key,
        "protocol": protocol,
        "tls": True,
        "cloud_serial": cloud_serial,
        "printer_id": getattr(printer, "id", ""),
        "printer_name": getattr(printer, "name", None) or client_id,
        "printer_model": getattr(printer, "model", "X1C"),
    }


def apply_auto_connect(printer: Optional[Printer]) -> Dict[str, Any]:
    """Apply the auto_connect flag for a printer by connecting or disconnecting."""
    logger = logging.getLogger("mqtt_runtime")
    if not printer:
        logger.warning("apply_auto_connect called without printer data")
        return {"success": False, "message": "printer missing"}

    if getattr(printer, "auto_connect", False):
        payload = _build_printer_connect_payload(printer)
        if not payload:
            logger.warning("Printer %s missing data, cannot auto-connect", getattr(printer, "id", "<unknown>"))
            return {"success": False, "message": "printer missing required data"}
        logger.info("Auto-connect enabled → connecting printer %s (%s)", getattr(printer, "name", printer.id), printer.id)
        result = connect(payload)
        if not isinstance(result, dict):
            logger.error("Auto-connect failed: unexpected result type %s", type(result).__name__)
            return {"success": False, "message": "invalid runtime response"}
        if not result.get("success"):
            logger.error(
                "Auto-connect failed for printer %s: %s",
                getattr(printer, "id", "<unknown>"),
                result.get("error") or "connect returned false",
            )
        return result

    logger.info("Auto-connect disabled → disconnecting runtime (printer %s)", getattr(printer, "id", "<unknown>"))
    return disconnect()


def _add_message(topic: str, payload: str, timestamp: datetime) -> None:
    """Add message to ring buffer (FIFO, max 50)."""
    t = _normalize_topic(topic)
    if not t:
        return
    
    msg_entry = {
        "topic": t,
        "payload": payload[:200] if payload else "",  # Truncate long payloads
        "timestamp": _iso_utc(timestamp),
    }
    
    with _messages_lock:
        _messages_buffer.append(msg_entry)
        # Keep only last 50 messages
        if len(_messages_buffer) > _messages_max_size:
            _messages_buffer.pop(0)


def get_messages(limit: int = 50) -> list[Dict[str, Any]]:
    """Get last N messages (most recent first)."""
    with _messages_lock:
        # Return in reverse order (newest first)
        return list(reversed(_messages_buffer[-limit:]))


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _reset_topic_stats() -> None:
    with _topic_stats_lock:
        _topic_stats.clear()


def _reset_subscribed_topics() -> None:
    with _subscribed_topics_lock:
        _subscribed_topics.clear()


def _normalize_topic(topic: str) -> str:
    return (topic or "").strip()


def register_subscription(topic: str) -> None:
    t = _normalize_topic(topic)
    if not t:
        return
    with _subscribed_topics_lock:
        _subscribed_topics.add(t)


def unregister_subscription(topic: str) -> None:
    t = _normalize_topic(topic)
    if not t:
        return
    with _subscribed_topics_lock:
        _subscribed_topics.discard(t)


def clear_subscriptions() -> None:
    _reset_subscribed_topics()


def _record_topic(topic: str) -> None:
    t = _normalize_topic(topic)
    if not t:
        return
    now = datetime.now(timezone.utc)
    with _topic_stats_lock:
        entry = _topic_stats.get(t)
        if entry is None:
            _topic_stats[t] = {"count": 1, "last_seen": now}
            return
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = now


def _aggregate_topic_stats() -> Dict[str, Any]:
    """Summarize topic stats for status response."""
    with _topic_stats_lock:
        total_topics = len(_topic_stats)
        total_messages = sum(int(v.get("count", 0)) for v in _topic_stats.values())
        last_dt = None
        for v in _topic_stats.values():
            dt = v.get("last_seen")
            if isinstance(dt, datetime):
                if last_dt is None or dt > last_dt:
                    last_dt = dt

    return {
        "subscriptions_count": len(_subscribed_topics),
        "topics_count": len(_subscribed_topics),
        "message_count": total_messages,
        "last_message_time": _iso_utc(last_dt) if last_dt else None,
    }


def _format_uptime(connected_since: Optional[str]) -> Optional[str]:
    if not connected_since:
        return None
    try:
        # Accept ISO with trailing Z or without
        dt = datetime.fromisoformat(str(connected_since).replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return None


def topics() -> Dict[str, Any]:
    """Return the list of subscribed topics (not message stats)."""
    connected_flag = bool(_runtime_state.get("connected"))

    with _subscribed_topics_lock:
        items = sorted(list(_subscribed_topics))
        count = len(items)

    return {
        "connected": connected_flag,
        "items": items,
        "count": count,
    }


def _is_connected(client: PrinterMQTTClient) -> bool:
    try:
        inner = getattr(client, "client", None)
        if inner is not None and hasattr(inner, "is_connected"):
            return bool(inner.is_connected())
    except Exception:
        pass

    connected_flag = getattr(client, "connected", None)
    if isinstance(connected_flag, bool):
        return connected_flag

    return False


def connect(config: Dict[str, Any]) -> Dict[str, Any]:
    """Create exactly one runtime PrinterMQTTClient instance and connect.

    Expected config keys (minimal):
    - host (str)
    Optional:
    - port (int, default 8883)  (PrinterMQTTClient currently connects to 8883 internally)
    - username (str, default 'bblp')
    - password (str | None)
    - client_id (str, default 'filamenthub_runtime')
    - protocol (str, default '311')  # '5' | '311' | '31'
    - tls (bool, default True)
    - model (str, default 'X1C')
    """
    global _client_instance, _client_config, _connected_since

    try:
        _reset_topic_stats()

        host = str(config.get("host") or config.get("broker") or config.get("ip") or "").strip()
        if not host:
            return {"success": False, "error": "missing host"}

        port_raw = config.get("port", 8883)
        try:
            port = int(port_raw)
        except Exception:
            port = 8883

        tls = bool(config.get("tls", True))
        if not tls:
            return {"success": False, "error": "tls must be enabled for PrinterMQTTClient"}

        if port != 8883:
            return {"success": False, "error": "port must be 8883 for PrinterMQTTClient"}

        username = str(config.get("username") or "bblp")
        password = config.get("password")
        password = None if password in ("", None) else str(password)

        client_id = str(config.get("client_id") or "filamenthub_runtime")
        protocol = str(config.get("protocol") or "311")
        model = str(config.get("model") or "X1C")

        # 1) If an instance exists and is connected -> disconnect first
        if _client_instance is not None and _is_connected(_client_instance):
            disconnect()

        # Initialize runtime state for UI status (do NOT mark connected True here).
        try:
            _runtime_state.update({
                "connected": False,
                "cloud_serial": config.get("cloud_serial"),
                "connected_since": None,
                "last_seen": None,
                "broker": host,
                "port": port,
                "client_id": client_id,
                "protocol": protocol,
            })
        except Exception:
            pass

        # 2) Create new instance (Source of Truth)
        printer_service = PrinterService()

        # Register printer in PrinterService by cloud_serial if provided
        cloud_serial = config.get("cloud_serial")
        try:
            printer_name = config.get("printer_name") or client_id
            printer_model = config.get("printer_model") or model
            printer_id_cfg = config.get("printer_id") or ""
            if cloud_serial:
                try:
                    printer_service.register_printer(key=cloud_serial, name=printer_name, model=printer_model, printer_id=printer_id_cfg, source="mqtt_connect")
                except Exception:
                    pass
        except Exception:
            pass

        # Track default subscription (device/<cloud_serial>/report) as soon as config is known.
        if cloud_serial:
            try:
                register_subscription(f"device/{cloud_serial}/report")
            except Exception:
                pass

        # Log client initialization
        print(f"[MQTT] INIT client_id={client_id} model={model}")

        client = PrinterMQTTClient(
            ip=host,
            model=model,
            name=client_id,
            mqtt_version=protocol,
            printer_service=printer_service,
            username=username,
            password=password,
            debug=False,
        )

        # Wrap on_message to record topics without changing existing behavior.
        try:
            inner = getattr(client, "client", None)
            if inner is not None:
                prev_on_message = getattr(inner, "on_message", None)

                def _runtime_on_message(c, u, msg):
                    try:
                        topic = getattr(msg, "topic", "")
                        _record_topic(topic)

                        # Get payload
                        payload = getattr(msg, "payload", b"")
                        if isinstance(payload, bytes):
                            try:
                                payload = payload.decode("utf-8", errors="replace")
                            except Exception:
                                payload = str(payload)

                        # Add message to live buffer for UI
                        from datetime import datetime, timezone
                        _add_message(topic, payload, datetime.now(timezone.utc))

                        # ===================================================================
                        # AMS CLIMATE WHITELIST - Always log, regardless of smart logging
                        # ===================================================================
                        if _is_ams_climate_data(topic, payload):
                            _log_ams_climate(payload)

                        # ===================================================================
                        # SMART LOGGING: Check triggers
                        # ===================================================================
                        if _mqtt_logging_config.get("smart_logging", {}).get("enabled", False):
                            if _check_start_trigger(payload):
                                _start_smart_logging("Start trigger found")
                            if _check_stop_trigger(payload):
                                _stop_smart_logging("Stop trigger found")

                        # ===================================================================
                        # MAIN LOGGING: Check if we should log this message
                        # ===================================================================
                        if _should_log_message(topic, payload):
                            # Get truncation limits from config
                            limits = _mqtt_logging_config.get("limits", {})
                            max_payload_chars = limits.get("max_payload_chars", 1000)
                            full_payload_enabled = limits.get("full_payload_enabled", False)

                            # Truncate payload for main log
                            payload_short = payload
                            if len(payload) > max_payload_chars:
                                payload_short = payload[:max_payload_chars] + "...[truncated]"

                            # Write to standard log (truncated)
                            try:
                                mqtt_logger = logging.getLogger("3D_drucker")
                                log_entry = {
                                    "ts": datetime.now(timezone.utc).isoformat(),
                                    "topic": topic,
                                    "payload": payload_short
                                }
                                mqtt_logger.info(json.dumps(log_entry, ensure_ascii=False))
                            except Exception:
                                pass

                            # Write to full payload file if enabled
                            if full_payload_enabled:
                                _write_full_payload(topic, payload)
                    except Exception:
                        pass
                    # Update runtime state immediately when a message for a device arrives
                    try:
                        topic = getattr(msg, "topic", "") or ""
                        parts = topic.split("/")
                        cloud_serial = None
                        if len(parts) > 1 and parts[0] == "device":
                            cloud_serial = parts[1]
                        if cloud_serial:
                            try:
                                from datetime import datetime, timezone
                                now = datetime.now(timezone.utc)
                                ts = _iso_utc(now)
                                # Unconditionally mark runtime connected when any report arrives
                                _runtime_state["connected"] = True
                                _runtime_state["last_seen"] = ts
                                _runtime_state["cloud_serial"] = cloud_serial
                                if not _runtime_state.get("connected_since"):
                                    _runtime_state["connected_since"] = ts
                                # keep broker/client_id/protocol as previously set
                                
                                # Update live_state for JSON Inspector
                                if topic.endswith("/report"):
                                    try:
                                        from app.services.live_state import set_live_state
                                        payload_str = getattr(msg, "payload", b"")
                                        if isinstance(payload_str, bytes):
                                            payload_str = payload_str.decode("utf-8", errors="replace")
                                        parsed = json.loads(payload_str)
                                        set_live_state(cloud_serial, parsed)

                                        # === JOB TRACKING ===
                                        try:
                                            from app.database import engine
                                            from sqlmodel import Session, select
                                            from app.models.job import Job
                                            from app.models.printer import Printer
                                            from datetime import datetime

                                            gcode_state = parsed.get("print", {}).get("gcode_state", "").upper()

                                            if gcode_state in ["RUNNING", "PRINTING"]:
                                                with Session(engine) as session:
                                                    # Find printer
                                                    printer = session.exec(
                                                        select(Printer).where(Printer.cloud_serial == cloud_serial)
                                                    ).first()

                                                    if printer:
                                                        # Check if job already exists
                                                        existing_job = session.exec(
                                                            select(Job)
                                                            .where(Job.printer_id == printer.id)
                                                            .where(Job.finished_at == None)
                                                        ).first()

                                                        if not existing_job:
                                                            # Create new job
                                                            job_name = (
                                                                parsed.get("print", {}).get("subtask_name") or
                                                                parsed.get("print", {}).get("gcode_file") or
                                                                "Unnamed Job"
                                                            )

                                                            new_job = Job(
                                                                printer_id=printer.id,
                                                                name=job_name,
                                                                started_at=datetime.utcnow(),
                                                                filament_used_mm=0,
                                                                filament_used_g=0,
                                                                status="running"
                                                            )

                                                            session.add(new_job)
                                                            session.commit()
                                                            session.refresh(new_job)

                                                            logger = logging.getLogger("3D_drucker")
                                                            logger.info(f"[JOB CREATED] job_id={new_job.id} name={new_job.name} printer={printer.name}")
                                        except Exception as job_err:
                                            print(f"[mqtt_runtime] ERROR job tracking: {job_err}")
                                            import traceback
                                            traceback.print_exc()
                                    except Exception as e:
                                        print(f"[mqtt_runtime] ERROR set_live_state: {e}")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if callable(prev_on_message):
                        return prev_on_message(c, u, msg)

                inner.on_message = _runtime_on_message
                # Set userdata for the underlying paho client so on_connect can
                # subscribe to the specific cloud_serial topic.
                try:
                    connection_id = str(uuid4())
                    cloud_serial = config.get("cloud_serial")
                    inner.user_data_set({
                        "connection_id": connection_id,
                        "client_id": client_id,
                        "cloud_serial": cloud_serial,
                    })
                except Exception:
                    # Non-fatal: don't break connect if userdata cannot be set
                    pass
        except Exception:
            # Never fail connect due to stats wiring
            pass

        # 3) Connect
        print(f"[MQTT] CONNECT host={host} port={port} tls={tls} user={username}")
        try:
            logging.getLogger("3D_drucker").info(f"connect host={host} port={port} tls={tls} client_id={client_id}")
        except Exception:
            pass
        client.connect()

        # 4) Set instance immediately so disconnect() can clean up on timeout
        _client_instance = client
        _client_config = _RuntimeConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            client_id=client_id,
            protocol=protocol,
            tls=tls,
            model=model,
            cloud_serial=config.get("cloud_serial"),
            printer_id=config.get("printer_id"),
            printer_name=config.get("printer_name"),
        )

        # 5) Wait (max 5s) until the underlying paho client is actually connected.
        # NOTE: Do NOT consider 'connected' == application-level connected here.
        # The UI should rely solely on _runtime_state which will be updated
        # when a device/<cloud_serial>/report arrives.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if _is_connected(client):
                # Underlying MQTT transport connected — report connect success
                # to caller. Mark runtime_state as connected so UI sees state
                # immediately, even bevor device/<serial>/report eintrifft.
                now = datetime.now(timezone.utc)
                ts = _iso_utc(now)
                _transport_connected_since = now
                try:
                    _runtime_state.update({
                        "connected": True,
                        "connected_since": ts,
                        "last_seen": ts if not _runtime_state.get("last_seen") else _runtime_state.get("last_seen"),
                    })
                except Exception:
                    pass
                try:
                    logging.getLogger("3D_drucker").info(f"connected host={host} client_id={client_id}")
                except Exception:
                    pass
                return {
                    "success": True,
                    "connected": True,
                    "host": host,
                    "port": port,
                    "client_id": client_id,
                    "protocol": protocol,
                }
            time.sleep(0.1)

        # If we get here, connect did not complete deterministically.
        try:
            logging.getLogger("MQTT").error(f"connect timeout host={host} client_id={client_id}")
        except Exception:
            pass
        disconnect()
        # Also ensure runtime state reflects disconnected
        try:
            _runtime_state.update({"connected": False, "connected_since": None})
        except Exception:
            pass
        return {
            "success": False,
            "error": "connect timeout (5s) - broker unreachable or auth failed",
        }

    except Exception as exc:
        # 4) Exception: reset instance
        _client_instance = None
        _client_config = None
        _connected_since = None
        try:
            logging.getLogger("3D_drucker").error(f"connect error: {exc}")
        except Exception:
            pass
        return {"success": False, "error": str(exc)}


def disconnect() -> Dict[str, Any]:
    """Disconnect the single runtime instance, if any."""
    global _client_instance, _client_config, _connected_since, _transport_connected_since

    if _client_instance is None:
        _reset_topic_stats()
        return {"success": True, "connected": False, "note": "already disconnected"}

    try:
        if hasattr(_client_instance, "disconnect"):
            # If the class ever grows a proper API, prefer it.
            _client_instance.disconnect()  # type: ignore[attr-defined]
        else:
            inner = getattr(_client_instance, "client", None)
            if inner is not None:
                try:
                    if hasattr(inner, "loop_stop"):
                        inner.loop_stop()
                finally:
                    if hasattr(inner, "disconnect"):
                        inner.disconnect()
    finally:
        _client_instance = None
        _client_config = None
        _connected_since = None
        _transport_connected_since = None
        _reset_topic_stats()
        _reset_subscribed_topics()
        try:
            # mark runtime as disconnected; keep broker/cloud_serial metadata
            _runtime_state.update({"connected": False, "connected_since": None})
        except Exception:
            pass
        try:
            logging.getLogger("3D_drucker").info("disconnect")
        except Exception:
            pass

    return {"success": True, "connected": False}


def status() -> Dict[str, Any]:
    """Return minimal runtime status for the single instance."""
    # Return the explicit runtime state only (no guessing, no heuristics).
    try:
        # Shallow copy as base
        base = dict(_runtime_state)

        # Wenn Transport verbunden ist, aber runtime_state.connected False, setze True
        transport_connected = _client_instance is not None and _is_connected(_client_instance)
        if transport_connected and not base.get("connected"):
            base["connected"] = True

        # connected_since ableiten
        if not base.get("connected_since"):
            if _transport_connected_since:
                base["connected_since"] = _iso_utc(_transport_connected_since)
            elif _connected_since:
                base["connected_since"] = _iso_utc(_connected_since)

        # Aggregate topic/message statistics
        stats = _aggregate_topic_stats()
        base.update(stats)

        # QoS fallback
        if base.get("qos") is None:
            base["qos"] = 1

        # Uptime derived from connected_since
        base["uptime"] = _format_uptime(base.get("connected_since"))

        # last_message_time fallback to last_seen if missing
        if not base.get("last_message_time") and base.get("last_seen"):
            base["last_message_time"] = base.get("last_seen")

        return base
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
