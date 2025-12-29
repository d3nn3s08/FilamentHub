import builtins
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.routes import mqtt_routes as mr

client = TestClient(app)


class DummyClient:
    def __init__(self, *args, **kwargs):
        self._connected = False
        self.userdata = None

    def user_data_set(self, data):
        self.userdata = data

    def tls_set(self, **kwargs):
        pass

    def tls_insecure_set(self, value):
        pass

    def username_pw_set(self, username, password=None):
        pass

    def connect(self, broker, port, keepalive=60):
        self._connected = True

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected

    def subscribe(self, topic):
        return (0, 1)

    def unsubscribe(self, topic):
        pass

    def publish(self, topic, payload, qos=0):
        return type("R", (), {"rc": 0})


class DummyProtocolDetector:
    def detect(self, broker, password, port):
        return {"detected": False}


def _patch_mqtt(monkeypatch):
    monkeypatch.setattr(mr.mqtt, "Client", DummyClient)
    monkeypatch.setattr(mr, "MQTTProtocolDetector", DummyProtocolDetector)
    monkeypatch.setattr(mr.mqtt_runtime, "register_subscription", lambda topic: None)
    monkeypatch.setattr(mr.mqtt_runtime, "clear_subscriptions", lambda: None)
    monkeypatch.setattr(mr.mqtt_runtime, "unregister_subscription", lambda topic: None)


def test_mqtt_connect_and_flow(monkeypatch):
    mr.mqtt_clients.clear()
    _patch_mqtt(monkeypatch)
    resp = client.post("/api/mqtt/connect", json={"broker": "127.0.0.1", "port": 1883, "use_tls": False})
    assert resp.status_code == 200
    connection_id = resp.json()["connection_id"]

    status = client.get("/api/mqtt/status")
    assert status.status_code == 200
    assert status.json()["active_connections"] == 1

    sub = client.post("/api/mqtt/subscribe", json={"topic": "device/test/report"})
    assert sub.status_code == 200
    assert sub.json()["topic"] == "device/test/report"

    pub = client.post("/api/mqtt/publish", params={"topic": "device/test/report", "payload": "hello"})
    assert pub.status_code == 200

    unsub = client.post("/api/mqtt/unsubscribe", json={"topic": "device/test/report"})
    assert unsub.status_code == 200

    client.post(f"/api/mqtt/disconnect?broker=127.0.0.1&port=1883")
    assert connection_id not in mr.mqtt_clients


def test_subscribe_without_connection_returns_error():
    mr.mqtt_clients.clear()
    resp = client.post("/api/mqtt/subscribe", json={"topic": "device/test"})
    assert resp.status_code == 400
    assert "No active MQTT connection" in resp.json()["detail"]


def test_publish_without_connection_returns_error():
    mr.mqtt_clients.clear()
    resp = client.post("/api/mqtt/publish", params={"topic": "device/test", "payload": "hi"})
    assert resp.status_code == 400
    assert "No active MQTT connection" in resp.json()["detail"]


def test_clear_message_buffer_endpoint():
    mr.message_buffer.clear()
    mr.message_buffer.append(mr.MQTTMessage(topic="device/test", payload="payload", timestamp=datetime.utcnow().isoformat()))
    resp = client.post("/api/mqtt/clear-buffer")
    assert resp.status_code == 200
    assert resp.json()["success"]
    assert mr.message_buffer == []


def test_get_messages_endpoint():
    resp = client.get("/api/mqtt/messages", params={"limit": 5})
    assert resp.status_code == 200
    assert "messages" in resp.json()
    assert isinstance(resp.json()["total"], int)


def test_mqtt_status_returns_counts():
    resp = client.get("/api/mqtt/status")
    assert resp.status_code == 200
    assert "active_connections" in resp.json()
    assert isinstance(resp.json()["active_connections"], int)


def test_suggest_topics_returns_structure():
    resp = client.get("/api/mqtt/topics/suggest")
    assert resp.status_code == 200
    body = resp.json()
    assert "bambu_lab" in body
    assert "common" in body


def test_get_mqtt_logs_handles_missing_file(monkeypatch):
    def fake_open(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("builtins.open", fake_open)
    resp = client.get("/api/mqtt/logs")
    assert resp.status_code == 200
    assert "Noch keine MQTT" in resp.text
