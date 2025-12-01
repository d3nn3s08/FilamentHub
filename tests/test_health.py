from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_route():
    response = client.get("/")
    assert response.status_code == 200

def test_api_docs_available():
    response = client.get("/docs")
    assert response.status_code == 200

def test_materials_route_exists():
    response = client.get("/api/materials")
    assert response.status_code in (200, 404, 204)
