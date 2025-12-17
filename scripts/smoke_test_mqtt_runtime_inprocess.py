import json
import os
import sys

# Allow `import app.*` when running from scripts/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app


def _show(resp):
    print(f"{resp.request.method} {resp.request.url.path} -> {resp.status_code}")
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text)


def main() -> int:
    client = TestClient(app)

    _show(client.get("/api/mqtt/runtime/status"))
    _show(client.post("/api/mqtt/runtime/disconnect"))
    _show(
        client.post(
            "/api/mqtt/runtime/connect",
            json={
                "broker": "127.0.0.1",
                "port": 8883,
                "client_id": "filamenthub_debug",
                "username": "bblp",
                "password": "x",
            },
        )
    )
    _show(client.get("/api/mqtt/runtime/status"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
