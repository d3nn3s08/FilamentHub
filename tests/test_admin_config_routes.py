from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import engine
from app.models.material import Material
from app.routes.config_routes import DEFAULT_CONFIG
from app.main import app
from tests.helpers import TEST_ADMIN_PASSWORD


def _admin_client():
    client = TestClient(app)
    resp = client.post("/api/admin/login", data={"password": TEST_ADMIN_PASSWORD})
    assert resp.status_code == 200
    token = resp.cookies.get("admin_token")
    assert token
    client.cookies.set("admin_token", token)
    return client


def test_admin_delete_material_success():
    client = TestClient(app)
    payload = {
        "name": "delete-me",
        "brand": "test",
        "density": 1.24,
        "diameter": 1.75,
    }
    create_resp = client.post("/api/materials/", json=payload)
    assert create_resp.status_code == 201
    material_id = create_resp.json()["id"]

    admin = _admin_client()
    resp = admin.post("/api/admin/delete", json={"table": "material", "id": material_id})
    assert resp.status_code == 200
    assert resp.json()["success"]

    with Session(engine) as session:
        assert session.get(Material, material_id) is None


def test_admin_delete_requires_auth():
    client = TestClient(app)
    resp = client.post("/api/admin/delete", json={"table": "material", "id": "x"})
    assert resp.status_code == 401


def test_admin_delete_unknown_table():
    admin = _admin_client()
    resp = admin.post("/api/admin/delete", json={"table": "unknown", "id": "x"})
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "Unbekannte Tabelle" in resp.json()["error"]


def test_admin_delete_missing_values():
    admin = _admin_client()
    resp = admin.post("/api/admin/delete", json={"table": "", "id": ""})
    assert resp.status_code == 200
    json_body = resp.json()
    assert json_body["success"] is False
    assert "Tabelle und ID erforderlich" in json_body["error"]


def test_config_update_rejects_empty_payload():
    client = TestClient(app)
    resp = client.put("/api/config", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No valid keys provided"


def test_config_update_respects_logging_validity():
    client = TestClient(app)
    resp = client.put(
        "/api/config",
        json={
            "logging": {"level": "NOTLEVEL", "keep_days": -5},
            "debug": {"system_health": {"warn_latency_ms": 50, "error_latency_ms": 40}},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["logging"]["level"] == DEFAULT_CONFIG["logging"]["level"]
    assert body["logging"]["keep_days"] == DEFAULT_CONFIG["logging"]["keep_days"]
    assert body["debug"]["system_health"]["warn_latency_ms"] == DEFAULT_CONFIG["debug"]["system_health"]["warn_latency_ms"]
    assert body["debug"]["system_health"]["error_latency_ms"] == DEFAULT_CONFIG["debug"]["system_health"]["error_latency_ms"]
