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

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if self.debug:
            print(f"[MQTT] Connected rc={rc}")
        self.client.subscribe("device/+/report")

    def _on_disconnect(self, client, userdata, rc) -> None:
        if self.debug:
            print(f"[MQTT] Disconnected rc={rc}, versuche Reconnect...")
        try:
            client.reconnect()
        except Exception as e:
            if self.debug:
                print(f"[MQTT] Reconnect fehlgeschlagen: {e}")

    def _on_message(self, client, userdata, msg) -> None:
        try:
            raw = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            if self.debug:
                print(f"[MQTT] JSON Fehler: {e}")
            return

        try:
            mapped = self.mapper.map(raw)
            self.printer_service.update_printer(self.name, mapped)
        except Exception as e:
            if self.debug:
                print(f"[MQTT] Mapping/Update Fehler: {e}")
