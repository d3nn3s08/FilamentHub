import ssl
import json
import paho.mqtt.client as mqtt
from legacy_printer_mapper import UniversalMapper


class PrinterMQTTClient:

    def __init__(self, ip, model, name, mqtt_version, printer_service):
        self.ip = ip
        self.model = model
        self.name = name
        self.printer_service = printer_service

        self.mapper = UniversalMapper(model)

        protocol = {
            "5": mqtt.MQTTv5,
            "311": mqtt.MQTTv311,
            "31": mqtt.MQTTv31
        }.get(str(mqtt_version), mqtt.MQTTv311)

        self.client = mqtt.Client(client_id=name, protocol=protocol)

        self.client.tls_set(cert_reqs=ssl.CERT_NONE)
        self.client.tls_insecure_set(True)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def connect(self):
        print(f"[MQTT] Verbinde zu {self.name} ({self.ip})")
        self.client.connect(self.ip, 8883, 60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] {self.name} verbunden (RC={rc})")
        self.client.subscribe("device/+/report")

    def _on_message(self, client, userdata, msg):
        try:
            raw = json.loads(msg.payload.decode("utf-8"))
        except:
            print("[MQTT] JSON Fehler")
            return

        mapped = self.mapper.map(raw)
        self.printer_service.update_printer(self.name, mapped)
