import pytest

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.database import engine
from app.main import app
from app.models.settings import Setting
from app.routes import notification_routes as nr
from app.routes.notification_routes import DEFAULT_NOTIFICATIONS

client = TestClient(app)


def cleanup_notifications():
    with Session(engine) as session:
        session.exec(delete(Setting).where(Setting.key == "notifications_config"))
        session.commit()


def test_get_notifications_config_defaults(tmp_path):
    cleanup_notifications()
    resp = client.get("/api/notifications-config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notifications"][0]["id"] == DEFAULT_NOTIFICATIONS[0]["id"]
    cleanup_notifications()


def test_save_notifications_config_validation():
    cleanup_notifications()
    resp = client.post("/api/notifications-config", json="not-a-list")
    assert resp.status_code == 400
    assert "Ungültiges Format" in resp.json()["detail"]
    cleanup_notifications()


def test_save_notifications_config_persists():
    cleanup_notifications()
    payload = {"notifications": [{"id": "custom", "message": "ok"}]}
    resp = client.post("/api/notifications-config", json=payload)
    assert resp.status_code == 200
    assert resp.json()["notifications"][0]["id"] == "custom"
    cleanup_notifications()


def test_trigger_notification_success(monkeypatch):
    cleanup_notifications()
    payload = {"notifications": [{"id": "alert", "message": "msg"}]}
    client.post("/api/notifications-config", json=payload)

    sent = []
    async def fake_broadcast(notification):
        sent.append(notification["id"])

    monkeypatch.setattr(nr, "broadcast_notification", fake_broadcast)
    resp = client.post("/api/notifications-trigger", json={"id": "alert"})
    assert resp.status_code == 200
    assert resp.json()["success"]
    assert sent == ["alert"]
    cleanup_notifications()


def test_trigger_notification_missing():
    cleanup_notifications()
    resp = client.post("/api/notifications-trigger", json={})
    assert resp.status_code == 400
    assert "Notification id fehlt" in resp.json()["detail"]
    cleanup_notifications()


def test_trigger_notification_disabled(monkeypatch):
    cleanup_notifications()
    payload = {"notifications": [{"id": "alert", "message": "msg", "enabled": False}]}
    client.post("/api/notifications-config", json=payload)
    resp = client.post("/api/notifications-trigger", json={"id": "alert"})
    assert resp.status_code == 400
    assert "deaktiviert" in resp.json()["detail"]
    cleanup_notifications()


def test_validate_notifications_rejects_invalid_format():
    with pytest.raises(HTTPException):
        nr._validate_notifications("not a list")


def test_validate_notifications_requires_id_and_message():
    with pytest.raises(HTTPException):
        nr._validate_notifications({"notifications": [{"id": "", "message": ""}]})


def test_ensure_notification_config_resets_on_corrupted_value():
    cleanup_notifications()
    with Session(engine) as session:
        session.add(Setting(key="notifications_config", value="not-json"))
        session.commit()

    resp = client.get("/api/notifications-config")
    assert resp.status_code == 200
    assert resp.json()["notifications"][0]["id"] == DEFAULT_NOTIFICATIONS[0]["id"]
    cleanup_notifications()
