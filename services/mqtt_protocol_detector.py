import ssl
import json
import threading
from typing import Dict, Optional

import paho.mqtt.client as mqtt


class MQTTProtocolDetector:
    """Erkennt MQTT-Protokoll (v5/311/31) für Bambu Lab Drucker mit TLS+Auth."""

    def __init__(self, timeout: int = 3) -> None:
        self.timeout = timeout

    def detect(self, ip: str, api_key: str, port: int = 8883) -> Dict[str, object]:
        protocols = [("5", mqtt.MQTTv5), ("311", mqtt.MQTTv311), ("31", mqtt.MQTTv31)]
        last_error: Optional[str] = None

        for label, proto in protocols:
            event = threading.Event()
            result: Dict[str, object] = {
                "detected": False,
                "protocol": label,
                "tls": True,
                "auth": True,
                "supports_properties": False,
                "error": None,
            }
            payload_holder = {}

            def on_connect(client, userdata, flags, rc, properties=None):
                if rc == 0:
                    try:
                        client.subscribe("device/+/report")
                    except Exception as e:
                        result["error"] = f"subscribe failed: {e}"
                        client.disconnect()
                else:
                    result["error"] = f"rc={rc}"
                    client.disconnect()

            def on_message(client, userdata, msg):
                try:
                    payload_holder["msg"] = msg
                    payload_holder["json"] = json.loads(msg.payload.decode("utf-8", errors="ignore"))
                except Exception:
                    payload_holder["json"] = None
                event.set()
                client.disconnect()

            client = mqtt.Client(protocol=proto)
            try:
                client.username_pw_set("bblp", api_key)
                client.tls_set(cert_reqs=ssl.CERT_NONE)
                client.tls_insecure_set(True)
                client.on_connect = on_connect
                client.on_message = on_message
                client.connect(ip, port, keepalive=30)
                client.loop_start()
                event.wait(timeout=self.timeout)
                client.loop_stop()
                client.disconnect()
                if event.is_set() and "msg" in payload_holder:
                    result["detected"] = True
                    result["supports_properties"] = (proto == mqtt.MQTTv5)
                    result["raw_topic"] = payload_holder.get("msg").topic
                    result["raw_payload"] = payload_holder.get("msg").payload.decode("utf-8", errors="ignore")
                    return result
                else:
                    last_error = result.get("error") or "timeout"
            except Exception as e:
                last_error = str(e)
                try:
                    client.loop_stop()
                except Exception:
                    pass
                try:
                    client.disconnect()
                except Exception:
                    pass
                continue

        return {"detected": False, "error": last_error or "no protocol matched"}
