import json
from typing import Optional, Any, Dict, List

from app.services.ams_parser import parse_ams
from app.services.job_parser import parse_job
from app.services.universal_mapper import UniversalMapper
from app.services.printer_auto_detector import PrinterAutoDetector


def process_mqtt_payload(topic: str, payload: str, printer_service_ref: Optional[Any] = None) -> Dict[str, Any]:
    """Process an MQTT payload and return parsed/derived pieces.

    This function intentionally avoids DB access, websockets, or changing
    global state. It is defensive and will never raise — errors are
    swallowed and sensible fallbacks returned.

    Returns a dict with keys: raw, ams, job, mapped, mapped_dict, serial, capabilities
    """
    result: Dict[str, Any] = {
        "raw": None,
        "ams": [],
        "job": {},
        "mapped": None,
        "mapped_dict": None,
        "serial": None,
        "capabilities": None,
    }

    try:
        # serial from topic if available (device/<serial>/...)
        try:
            parts = topic.split("/")
            if len(parts) >= 2 and parts[0] == "device":
                result["serial"] = parts[1]
        except Exception:
            result["serial"] = None

        # parse JSON
        try:
            parsed = json.loads(payload)
            result["raw"] = parsed
        except Exception:
            parsed = None
            result["raw"] = None

        # parse AMS / job only for report topics (keeps parity with callers)
        try:
            if parsed is not None and topic.endswith("/report"):
                try:
                    result["ams"] = parse_ams(parsed) or []
                except Exception:
                    result["ams"] = []
                try:
                    result["job"] = parse_job(parsed) or {}
                except Exception:
                    result["job"] = {}
        except Exception:
            # defensive catch; keep defaults
            pass

        # mapping + capability detection (no DB, no side effects)
        if parsed is not None:
            try:
                detected_model = PrinterAutoDetector.detect_model_from_payload(parsed) or PrinterAutoDetector.detect_model_from_serial(result.get("serial"))
            except Exception:
                detected_model = None
            try:
                caps = PrinterAutoDetector.detect_capabilities(parsed)
            except Exception:
                caps = None

            try:
                model_for_mapper = detected_model or "UNKNOWN"
                mapper = UniversalMapper(model_for_mapper)
                mapped_obj = mapper.map(parsed)
                result["mapped"] = mapped_obj
                try:
                    result["mapped_dict"] = mapped_obj.to_dict() if hasattr(mapped_obj, "to_dict") else None
                except Exception:
                    result["mapped_dict"] = None
            except Exception:
                result["mapped"] = None
                result["mapped_dict"] = None

            result["capabilities"] = caps

    except Exception:
        # Top-level safety — never raise
        return result

    return result
