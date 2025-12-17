from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import datetime, timezone
import time
from threading import Lock
from typing import Any, Dict, Optional

from app.services.printer_mqtt_client import PrinterMQTTClient
from uuid import uuid4
from services.printer_service import PrinterService


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
                        # Add message to live buffer for UI
                        payload = getattr(msg, "payload", b"")
                        if isinstance(payload, bytes):
                            try:
                                payload = payload.decode("utf-8", errors="replace")
                            except Exception:
                                payload = str(payload)
                        _add_message(topic, payload, datetime.now(timezone.utc))
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
                                now = datetime.now(timezone.utc)
                                ts = _iso_utc(now)
                                # Unconditionally mark runtime connected when any report arrives
                                _runtime_state["connected"] = True
                                _runtime_state["last_seen"] = ts
                                _runtime_state["cloud_serial"] = cloud_serial
                                if not _runtime_state.get("connected_since"):
                                    _runtime_state["connected_since"] = ts
                                # keep broker/client_id/protocol as previously set
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
