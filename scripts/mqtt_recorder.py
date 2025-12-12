"""
MQTT Recorder for Bambu X1C payloads.

Connects to printer MQTT, records samples, and validates mapping.
"""
import json
import ssl
from pathlib import Path
from typing import List

import paho.mqtt.client as mqtt

from app.services.universal_mapper import UniversalMapper

HOST = "192.168.178.41"
PORT = 8883
USERNAME = "bblp"
PASSWORD = "3e0685ba"
TOPIC = "device/+/report"
PROTOCOL = mqtt.MQTTv5

SAMPLES = [
    "x1c_idle.json",
    "x1c_heating.json",
    "x1c_printing.json",
    "x1c_pause.json",
    "x1c_finish.json",
]

OUTPUT_DIR = Path("tests/live_samples")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

received: List[dict] = []


def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[RECORDER] Connected rc={rc}")
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        received.append(payload)
        print(f"[RECORDER] Received sample #{len(received)} from {msg.topic}")
        if len(received) >= len(SAMPLES):
            client.disconnect()
    except Exception as e:
        print(f"[RECORDER] Parse error: {e}")


def record_samples():
    client = mqtt.Client(protocol=PROTOCOL)
    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(HOST, PORT, 60)
    client.loop_forever()


def validate_samples():
    mapper = UniversalMapper("X1C")
    for idx, payload in enumerate(received):
        pd = mapper.map(payload)
        print(f"[VALIDATE] Sample #{idx+1}: state={pd.state}, progress={pd.progress}")
        assert pd.state is not None
        assert isinstance(pd.progress, (float, type(None)))
        assert isinstance(pd.temperature.get("nozzle"), (float, type(None)))
        assert isinstance(pd.temperature.get("bed"), (float, type(None)))
        assert isinstance(pd.temperature.get("chamber"), (float, type(None)))
        assert isinstance(pd.layer.get("current"), (int, type(None)))
        assert isinstance(pd.layer.get("total"), (int, type(None)))
        assert isinstance(pd.job.get("file"), (str, type(None)))


def save_samples():
    for name, payload in zip(SAMPLES, received):
        (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[RECORDER] Saved {name}")


if __name__ == "__main__":
    record_samples()
    save_samples()
    validate_samples()
