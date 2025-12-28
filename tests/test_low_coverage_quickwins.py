from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.database import get_session
from tests.helpers import TEST_ADMIN_PASSWORD


def _fake_empty_printer_session():
    class DummyQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class DummySession:
        def query(self, *args, **kwargs):
            return DummyQuery()

    yield DummySession()


def test_admin_login_success_sets_cookie():
    client = TestClient(app)
    response = client.post("/api/admin/login", data={"password": TEST_ADMIN_PASSWORD})
    assert response.status_code == 200
    assert response.json().get("success") is True
    assert response.cookies.get("admin_token")


def test_admin_login_without_password_fails():
    client = TestClient(app)
    response = client.post("/api/admin/login", data={})
    assert response.status_code == 401
    assert response.json().get("success") is False


def test_admin_greeting_requires_auth():
    """Greeting-Endpoint ist jetzt öffentlich lesbar (bewusste Änderung)"""
    client = TestClient(app)
    response = client.get("/api/admin/greeting")
    # GEÄNDERT: Greeting ist jetzt öffentlich lesbar (kein admin_required)
    assert response.status_code == 200
    assert "greeting_text" in response.json()


def test_create_material_duplicate_name_returns_conflict():
    client = TestClient(app)
    name = f"PLA Black {uuid4().hex}"
    payload = {
        "name": name,
        "brand": "QuickTest",
        "density": 1.24,
        "diameter": 1.75,
    }
    first = client.post("/api/materials/", json=payload)
    assert first.status_code == 201
    second = client.post("/api/materials/", json=payload)
    assert second.status_code == 409
    assert "Material existiert bereits" in second.json().get("detail", "")


def test_mqtt_topic_suggest_fallback_when_no_printers(monkeypatch):
    app.dependency_overrides[get_session] = _fake_empty_printer_session
    client = TestClient(app)
    try:
        response = client.get("/api/mqtt/topics/suggest")
        assert response.status_code == 200
        data = response.json()
        assert "bambu_lab" in data
        assert "device/+/report" in data["bambu_lab"]
        assert "common" in data and "#"
    finally:
        app.dependency_overrides.pop(get_session, None)
