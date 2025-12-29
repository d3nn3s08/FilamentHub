import json
import os

from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.main import app
from app.models.settings import Setting
from app.routes.settings_routes import (
    DEFAULTS,
    PRO_CONFIG_DEFAULTS,
    router as settings_router,
    _normalize_float,
    _normalize_int,
    _normalize_bool,
    _normalize_enum,
)
from app.services.job_parser import parse_job
from app.services import mqtt_runtime as mr

client = TestClient(app)


def test_parse_job_with_printer_map():
    payload = {
        "printer": {
            "state": "PRINTING",
            "temperature": {"nozzle": 215, "bed": 60},
            "layer": {"current": 3, "total": 10},
            "job": {"time_remaining": "1200", "file": "part.gcode"},
            "progress": "45",
        }
    }
    parsed = parse_job(payload)
    assert parsed["gcode_state"] == "PRINTING"
    assert parsed["progress_percent"] == 45
    assert parsed["nozzle_temp"] == 215
    assert parsed["layer_total"] == 10


def test_parse_job_generic_payload():
    payload = {
        "print": {
            "gcode_state": "RUNNING",
            "percent": "55",
            "remain_time": "800",
            "job": {"file": "job.gcode"},
            "ams": {"tray_tar": "2", "tray_now": "1"},
            "vt_tray": {"id": "7", "tray_type": "ASM", "tray_color": "red"},
        },
        "upgrade_state": {"status": "idle"},
    }
    parsed = parse_job(payload)
    assert parsed["gcode_state"] == "RUNNING"
    assert parsed["progress_percent"] == 55
    assert parsed["tray_target"] == 2
    assert parsed["virtual_tray"]["id"] == 7
    assert parsed["upgrade_state"] == "idle"


def test_settings_get_and_update_defaults(tmp_path):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ams_mode"] in {"single", "multi"}
    assert isinstance(data["debug.config.scanner_probe_timeout_ms"], int)

    # update success and error
    bad = client.put("/api/settings", json={"ams_mode": "wrong"})
    assert bad.status_code == 400

    resp = client.put("/api/settings", json={"ams_mode": "multi", "debug_center_mode": "pro", "cost.electricity_price_kwh": "0.5"})
    assert resp.status_code == 200
    assert resp.json()["ams_mode"] == "multi"
    assert resp.json()["debug_center_mode"] == "pro"


def test_normalizers():
    assert _normalize_bool(None, True) is True
    assert _normalize_bool("yes", False) is True
    assert _normalize_int("50", 10) == 50
    assert _normalize_int("x", 5) == 5
    assert _normalize_float("2.3", 1.0) == 2.3
    assert _normalize_float("-1", 1.0, minimum=0) == 1.0
    assert _normalize_enum("verbose", {"off", "basic", "verbose"}, "basic") == "verbose"
    assert _normalize_enum("none", {"off", "basic"}, "off") == "off"


def test_mqtt_runtime_topic_stats():
    mr._reset_topic_stats()
    mr._record_topic(" device/test ")
    mr._record_topic("device/test")
    stats = mr._aggregate_topic_stats()
    assert stats["message_count"] == 2
    assert stats["last_message_time"] is not None

    mr.register_subscription(" topic ")
    assert "topic" in mr._subscribed_topics
    mr.unregister_subscription("topic")
    assert "topic" not in mr._subscribed_topics

    messages_before = len(mr.get_messages())
    mr._add_message("device/abc", "payload", mr.datetime.now(mr.timezone.utc))
    assert len(mr.get_messages()) == min(messages_before + 1, mr._messages_max_size)
