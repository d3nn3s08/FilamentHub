import json
import logging
from typing import Optional, Any, Dict, List

from app.services.ams_parser import parse_ams
from app.services.job_parser import parse_job
from app.services.universal_mapper import UniversalMapper
from app.services.printer_auto_detector import PrinterAutoDetector

logger = logging.getLogger("mqtt")

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
            logger.exception("Failed to parse device serial from topic=%s; continuing without serial", topic)
            result["serial"] = None

        # parse JSON
        try:
            parsed = json.loads(payload)
            result["raw"] = parsed
        except Exception:
            logger.exception("Failed to decode MQTT payload JSON for topic=%s; using defaults", topic)
            parsed = None
            result["raw"] = None

        # parse AMS / job only for report topics (keeps parity with callers)
        try:
            if parsed is not None and topic.endswith("/report"):
                try:
                    result["ams"] = parse_ams(parsed) or []
                except Exception:
                    logger.exception("Failed to parse AMS data for topic=%s; using empty AMS list", topic)
                    result["ams"] = []
                try:
                    result["job"] = parse_job(parsed) or {}
                except Exception:
                    logger.exception("Failed to parse job data for topic=%s; using empty job payload", topic)
                    result["job"] = {}
        except Exception:
            # defensive catch; keep defaults
            logger.exception("Failed to evaluate report payload for topic=%s; using defaults", topic)

        # mapping + capability detection (no DB, no side effects)
        if parsed is not None:
            try:
                detected_model = PrinterAutoDetector.detect_model_from_payload(parsed) or PrinterAutoDetector.detect_model_from_serial(result.get("serial"))
            except Exception:
                logger.exception("Failed to detect printer model from payload for topic=%s; using fallback model", topic)
                detected_model = None
            try:
                caps = PrinterAutoDetector.detect_capabilities(parsed)
            except Exception:
                logger.exception("Failed to detect capabilities for topic=%s; continuing without caps", topic)
                caps = None

            try:
                model_for_mapper = detected_model or "UNKNOWN"
                mapper = UniversalMapper(model_for_mapper)
                mapped_obj = mapper.map(parsed)
                result["mapped"] = mapped_obj
                try:
                    result["mapped_dict"] = mapped_obj.to_dict() if hasattr(mapped_obj, "to_dict") else None
                except Exception:
                    logger.exception("Failed to convert mapped object to dict for topic=%s; continuing", topic)
                    result["mapped_dict"] = None
            except Exception:
                logger.exception("Failed to map MQTT payload for topic=%s; continuing with defaults", topic)
                result["mapped"] = None
                result["mapped_dict"] = None

            result["capabilities"] = caps

    except Exception:
        # Top-level safety — never raise
        logger.exception("Unhandled error while processing MQTT payload for topic=%s; using defaults", topic)
        return result

    return result
