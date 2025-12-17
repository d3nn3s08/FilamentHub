import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request


def _call(method: str, base: str, path: str, body=None, timeout: float = 3.0) -> int:
    url = base.rstrip("/") + path

    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                raw_out = json.dumps(parsed, ensure_ascii=False, indent=2)
            except Exception:
                raw_out = raw

            print(f"{method} {path} -> {resp.status}")
            print(raw_out)
            return 0
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        print(f"{method} {path} -> HTTPError {e.code}")
        print(raw)
        return 2
    except Exception as e:
        print(f"{method} {path} -> ERROR: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8085")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--username", default="bblp")
    parser.add_argument("--password", default=None)
    parser.add_argument("--client-id", default="fh_debug")
    parser.add_argument("--tls", action="store_true", default=True)
    parser.add_argument("--keepalive", type=int, default=60)
    args = parser.parse_args()

    password = args.password
    if password is None:
        password = os.environ.get("FILAMENTHUB_MQTT_PASSWORD")
    if password is None:
        password = getpass.getpass("Bambu ACCESS_CODE (wird nicht angezeigt): ")

    connect_body = {
        "broker": args.host,
        "port": args.port,
        "client_id": args.client_id,
        "username": args.username,
        "password": password,
    }

    rc = 0
    rc |= _call("GET", args.base, "/api/mqtt/runtime/status", timeout=args.timeout)
    rc |= _call("POST", args.base, "/api/mqtt/runtime/disconnect", timeout=args.timeout)
    rc |= _call("POST", args.base, "/api/mqtt/runtime/connect", body=connect_body, timeout=args.timeout)
    rc |= _call("GET", args.base, "/api/mqtt/runtime/status", timeout=args.timeout)
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
