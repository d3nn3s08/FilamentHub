import json
import ssl
from typing import Optional
from datetime import datetime

import paho.mqtt.client as mqtt

from app.services.universal_mapper import UniversalMapper
from services.printer_service import PrinterService


class PrinterMQTTClient:
    """MQTT Client der immer PrinterData über den UniversalMapper liefert."""

    def __init__(
        self,
        ip: str,
        model: str,
        name: str,
        mqtt_version: str,
        printer_service: PrinterService,
        username: str = "bblp",
        password: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        self.ip = ip
        self.model = model
        self.name = name
        self.username = username or "bblp"
        self.password = password
        self.printer_service = printer_service
        self.debug = debug

        # Track connected state for runtime checks
        self.connected: bool = False

        self.mapper = UniversalMapper(model)

        protocol = {
            "5": mqtt.MQTTv5,
            "311": mqtt.MQTTv311,
            "31": mqtt.MQTTv31,
        }.get(str(mqtt_version), mqtt.MQTTv311)

        self.client = mqtt.Client(client_id=name, protocol=protocol)

        if password is not None:
            self.client.username_pw_set(self.username, password)

        self.client.tls_set(cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def set_model(self, model: str) -> None:
        """Bei Modelwechsel Mapper neu setzen."""
        new_model = (model or "").upper()
        if new_model and new_model != self.model:
            self.model = new_model
            self.mapper = UniversalMapper(new_model)
            if self.debug:
                print(f"[MQTT] Mapper aktualisiert auf Modell {new_model}")

    def connect(self) -> None:
        """Mit TLS (Port 8883) verbinden und Listening starten."""
        if self.debug:
            print(f"[MQTT] Verbinde {self.name} ({self.ip}) als {self.username} (TLS, insecure)")
        self.client.connect(self.ip, 8883, 60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        # MQTT v5 on_connect signature: (client, userdata, flags, reason_code, properties)
        serial = None
        try:
            if isinstance(userdata, dict):
                serial = userdata.get("cloud_serial")
        except Exception:
            serial = None

        print(f"[MQTT] CONNECT rc={reason_code} cloud_serial={serial}")

        # reason_code == 0 indicates success
        try:
            if reason_code == 0:
                self.connected = True
            else:
                self.connected = False
        except Exception:
            self.connected = False

        if self.connected:
            if serial:
                try:
                    topic = f"device/{serial}/report"
                    self.client.subscribe(topic)
                    print(f"[MQTT] SUBSCRIBED {topic}")
                except Exception as e:
                    print(f"[MQTT] SUBSCRIBE FAILED cloud_serial={serial} error={e}")
            else:
                print(f"[MQTT] CONNECTED but no cloud_serial; not subscribing")
        else:
            print(f"[MQTT] CONNECT FAILED rc={reason_code} cloud_serial={serial}")

    def _on_disconnect(self, client, userdata, rc) -> None:
        # Always log disconnects for debugging
        print(f"[MQTT] DISCONNECT rc={rc}")
        try:
            client.reconnect()
        except Exception as e:
            print(f"[MQTT] Reconnect fehlgeschlagen: {e}")

    def _on_message(self, client, userdata, msg) -> None:
        topic = getattr(msg, "topic", "")
        payload_bytes = getattr(msg, "payload", b"")
        try:
            raw = json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            print(f"[MQTT] JSON Fehler topic={topic} error={e}")
            return

        # extract cloud_serial from topic device/<serial>/...
        serial = None
        try:
            parts = (topic or "").split("/")
            if len(parts) > 1 and parts[0] == "device":
                serial = parts[1]
        except Exception:
            serial = None

        print(f"[MQTT] MESSAGE topic={topic} cloud_serial={serial} size={len(payload_bytes)}")

        # Mark as connected on first receipt
        try:
            if serial:
                from datetime import datetime, timezone

                ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                try:
                    self.printer_service.set_connected(serial, True, ts)
                except Exception as e:
                    print(f"[MQTT] set_connected failed for {serial}: {e}")
        except Exception:
            pass

        try:
            mapped = self.mapper.map(raw)
            if mapped.model and mapped.model != self.model:
                self.set_model(mapped.model)
            # Use cloud_serial as logical key for printer updates
            if serial:
                self.printer_service.update_printer(serial, mapped)
            else:
                print(f"[MQTT] MESSAGE without cloud_serial; ignored")
        except Exception as e:
            print(f"[MQTT] Mapping/Update Fehler: {e}")
        # Update global runtime state so status() returns connected when reports arrive
        try:
            if serial:
                try:
                    # import at runtime to avoid circular imports
                    from app.services import mqtt_runtime

                    ts = None
                    try:
                        from datetime import datetime, timezone

                        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    except Exception:
                        ts = None

                    # mark runtime connected and update last_seen/connected_since if first
                    if ts:
                        mqtt_runtime._runtime_state["last_seen"] = ts
                        if not mqtt_runtime._runtime_state.get("connected"):
                            mqtt_runtime._runtime_state["connected"] = True
                            mqtt_runtime._runtime_state["connected_since"] = ts
                except Exception:
                    pass
        except Exception:
            pass
