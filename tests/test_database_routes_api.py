import sqlite3
import os
import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
import app.routes.database_routes as db_routes


def make_test_db(tmp_path: Path):
    db_path = tmp_path / "filament_test.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    # Minimal table used by endpoints
    cur.execute("CREATE TABLE material (id TEXT PRIMARY KEY, name TEXT)")
    cur.execute("INSERT INTO material (id, name) VALUES (?,?)", ("m1", "Mat1"))
    conn.commit()
    conn.close()

    # Point the module to the test DB
    db_routes.DB_PATH = str(db_path)
    return db_path


def test_get_database_info(tmp_path):
    db = make_test_db(tmp_path)

    client = TestClient(app)
    resp = client.get('/api/database/info')

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert data.get('exists') is True
    assert 'tables' in data
    assert 'material' in data.get('tables', [])


def test_post_editor_create_row_and_query(tmp_path):
    make_test_db(tmp_path)

    client = TestClient(app)

    # Insert new row via editor endpoint
    payload = {"sql": "INSERT INTO material (id, name) VALUES ('m2', 'Mat2')"}
    resp = client.post('/api/database/editor', json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data.get('success') is True

    # Verify with query endpoint
    qresp = client.get('/api/database/query', params={"sql": "SELECT * FROM material WHERE id='m2'"})
    assert qresp.status_code == 200
    qdata = qresp.json()
    assert qdata.get('success') is True
    assert qdata.get('row_count', 0) == 1


def test_delete_row_success(tmp_path):
    make_test_db(tmp_path)

    client = TestClient(app)

    # Delete existing row (m1)
    resp = client.delete('/api/database/row', params={"table": "material", "id": "m1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get('success') is True

    # Deleting again should return 404 from endpoint
    resp2 = client.delete('/api/database/row', params={"table": "material", "id": "m1"})
    assert resp2.status_code == 404


def test_post_editor_invalid_payload(tmp_path):
    make_test_db(tmp_path)

    client = TestClient(app)

    # Empty SQL -> should return 400
    resp = client.post('/api/database/editor', json={"sql": ""})
    assert resp.status_code == 400
    err = resp.json()
    assert 'detail' in err
