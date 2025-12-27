from typing import Optional, Dict, Any


class PrinterAutoDetector:
    """
    Erkennt automatisch:
      - Modell (X1C, P1S, P1P, A1, A1MINI, X1E, H2D)
      - MQTT-Protokoll (5 / 311 / 31)
      - Capability-Map (AMS vorhanden? LiDAR? Chamber sensor?)
    """

    MODEL_MAP_PREFIX = {
        "00M09A": "X1C",
        "0309DA": "A1MINI",
        "0309DB": "A1",
        "01P1S": "P1S",
        "01P1P": "P1P",
        "01X1E": "X1E",
        "H2D": "H2D",
    }

    # MQTT Protokoll-Zuordnung nach Modell
    # X1C, X1E, P1P, P1S verwenden MQTT v5 für vollständige Daten
    # A1, A1 Mini verwenden MQTT v3.1.1
    MODEL_MQTT_PROTOCOL = {
        "X1C": "5",
        "X1E": "5",
        "P1S": "5",
        "P1P": "5",
        "A1": "311",
        "A1MINI": "311",
        "H2D": "311",
    }

    @staticmethod
    def detect_model_from_serial(serial: Optional[str]) -> Optional[str]:
        if not serial:
            return None
        for prefix, model in PrinterAutoDetector.MODEL_MAP_PREFIX.items():
            if serial.startswith(prefix):
                return model
        return None

    @staticmethod
    def detect_model_from_payload(data: Dict[str, Any]) -> Optional[str]:
        dev = data.get("device", {}) if isinstance(data, dict) else {}
        model = dev.get("model") or dev.get("machine", {}).get("model") if isinstance(dev, dict) else None
        if model:
            return str(model).upper()
        return None

    @staticmethod
    def detect_capabilities(data: Dict[str, Any]) -> Dict[str, bool]:
        caps = {
            "has_ams": False,
            "has_lidar": False,
            "has_chamber_temp": False,
            "has_aux_fan": False,
        }
        if isinstance(data, dict):
            if any(k in data for k in ("ams", "filament", "material_system")):
                caps["has_ams"] = True
            if "lidar" in str(data).lower():
                caps["has_lidar"] = True
            temp_block = data.get("temperature", {}) if isinstance(data.get("temperature"), dict) else {}
            if any("chamber" in str(v).lower() for v in temp_block.values()) or "chamber" in temp_block:
                caps["has_chamber_temp"] = True
            cooling = data.get("cooling") if isinstance(data.get("cooling"), dict) else {}
            if cooling.get("fan_2_speed") is not None:
                caps["has_aux_fan"] = True
        return caps

    @staticmethod
    def detect_mqtt_version(protocol_detector, printer) -> Optional[str]:
        """
        Erkennt MQTT-Protokoll mit Modell-basierter Priorisierung.

        1. Wenn mqtt_version bereits gesetzt: verwende diese
        2. Wenn Modell bekannt: verwende modell-spezifisches Protokoll (harte Regel)
        3. Fallback: Auto-Detection über protocol_detector
        """
        # Falls bereits gesetzt
        if getattr(printer, "mqtt_version", None):
            return printer.mqtt_version

        # Modell-basierte Zuordnung (höchste Priorität)
        model = getattr(printer, "model", None)
        if model and model.upper() in PrinterAutoDetector.MODEL_MQTT_PROTOCOL:
            protocol = PrinterAutoDetector.MODEL_MQTT_PROTOCOL[model.upper()]
            print(f"[MQTT] Modell '{model}' → Protokoll {protocol} (harte Regel)")
            return protocol

        # Fallback: Auto-Detection
        try:
            res = protocol_detector.detect(printer.ip_address, printer.api_key, port=printer.port or 8883)
            if isinstance(res, dict) and res.get("detected"):
                detected_protocol = str(res.get("protocol"))
                print(f"[MQTT] Auto-Detection → Protokoll {detected_protocol}")
                return detected_protocol
        except Exception as e:
            print(f"[MQTT] Auto-Detection fehlgeschlagen: {e}")
            return None
        return None
