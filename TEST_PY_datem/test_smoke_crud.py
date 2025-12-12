
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

material_data = {
    "name": "TestPLA_unique_20251127",
    "type": "PLA",
    "color": "Rot",
    "manufacturer": "TestMaker",
    "density": 1.24,
    "diameter": 1.75
}

spool_data = {
    "weight": 1000,
    "external_id": "spool-456-20251127",
    "printer_slot": "AMS-2",
    "manufacturer": "TestMaker",
    "color": "Rot"
}

material_id = None
spool_id = None

def test_crud_material():
    global material_id
    # Create
    response = client.post("/api/materials", json=material_data)
    assert response.status_code == 201
    material_id = response.json()["id"]
    # Get
    response = client.get(f"/api/materials/{material_id}")
    assert response.status_code == 200
    assert response.json()["name"] == material_data["name"]
    # List
    response = client.get("/api/materials")
    assert response.status_code == 200
    assert any(m["id"] == material_id for m in response.json())
    # Update
    update_data = material_data.copy()
    update_data["color"] = "Blau"
    response = client.put(f"/api/materials/{material_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["color"] == "Blau"
    # Delete
    response = client.delete(f"/api/materials/{material_id}")
    assert response.status_code == 204
    response = client.get(f"/api/materials/{material_id}")
    assert response.status_code == 404

def test_crud_spool():
    global spool_id
    # Material für Spool anlegen
    response = client.post("/api/materials", json=material_data)
    assert response.status_code == 201
    spool_data["material_id"] = response.json()["id"]
    # Create Spool
    response = client.post("/api/spools", json=spool_data)
    assert response.status_code == 201
    spool_id = response.json()["id"]
    # Get
    response = client.get(f"/api/spools/{spool_id}")
    assert response.status_code == 200
    assert response.json()["external_id"] == spool_data["external_id"]
    # List
    response = client.get("/api/spools")
    assert response.status_code == 200
    assert any(s["id"] == spool_id for s in response.json())
    # Update
    update_data = spool_data.copy()
    update_data["weight"] = 900
    response = client.put(f"/api/spools/{spool_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["weight"] == 900
    # Delete
    response = client.delete(f"/api/spools/{spool_id}")
    assert response.status_code == 204
    response = client.get(f"/api/spools/{spool_id}")
    assert response.status_code == 404
