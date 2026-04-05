"""
Cloud MQTT Client for Bambu Lab
================================
Verbindet sich mit dem Bambu Lab Cloud MQTT Broker statt direkt zum Drucker.
Ermöglicht Drucker-Überwachung ohne LAN-Zugang.

Basiert auf: https://github.com/coelacant1/Bambu-Lab-Cloud-API

Cloud MQTT Broker:
  - EU: eu.mqtt.bambulab.com:8883
  - US: us.mqtt.bambulab.com:8883
  - CN: cn.mqtt.bambulab.com:8883

Auth:
  - Username: u_{user_id}
  - Password: access_token
"""

import json
import ssl
import logging
import threading
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.services.universal_mapper import UniversalMapper
from services.printer_service import PrinterService

logger = logging.getLogger("cloud_mqtt")


# Cloud MQTT Broker Endpoints
CLOUD_MQTT_BROKERS = {
    "eu": "eu.mqtt.bambulab.com",
    "us": "us.mqtt.bambulab.com",
    "cn": "cn.mqtt.bambulab.com",
}

CLOUD_MQTT_PORT = 8883


class CloudMQTTClient:
    """
    MQTT Client der sich mit dem Bambu Lab Cloud Broker verbindet.

    Vorteile gegenüber lokalem MQTT:
    - Funktioniert ohne LAN-Zugang zum Drucker
    - Nutzt Cloud-Authentifizierung (Token)
    - Kann mehrere Drucker gleichzeitig überwachen

    Usage:
        client = CloudMQTTClient(
            user_id="123456789",
            access_token="eyJ...",
            region="eu",
            printer_service=printer_service,
        )
        client.add_device("01P00A000000001")  # Seriennummer
        client.connect()
    """

    def __init__(
        self,
        user_id: str,
        access_token: str,
        region: str = "eu",
        printer_service: Optional[PrinterService] = None,
        on_message_callback: Optional[Callable[[str, Dict], None]] = None,
        debug: bool = False,
    ):
        self.user_id = user_id
        self.access_token = access_token
        self.region = region.lower()
        self.printer_service = printer_service
        self.on_message_callback = on_message_callback
        self.debug = debug

        # Broker URL
        self.broker_host = CLOUD_MQTT_BROKERS.get(self.region, CLOUD_MQTT_BROKERS["eu"])

        # Username muss mit u_ prefixed sein
        self.username = f"u_{user_id}" if not user_id.startswith("u_") else user_id

        # Geräte die überwacht werden
        self._devices: Dict[str, Dict[str, Any]] = {}  # serial -> info
        self._mappers: Dict[str, UniversalMapper] = {}  # serial -> mapper

        # Connection State
        self.connected = False
        self._client: Optional[mqtt.Client] = None
        self._lock = threading.Lock()

        logger.info(
            f"CloudMQTTClient initialisiert: broker={self.broker_host}, "
            f"user={self.username[:10]}..."
        )

    def add_device(
        self,
        serial: str,
        model: str = "UNKNOWN",
        name: Optional[str] = None
    ) -> None:
        """
        Fügt ein Gerät zur Überwachung hinzu.

        Args:
            serial: Seriennummer des Druckers
            model: Modell (X1C, P1S, A1, etc.)
            name: Optionaler Name
        """
        with self._lock:
            self._devices[serial] = {
                "serial": serial,
                "model": model.upper() if model else "UNKNOWN",
                "name": name or serial,
                "subscribed": False,
                "last_message": None,
            }
            self._mappers[serial] = UniversalMapper(model.upper() if model else "UNKNOWN")

        logger.info(f"CloudMQTT: Device hinzugefügt: {serial} ({model})")

        # Wenn bereits verbunden, sofort subscriben
        if self.connected and self._client:
            self._subscribe_device(serial)

    def remove_device(self, serial: str) -> None:
        """Entfernt ein Gerät aus der Überwachung."""
        with self._lock:
            if serial in self._devices:
                # Unsubscribe
                if self._client and self._devices[serial].get("subscribed"):
                    try:
                        topic = f"device/{serial}/report"
                        self._client.unsubscribe(topic)
                        logger.info(f"CloudMQTT: Unsubscribed von {topic}")
                    except Exception as e:
                        logger.warning(f"CloudMQTT: Unsubscribe fehlgeschlagen: {e}")

                del self._devices[serial]
                if serial in self._mappers:
                    del self._mappers[serial]

                logger.info(f"CloudMQTT: Device entfernt: {serial}")

    def connect(self, blocking: bool = False) -> bool:
        """
        Verbindet mit dem Cloud MQTT Broker.

        Args:
            blocking: Wenn True, blockiert bis Verbindung steht oder Fehler

        Returns:
            True wenn Verbindung initiiert wurde
        """
        if self.connected:
            logger.warning("CloudMQTT: Bereits verbunden")
            return True

        try:
            # Client erstellen
            client_id = f"filamenthub-cloud-{self.user_id[-8:]}"
            self._client = mqtt.Client(
                client_id=client_id,
                protocol=mqtt.MQTTv311,
                clean_session=True,
            )

            # Auth
            self._client.username_pw_set(self.username, self.access_token)

            # TLS - Cloud Broker braucht echtes Zertifikat
            self._client.tls_set(
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
                cert_reqs=ssl.CERT_REQUIRED,
            )

            # Callbacks
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect

            # Reconnect Delay
            self._client.reconnect_delay_set(min_delay=1, max_delay=60)

            logger.info(
                f"CloudMQTT: Verbinde zu {self.broker_host}:{CLOUD_MQTT_PORT} "
                f"als {self.username[:15]}..."
            )

            # Verbinden
            self._client.connect(
                self.broker_host,
                CLOUD_MQTT_PORT,
                keepalive=60,
            )

            if blocking:
                # Blockierend warten
                self._client.loop_forever()
            else:
                # Background Thread
                self._client.loop_start()

            return True

        except Exception as e:
            logger.error(f"CloudMQTT: Verbindung fehlgeschlagen: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Trennt die Verbindung."""
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception as e:
                logger.warning(f"CloudMQTT: Disconnect Fehler: {e}")
            finally:
                self._client = None
                self.connected = False

        logger.info("CloudMQTT: Verbindung getrennt")

    def _subscribe_device(self, serial: str) -> None:
        """Subscribed zu den Topics eines Geräts."""
        if not self._client:
            return

        try:
            # Report Topic für Status-Updates
            report_topic = f"device/{serial}/report"
            self._client.subscribe(report_topic, qos=1)

            with self._lock:
                if serial in self._devices:
                    self._devices[serial]["subscribed"] = True

            logger.info(f"CloudMQTT: Subscribed zu {report_topic}")

            # Pushall Request senden um alle Daten zu bekommen
            self._send_pushall(serial)

        except Exception as e:
            logger.error(f"CloudMQTT: Subscribe fehlgeschlagen für {serial}: {e}")

    def _send_pushall(self, serial: str) -> None:
        """Sendet pushall Request um alle Daten vom Drucker zu bekommen."""
        if not self._client:
            return

        try:
            request_topic = f"device/{serial}/request"
            pushall_payload = json.dumps({
                "pushing": {
                    "sequence_id": "1",
                    "command": "pushall"
                }
            })

            self._client.publish(request_topic, pushall_payload, qos=1)
            logger.info(f"CloudMQTT: Pushall gesendet an {serial}")

        except Exception as e:
            logger.warning(f"CloudMQTT: Pushall fehlgeschlagen für {serial}: {e}")

    def _on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        """Callback bei erfolgreicher Verbindung."""
        if rc == 0:
            self.connected = True
            logger.info(f"CloudMQTT: Verbunden mit {self.broker_host}")

            # Alle Geräte subscriben
            with self._lock:
                for serial in self._devices:
                    self._subscribe_device(serial)
        else:
            self.connected = False
            error_msgs = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized",
            }
            error_msg = error_msgs.get(rc, f"Unknown error {rc}")
            logger.error(f"CloudMQTT: Verbindung fehlgeschlagen: {error_msg}")

    def _on_disconnect(self, client, userdata, rc) -> None:
        """Callback bei Verbindungstrennung."""
        self.connected = False

        if rc == 0:
            logger.info("CloudMQTT: Sauber getrennt")
        else:
            logger.warning(f"CloudMQTT: Unerwartet getrennt (rc={rc}), versuche Reconnect...")
            # Paho handled auto-reconnect wenn loop_start verwendet wird

    def _on_message(self, client, userdata, msg) -> None:
        """Callback für eingehende MQTT Nachrichten."""
        topic = msg.topic

        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.warning(f"CloudMQTT: JSON Fehler: {e}")
            return
        except Exception as e:
            logger.warning(f"CloudMQTT: Payload Fehler: {e}")
            return

        # Serial aus Topic extrahieren
        # Format: device/<serial>/report
        parts = topic.split("/")
        if len(parts) < 2 or parts[0] != "device":
            logger.warning(f"CloudMQTT: Unbekanntes Topic Format: {topic}")
            return

        serial = parts[1]

        if self.debug:
            logger.debug(f"CloudMQTT: Message von {serial}, {len(msg.payload)} bytes")

        # Timestamp aktualisieren
        now = datetime.now(timezone.utc)
        with self._lock:
            if serial in self._devices:
                self._devices[serial]["last_message"] = now.isoformat()

        # Durch Mapper jagen
        mapper = self._mappers.get(serial)
        if mapper:
            try:
                mapped_data = mapper.map(payload)

                # Modell aktualisieren falls erkannt
                if mapped_data.model:
                    with self._lock:
                        if serial in self._devices:
                            old_model = self._devices[serial].get("model")
                            if old_model != mapped_data.model:
                                self._devices[serial]["model"] = mapped_data.model
                                self._mappers[serial] = UniversalMapper(mapped_data.model)
                                logger.info(f"CloudMQTT: Modell aktualisiert: {serial} -> {mapped_data.model}")

                # An PrinterService weiterleiten
                if self.printer_service:
                    try:
                        self.printer_service.set_connected(serial, True, now.isoformat())
                        self.printer_service.mark_seen(serial, now.isoformat())
                        self.printer_service.update_printer(serial, mapped_data)
                    except Exception as e:
                        logger.error(f"CloudMQTT: PrinterService Update fehlgeschlagen: {e}")

                # Job Tracking Service aufrufen (für task_id, subtask_name, etc.)
                try:
                    from app.services.job_tracking_service import job_tracking_service
                    from app.database import engine
                    from sqlmodel import Session, select
                    from app.models.printer import Printer

                    # Printer ID ermitteln
                    printer_id = None
                    with Session(engine) as session:
                        printer = session.exec(
                            select(Printer).where(Printer.cloud_serial == serial)
                        ).first()
                        if printer:
                            printer_id = printer.id

                    if printer_id:
                        # AMS-Daten aus mapped_data extrahieren
                        ams_data = None
                        if mapped_data.ams_units:
                            ams_data = [dict(unit) if hasattr(unit, '__iter__') else unit for unit in mapped_data.ams_units]

                        # Job Tracking verarbeiten mit Raw Payload
                        result = job_tracking_service.process_message(
                            cloud_serial=serial,
                            parsed_payload=payload,  # Raw Payload mit task_id, subtask_name
                            printer_id=printer_id,
                            ams_data=ams_data
                        )
                        if result and result.get("action") not in [None, "none", "no_action"]:
                            logger.info(f"CloudMQTT: JobTracking action={result.get('action')} für {serial}")
                    else:
                        logger.debug(f"CloudMQTT: Kein Drucker mit cloud_serial={serial} gefunden")

                except Exception as e:
                    logger.error(f"CloudMQTT: JobTracking fehlgeschlagen für {serial}: {e}")

            except Exception as e:
                logger.error(f"CloudMQTT: Mapping fehlgeschlagen für {serial}: {e}")

        # Custom Callback
        if self.on_message_callback:
            try:
                self.on_message_callback(serial, payload)
            except Exception as e:
                logger.error(f"CloudMQTT: Callback Fehler: {e}")

    def send_command(self, serial: str, command: Dict[str, Any]) -> bool:
        """
        Sendet einen Befehl an einen Drucker.

        Args:
            serial: Seriennummer
            command: Command Dictionary

        Returns:
            True wenn gesendet
        """
        if not self._client or not self.connected:
            logger.warning("CloudMQTT: Nicht verbunden, kann Befehl nicht senden")
            return False

        try:
            request_topic = f"device/{serial}/request"
            payload = json.dumps(command)

            result = self._client.publish(request_topic, payload, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"CloudMQTT: Befehl gesendet an {serial}")
                return True
            else:
                logger.warning(f"CloudMQTT: Befehl senden fehlgeschlagen: rc={result.rc}")
                return False

        except Exception as e:
            logger.error(f"CloudMQTT: Befehl senden Fehler: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Gibt den aktuellen Status zurück."""
        with self._lock:
            devices_status = {}
            for serial, info in self._devices.items():
                devices_status[serial] = {
                    "model": info.get("model"),
                    "name": info.get("name"),
                    "subscribed": info.get("subscribed", False),
                    "last_message": info.get("last_message"),
                }

        return {
            "connected": self.connected,
            "broker": self.broker_host,
            "region": self.region,
            "user_id": self.user_id[:8] + "...",
            "devices_count": len(self._devices),
            "devices": devices_status,
        }


# ============================================================
# GLOBAL INSTANCE MANAGEMENT
# ============================================================

_cloud_mqtt_instance: Optional[CloudMQTTClient] = None
_cloud_mqtt_lock = threading.Lock()


def get_cloud_mqtt_client() -> Optional[CloudMQTTClient]:
    """Gibt die globale Cloud MQTT Instanz zurück."""
    return _cloud_mqtt_instance


def init_cloud_mqtt(
    user_id: str,
    access_token: str,
    region: str = "eu",
    printer_service: Optional[PrinterService] = None,
    devices: Optional[List[Dict[str, str]]] = None,
) -> CloudMQTTClient:
    """
    Initialisiert den globalen Cloud MQTT Client.

    Args:
        user_id: Bambu Cloud User ID
        access_token: Bambu Cloud Access Token
        region: Region (eu, us, cn)
        printer_service: Optional PrinterService für Updates
        devices: Liste von Geräten [{serial, model, name}, ...]

    Returns:
        CloudMQTTClient Instanz
    """
    global _cloud_mqtt_instance

    with _cloud_mqtt_lock:
        # Alten Client trennen
        if _cloud_mqtt_instance:
            try:
                _cloud_mqtt_instance.disconnect()
            except Exception:
                pass

        # Neuen Client erstellen
        _cloud_mqtt_instance = CloudMQTTClient(
            user_id=user_id,
            access_token=access_token,
            region=region,
            printer_service=printer_service,
        )

        # Geräte hinzufügen
        if devices:
            for device in devices:
                _cloud_mqtt_instance.add_device(
                    serial=device.get("serial", ""),
                    model=device.get("model", "UNKNOWN"),
                    name=device.get("name"),
                )

        # Verbinden
        _cloud_mqtt_instance.connect(blocking=False)

        return _cloud_mqtt_instance


def stop_cloud_mqtt() -> None:
    """Stoppt den globalen Cloud MQTT Client."""
    global _cloud_mqtt_instance

    with _cloud_mqtt_lock:
        if _cloud_mqtt_instance:
            try:
                _cloud_mqtt_instance.disconnect()
            except Exception as e:
                logger.warning(f"CloudMQTT Stop Fehler: {e}")
            finally:
                _cloud_mqtt_instance = None

    logger.info("CloudMQTT: Global Instance gestoppt")
