import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.database import engine
from app.main import app
from app.models.settings import Setting
from app.routes.config_routes import DEFAULT_CONFIG, _validate_payload

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.json"


def _read_config():
    return CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else ""


def _restore_config(content: str):
    if content == "":
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
        return
    CONFIG_PATH.write_text(content, encoding="utf-8")


def test_get_config_current_applies_file_fallback(tmp_path):
    original = _read_config()
    bad_cfg = {
        "debug": {
            "system_health": {
                "warn_latency_ms": 10,
                "error_latency_ms": 20,
            }
        }
    }
    CONFIG_PATH.write_text(json.dumps(bad_cfg), encoding="utf-8")
    client = TestClient(app)
    try:
        response = client.get("/api/config/current")
        assert response.status_code == 200
        payload = response.json()
        assert payload["debug"]["system_health"]["warn_latency_ms"] == DEFAULT_CONFIG["debug"]["system_health"]["warn_latency_ms"]
        assert payload["debug"]["system_health"]["error_latency_ms"] == DEFAULT_CONFIG["debug"]["system_health"]["error_latency_ms"]
    finally:
        _restore_config(original)


@pytest.mark.usefixtures("reset_db")
def test_get_config_current_applies_db_overrides():
    keys = [
        "debug.runtime.enabled",
        "debug.runtime.poll_interval_ms",
    ]
    with Session(engine) as session:
        session.exec(delete(Setting).where(Setting.key.in_(keys)))
        session.add_all(
            [
                Setting(key="debug.runtime.enabled", value="false"),
                Setting(key="debug.runtime.poll_interval_ms", value="700"),
            ]
        )
        session.commit()
    client = TestClient(app)
    try:
        response = client.get("/api/config/current")
        assert response.status_code == 200
        data = response.json()
        assert data["debug"]["runtime"]["enabled"] is False
        assert data["debug"]["runtime"]["poll_interval_ms"] == 700
    finally:
        with Session(engine) as session:
            session.exec(delete(Setting).where(Setting.key.in_(keys)))
            session.commit()


def test_update_config_persists_sanitized_payload():
    client = TestClient(app)
    payload = {
        "logging": {
            "level": "NOTLEVEL",
            "modules": {
                "app": {"enabled": False},
                "mqtt": {"enabled": "yes"},
            },
            "keep_days": -1,
        }
    }
    response = client.put("/api/config", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["logging"]["level"] == DEFAULT_CONFIG["logging"]["level"]
    assert body["logging"]["modules"]["app"]["enabled"] is True
    assert body["logging"]["modules"]["mqtt"]["enabled"] is False
    assert body["logging"]["keep_days"] == DEFAULT_CONFIG["logging"]["keep_days"]
    with Session(engine) as session:
        for key in [
            "logging.level",
            "logging.modules.app",
            "logging.modules.mqtt",
            "logging.keep_days",
        ]:
            assert session.get(Setting, key) is not None
        session.exec(delete(Setting).where(Setting.key.like("logging%")))
        session.commit()


def test_validate_payload_parses_fingerprint_ports_list():
    validated = _validate_payload({"fingerprint.ports": "8883,6000"})
    assert validated["fingerprint.ports"] == [8883, 6000]
    fallback = _validate_payload({"fingerprint.ports": "invalid"})
    assert fallback["fingerprint.ports"] == DEFAULT_CONFIG["fingerprint"]["ports"]


def test_validate_payload_accepts_flat_module_bool():
    validated = _validate_payload({"logging.modules.app": False})
    assert validated["logging.modules.app"] is False
