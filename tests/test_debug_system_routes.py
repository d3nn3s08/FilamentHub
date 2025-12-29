import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import debug_system_routes as dsr


class DummyMQTTClient:
    def __init__(self, connected: bool = True):
        self._connected = connected

    def is_connected(self):
        if self._connected is None:
            raise RuntimeError("state unknown")
        return self._connected


@pytest.fixture(autouse=True)
def reset_debug_state():
    orig_clients = dict(dsr.mqtt_clients)
    orig_connections = set(dsr.active_connections)
    orig_last_ws = dsr.last_ws_activity_ts
    orig_ws_clients = dsr.active_ws_clients
    orig_last_err = dsr.last_connect_error
    orig_build_env = dsr.build_environment_snapshot
    orig_get_runtime = dsr.get_runtime_metrics
    orig_load_config = dsr._load_config

    yield

    dsr.mqtt_clients.clear()
    dsr.mqtt_clients.update(orig_clients)
    dsr.active_connections.clear()
    dsr.active_connections.update(orig_connections)
    dsr.last_ws_activity_ts = orig_last_ws
    dsr.active_ws_clients = orig_ws_clients
    dsr.last_connect_error = orig_last_err
    dsr.build_environment_snapshot = orig_build_env
    dsr.get_runtime_metrics = orig_get_runtime
    dsr._load_config = orig_load_config


def _patch_common(monkeypatch, avg_ms, rpm, config=None):
    monkeypatch.setattr(dsr, "build_environment_snapshot", lambda req: {"mode": "test"})
    monkeypatch.setattr(
        dsr,
        "get_runtime_metrics",
        lambda: {"avg_response_ms": avg_ms, "requests_per_minute": rpm, "avg_response_ms": avg_ms},
    )
    if config is None:
        config = {"debug": {"system_health": {"enabled": True, "warn_latency_ms": 100, "error_latency_ms": 200}}}
    monkeypatch.setattr(dsr, "_load_config", lambda session: config)


def test_system_status_reports_disabled_mqtt_and_critical_health(monkeypatch):
    _patch_common(monkeypatch, avg_ms=250, rpm=10)
    dsr.mqtt_clients.clear()
    dsr.active_connections.clear()
    dsr.active_ws_clients = 0
    dsr.last_ws_activity_ts = None
    client = TestClient(app)

    resp = client.get("/api/debug/system_status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mqtt"]["state"] == "disabled"
    assert body["websocket"]["state"] in ("listening", "idle")
    assert body["runtime"]["state"] == "active"
    assert body["system_health"]["status"] == "critical"
    assert any("High average response time" in reason for reason in body["system_health"]["reasons"])
    assert body["environment"]["mode"] == "test"


def test_system_status_handles_connected_mqtt_and_missing_latency(monkeypatch):
    _patch_common(monkeypatch, avg_ms=None, rpm=0)
    dsr.mqtt_clients.clear()
    dsr.mqtt_clients["host:1883"] = DummyMQTTClient(connected=True)
    dsr.active_connections.clear()
    dsr.active_connections.add(object())
    dsr.active_ws_clients = 1
    dsr.last_ws_activity_ts = time.time()
    dsr.last_connect_error = 404
    client = TestClient(app)

    resp = client.get("/api/debug/system_status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mqtt"]["state"] == "connected"
    assert body["mqtt"]["last_error"] == "404"
    assert body["websocket"]["state"] == "connected"
    assert "Average response time not available" in body["system_health"]["reasons"]
    assert "Nicht verbunden" not in body["system_health"]["reasons"]
    assert body["system_health"]["status"] == "warning"
