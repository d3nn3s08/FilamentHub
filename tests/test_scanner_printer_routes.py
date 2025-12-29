import uuid

from fastapi.testclient import TestClient

from app.routes import scanner_routes as sr
from app.routes import printers as pr
from app.main import app
from tests.helpers import TEST_ADMIN_PASSWORD


client = TestClient(app)


class DummySocketBase:
    def __init__(self, *args, **kwargs):
        pass

    def bind(self, addr):
        pass

    def listen(self, backlog=0):
        pass

    def settimeout(self, timeout):
        pass

    def setblocking(self, flag):
        pass

    def setsockopt(self, *args, **kwargs):
        pass

    def fileno(self):
        return 0

    def close(self):
        pass

    def connect(self, target):
        pass

    def connect_ex(self, target):
        return 1

    def getsockname(self):
        return ("127.0.0.1", 0)
def test_scan_network_returns_printer(monkeypatch):
    async def fake_scan_host(ip, ports, timeout):
        return sr.PrinterInfo(
            ip=ip,
            hostname="test",
            type="bambu",
            port=6000,
            accessible=True,
            response_time=0.1,
        )

    class FakeNetwork:
        def __init__(self, hosts):
            self._hosts = hosts

        def hosts(self):
            return iter(self._hosts)

    monkeypatch.setattr(sr, "scan_host", fake_scan_host)
    monkeypatch.setattr(sr.ipaddress, "ip_network", lambda rng, strict=False: FakeNetwork(["1.2.3.4"]))
    resp = client.post("/api/scanner/scan/network", json={"ip_range": "1.2.3.4/32", "ports": [6000]})
    assert resp.status_code == 200
    assert resp.json()["found_printers"] == 1
    assert resp.json()["printers"][0]["ip"] == "1.2.3.4"


def test_scan_network_handles_error(monkeypatch):
    monkeypatch.setattr(sr.ipaddress, "ip_network", lambda rng, strict=False: (_ for _ in ()).throw(ValueError("bad")))
    resp = client.post("/api/scanner/scan/network", json={"ip_range": "bad"})
    assert resp.status_code == 500
    assert "Scan Fehler" in resp.json()["detail"]


def test_generate_config_creates_suggestions():
    printers = [{"ip": "10.0.0.1", "type": "bambu", "hostname": "alpha"}, {"ip": "10.0.0.2", "type": "klipper"}]
    resp = client.post("/api/scanner/generate/config", json=printers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"]
    assert body["count"] == 2
    assert any(s["type"] == "bambu" for s in body["suggestions"])


def test_network_info_returns_expected_fields():
    resp = client.get("/api/scanner/network/info")
    assert resp.status_code == 200
    body = resp.json()
    assert "local_ip" in body
    assert "hostname" in body


def test_fingerprint_requires_host(monkeypatch):
    resp = client.post("/api/debug/printer/fingerprint", json={"host": ""})
    assert resp.status_code == 400
    assert "host required" in resp.json()["detail"]


def test_fingerprint_detects_types(monkeypatch):
    def fake_fingerprint(host, port, timeout):
        return {"reachable": True, "error_class": "ok", "message": "ok", "latency_ms": 5}

    monkeypatch.setattr(sr, "_fingerprint_port", fake_fingerprint)
    resp = client.post("/api/debug/printer/fingerprint", json={"host": "1.2.3.4", "port": 6000, "timeout_ms": 500})
    assert resp.status_code == 200
    assert resp.json()["detected_type"] in {"bambu", "unkown"}


def test_test_connection_reports_status(monkeypatch):
    async def fake_check_port(ip, port, timeout):
        return ip == "1.2.3.4" and port == 6000

    monkeypatch.setattr(sr, "check_port", fake_check_port)
    resp = client.get("/api/scanner/test/connection", params={"ip": "1.2.3.4", "port": 6000})
    assert resp.status_code == 200
    assert resp.json()["success"]


def test_printer_lifecycle(monkeypatch):
    payload = {
        "name": "test printer",
        "printer_type": "bambu",
        "ip_address": "10.0.0.10",
        "cloud_serial": "serial",
        "api_key": "apikey",
    }
    create_resp = client.post("/api/printers/", json=payload)
    assert create_resp.status_code == 200
    printer = create_resp.json()
    assert printer["status"] == "created"

    cred_resp = client.get(f"/api/printers/{printer['id']}/credentials")
    assert cred_resp.status_code == 200
    assert cred_resp.json()["name"] == "test printer"

    update_resp = client.put(f"/api/printers/{printer['id']}", json={**payload, "name": "updated"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "updated"

    delete_resp = client.delete(f"/api/printers/{printer['id']}")
    assert delete_resp.status_code == 200


def test_printer_connection_manual_type():
    payload = {
        "name": "manual",
        "printer_type": "manual",
        "ip_address": "127.0.0.1",
    }
    resp = client.post("/api/printers/", json=payload)
    assert resp.status_code == 200
    printer = resp.json()
    conn_resp = client.post(f"/api/printers/{printer['id']}/test")
    assert conn_resp.status_code == 200
    assert conn_resp.json()["status"] == "info"


def _make_bambu_payload():
    serial = uuid.uuid4().hex[:8]
    octets = [
        str((int(serial[i : i + 2], 16) % 254) + 1) for i in range(0, 6, 2)
    ]
    ip_address = f"10.{octets[0]}.{octets[1]}.{octets[2]}"
    return {
        "name": f"bambu-{serial}",
        "printer_type": "bambu",
        "ip_address": ip_address,
        "cloud_serial": serial,
        "api_key": f"key-{serial}",
    }


def test_get_printer_not_found():
    resp = client.get("/api/printers/nonexistent-uuid")
    assert resp.status_code == 404


def test_create_printer_duplicate_returns_exists():
    payload = _make_bambu_payload()
    first_resp = client.post("/api/printers/", json=payload)
    assert first_resp.status_code == 200
    assert first_resp.json()["status"] == "created"
    printer_id = first_resp.json()["id"]

    duplicate_resp = client.post("/api/printers/", json=payload.copy())
    assert duplicate_resp.status_code == 200
    assert duplicate_resp.json()["status"] == "exists"
    assert duplicate_resp.json()["id"] == printer_id

    delete_resp = client.delete(f"/api/printers/{printer_id}")
    assert delete_resp.status_code == 200
