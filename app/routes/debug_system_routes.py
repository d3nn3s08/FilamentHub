import time
from typing import Dict

from fastapi import APIRouter
from sqlalchemy import text
from sqlmodel import Session

from app.database import engine
from app.monitoring.runtime_monitor import get_runtime_metrics
from app.routes.config_routes import _load_config  # type: ignore

try:
    from app.routes.mqtt_routes import (
        mqtt_clients,
        active_connections,
        last_ws_ping,
        last_connect_error,
        active_ws_clients,
        last_ws_activity_ts,
    )
except Exception:  # pragma: no cover - fallback
    mqtt_clients: Dict[str, object] = {}
    active_connections = set()
    last_ws_ping = None
    last_connect_error = None
    active_ws_clients = 0
    last_ws_activity_ts = None

router = APIRouter(prefix="/api/debug", tags=["Debug System"])


@router.get("/system_status")
def system_status():
    api_state = {"state": "online"}

    db_state = {"state": "error"}
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
            db_state["state"] = "connected"
    except Exception:
        db_state["state"] = "error"

    mqtt_state: Dict[str, object] = {"state": "disabled"}
    try:
        if mqtt_clients:
            connection_id, client = next(iter(mqtt_clients.items()))
            host, port = None, None
            try:
                if ":" in connection_id:
                    host, port = connection_id.split(":", 1)
            except Exception:
                host, port = None, None
            mqtt_state["host"] = host
            mqtt_state["port"] = int(port) if port and port.isdigit() else port

            try:
                if client.is_connected():
                    mqtt_state["state"] = "connected"
                else:
                    mqtt_state["state"] = "disconnected"
            except Exception:
                mqtt_state["state"] = "error"

            if last_connect_error is not None:
                mqtt_state["last_error"] = str(last_connect_error)
        else:
            mqtt_state["state"] = "disabled"
    except Exception as exc:
        mqtt_state = {"state": "error", "last_error": str(exc)}

    websocket_state: Dict[str, object] = {"state": "offline"}
    try:
        now = time.time()
        clients = active_ws_clients if active_ws_clients is not None else 0
        websocket_state["clients"] = clients
        if last_ws_activity_ts:
            websocket_state["last_activity_s"] = round(now - last_ws_activity_ts, 1)
        if active_connections is None:
            websocket_state["state"] = "offline"
        else:
            if clients > 0:
                websocket_state["state"] = "connected"
            else:
                if last_ws_activity_ts:
                    delta = now - last_ws_activity_ts
                    websocket_state["last_activity_s"] = round(delta, 1)
                    websocket_state["state"] = "idle" if delta < 30 else "listening"
                else:
                    websocket_state["state"] = "listening"
    except Exception:
        websocket_state = {"state": "offline"}

    # WebSocket semantisch: connected > idle > listening; offline nur bei fehlender Erreichbarkeit
    try:
        if active_connections is None:
            websocket_state = {"state": "offline"}
        else:
            count = len(active_connections)
            now = time.time()
            if count > 0:
                websocket_state = {"state": "connected", "clients": count}
            else:
                # Kein aktiver Client, aber Endpoint existiert
                ws_state = "listening"
                if last_ws_ping:
                    diff = round(now - last_ws_ping, 1)
                    websocket_state["last_ping_s"] = diff
                    if diff < 30:
                        ws_state = "idle"
                websocket_state["state"] = ws_state
    except Exception:
        websocket_state = {"state": "offline"}

    runtime_state = get_runtime_metrics()
    try:
        rpm = runtime_state.get("requests_per_minute", 0) if isinstance(runtime_state, dict) else 0
        rpm_num = float(rpm) if rpm is not None else 0.0
        runtime_state["requests_per_minute"] = rpm_num
        runtime_state["state"] = "active" if rpm_num > 0 else "idle"
    except Exception:
        runtime_state = {"requests_per_minute": 0, "avg_response_ms": None, "state": "idle"}

    # System health with thresholds from settings/config
    def _load_health_thresholds():
        enabled = True
        warn = 600
        error = 1200
        try:
            with Session(engine) as s:
                cfg = _load_config(s)
                sh = cfg.get("debug", {}).get("system_health", {})
                enabled = bool(sh.get("enabled", True))
                warn = int(sh.get("warn_latency_ms", warn))
                error = int(sh.get("error_latency_ms", error))
        except Exception:
            pass
        return enabled, warn, error

    enabled, warn_threshold, error_threshold = _load_health_thresholds()
    reasons = []
    health_status = "ok"
    try:
        avg_ms = runtime_state.get("avg_response_ms")
        mqtt_state_value = mqtt_state.get("state")
        if not enabled:
            reasons = ["Health monitoring disabled"]
        else:
            if isinstance(avg_ms, (int, float)):
                if avg_ms >= error_threshold:
                    health_status = "critical"
                    reasons.append(f"High average response time ({int(round(avg_ms))} ms >= {error_threshold} ms)")
                elif avg_ms >= warn_threshold:
                    health_status = "warning"
                    reasons.append(f"High average response time ({int(round(avg_ms))} ms >= {warn_threshold} ms)")
            else:
                health_status = "warning"
                reasons.append("Average response time not available")
                reasons.append("MQTT service is disabled")
                if health_status == "ok":
                    health_status = "warning"
            # Service-MQTT ist immer abgeleitet vom Runtime-MQTT-Status
            if mqtt_state_value != "connected":
                reasons.append("Nicht verbunden")
                if health_status == "ok":
                    health_status = "warning"
    except Exception:
        health_status = "warning"
        if not reasons:
            reasons = ["Health monitoring unavailable"]

    if health_status == "ok" and not reasons:
        reasons = ["System is operating normally"]
    if health_status == "warning" and not reasons:
        reasons = ["Some services require attention"]

    system_health = {"status": health_status, "reasons": reasons}

    return {
        "api": api_state,
        "db": db_state,
        "mqtt": mqtt_state,
        "websocket": websocket_state,
        "runtime": runtime_state,
        "system_health": system_health,
    }
