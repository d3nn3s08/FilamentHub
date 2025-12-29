
from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def get_unique_material_data():
    return {
        "name": f"TestPLA_{uuid.uuid4().hex[:8]}",
        "type": "PLA",
        "color": "Rot",
        "manufacturer": "TestMaker",
        "density": 1.24,
        "diameter": 1.75
    }

def get_unique_spool_data():
    return {
        "weight": 1000,
        "external_id": f"spool-{uuid.uuid4().hex[:8]}",
        "printer_slot": "AMS-2",
        "manufacturer": "TestMaker",
        "color": "Rot"
    }

material_data = get_unique_material_data()
spool_data = get_unique_spool_data()

material_id = None
spool_id = None

def test_crud_material():
    global material_id
    # Create with unique data
    test_material = get_unique_material_data()
    response = client.post("/api/materials", json=test_material)
    assert response.status_code == 201
    material_id = response.json()["id"]
    # Get
    response = client.get(f"/api/materials/{material_id}")
    assert response.status_code == 200
    assert response.json()["name"] == test_material["name"]
    # List
    response = client.get("/api/materials")
    assert response.status_code == 200
    assert any(m["id"] == material_id for m in response.json())
    # Update
    update_data = test_material.copy()
    update_data["density"] = 1.30
    response = client.put(f"/api/materials/{material_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["density"] == 1.30
    # Delete
    response = client.delete(f"/api/materials/{material_id}")
    assert response.status_code == 204
    response = client.get(f"/api/materials/{material_id}")
    assert response.status_code == 404

def test_crud_spool():
    global spool_id
    # Material für Spool anlegen with unique data
    test_material = get_unique_material_data()
    response = client.post("/api/materials", json=test_material)
    assert response.status_code == 201
    mat_id = response.json()["id"]
    # Create Spool with unique data
    test_spool = get_unique_spool_data()
    test_spool["material_id"] = mat_id
    response = client.post("/api/spools", json=test_spool)
    assert response.status_code == 201
    spool_id = response.json()["id"]
    # Get
    response = client.get(f"/api/spools/{spool_id}")
    assert response.status_code == 200
    assert response.json()["external_id"] == test_spool["external_id"]
    # List
    response = client.get("/api/spools")
    assert response.status_code == 200
    assert any(s["id"] == spool_id for s in response.json())
    # Update
    update_data = test_spool.copy()
    update_data["weight"] = 900
    response = client.put(f"/api/spools/{spool_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["weight"] == 900
    # Delete
    response = client.delete(f"/api/spools/{spool_id}")
    assert response.status_code == 204
    response = client.get(f"/api/spools/{spool_id}")
    assert response.status_code == 404
