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
        # Falls bereits gesetzt
        if getattr(printer, "mqtt_version", None):
            return printer.mqtt_version
        try:
            res = protocol_detector.detect(printer.ip_address, printer.api_key, port=printer.port or 8883)
            if isinstance(res, dict) and res.get("detected"):
                return str(res.get("protocol"))
        except Exception:
            return None
        return None
