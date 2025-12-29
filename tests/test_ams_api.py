from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import app.services.live_state as live_state_module
from app.routes import ams_routes


@pytest.fixture()
def client(monkeypatch):
    sample_payload = {
        "ams": {
            "ams": [
                {
                    "ams_id": 1,
                    "temp": 22.5,
                    "humidity": 55,
                    "tray": [
                        {
                            "tray_id": 0,
                            "tray_uuid": "uuid-1",
                            "tag_uid": "tag-1",
                            "remain": 0.75,
                            "total_len": 123
                        }
                    ]
                }
            ]
        }
    }

    in_memory = {
        "DEV123": {
            "device": "DEV123",
            "ts": "2025-12-28T00:00:00Z",
            "payload": sample_payload,
        },
        "DEV_EMPTY": {
            "device": "DEV_EMPTY",
            "ts": "2025-12-28T00:00:01Z",
            "payload": {},
        },
    }

    monkeypatch.setattr(live_state_module, "get_all_live_state", lambda: in_memory)
    monkeypatch.setattr(live_state_module, "get_live_state", lambda d: in_memory.get(d))

    app = FastAPI()
    app.include_router(ams_routes.router)
    return TestClient(app)


def test_list_ams(client):
    resp = client.get("/api/ams/")
    assert resp.status_code == 200
    data = resp.json()
    assert "devices" in data
    devices = data["devices"]
    assert any(d.get("device_serial") == "DEV123" for d in devices)
    dev = next(d for d in devices if d.get("device_serial") == "DEV123")
    assert dev.get("ts") == "2025-12-28T00:00:00Z"
    assert dev.get("online") is True
    ams_units = dev.get("ams_units")
    assert isinstance(ams_units, list)
    assert len(ams_units) == 1
    unit = ams_units[0]
    assert unit.get("ams_id") == 1
    assert unit.get("temp") == 22.5
    assert unit.get("humidity") == 55
    trays = unit.get("trays")
    assert isinstance(trays, list)
    assert len(trays) == 1
    tray = trays[0]
    assert tray.get("slot") == 0
    assert tray.get("tray_uuid") == "uuid-1"
    assert tray.get("tag_uid") == "tag-1"
    assert tray.get("remain_percent") == 0.75


def test_get_single_device(client):
    resp = client.get("/api/ams/DEV123")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("device_serial") == "DEV123"
    assert data.get("online") is True

    resp2 = client.get("/api/ams/NONEXISTENT")
    assert resp2.status_code == 404


def test_empty_payload_device(client):
    resp = client.get("/api/ams/DEV_EMPTY")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("device_serial") == "DEV_EMPTY"
    assert data.get("online") is False
    assert data.get("ams_units") == []
