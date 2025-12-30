import logging
from typing import Any, Dict, List, Optional

from app.services.ams_parser import AMSUnit, Tray, parse_ams

logger = logging.getLogger(__name__)


def _safe_get(d: Optional[Dict[str, Any]], k: str, default: Any = None) -> Any:
    if not isinstance(d, dict):
        return default
    return d.get(k, default)


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _rssi_to_percent(value: Any) -> Optional[str]:
    """Convert RSSI strings like '-42dBm' or numeric values to a human-friendly percent string.

    Returns e.g. '83%' or None if parsing failed.
    Mapping uses range -100..-30 dBm -> 0..100%.
    """
    if value is None:
        return None
    try:
        # Accept formats like '-42dBm' or '-42'
        s = str(value).strip()
        # strip trailing 'dBm' or similar
        if s.lower().endswith('dbm'):
            s = s[:-3]
        # remove any non-digit/sign characters
        import re
        m = re.search(r"-?\d+", s)
        if not m:
            return None
        rssi = int(m.group(0))
        # clamp
        rssi = max(-100, min(-30, rssi))
        percent = int(round((rssi + 100) / 70.0 * 100))
        return f"{percent}%"
    except Exception:
        return None


def _normalize_tray(tray: Tray) -> Dict[str, Optional[Any]]:
    # Normalize numeric fields where possible and keep names consistent for frontend
    slot = None
    if isinstance(tray, dict):
        raw_slot = None
        if "tray_id" in tray and tray.get("tray_id") is not None:
            raw_slot = tray.get("tray_id")
        elif "id" in tray and tray.get("id") is not None:
            raw_slot = tray.get("id")
        slot = _to_int(raw_slot)

    remain = None
    if isinstance(tray, dict):
        # parser already tries multiple keys; here defensively parse common ones
        remain = _to_float(tray.get("remain") or tray.get("remain_percent") or tray.get("remain_weight"))

    total_len = None
    if isinstance(tray, dict):
        total_len = _to_int(tray.get("total_len"))

    nozzle_min = None
    nozzle_max = None
    if isinstance(tray, dict):
        nozzle_min = _to_float(tray.get("nozzle_temp_min") or tray.get("nozzle_min") or tray.get("nozzle_temp_min"))
        nozzle_max = _to_float(tray.get("nozzle_temp_max") or tray.get("nozzle_max") or tray.get("nozzle_temp_max"))

    return {
        "slot": slot,
        "tray_uuid": tray.get("tray_uuid") if isinstance(tray, dict) else None,
        "tag_uid": tray.get("tag_uid") if isinstance(tray, dict) else None,
        "remain_weight": None,
        "remain_percent": remain,
        "total_len": total_len,
        "nozzle_temp_min": nozzle_min,
        "nozzle_temp_max": nozzle_max,
    }


def _normalize_ams_unit(ams_unit: AMSUnit) -> Dict[str, Any]:
    return {
        "ams_id": ams_unit.get("ams_id"),
        "temp": ams_unit.get("temp"),
        "humidity": ams_unit.get("humidity"),
        "active_tray": ams_unit.get("active_tray"),
        "trays": [_normalize_tray(t) for t in (ams_unit.get("trays") or [])],
    }


def normalize_device(device_entry: Dict[str, Any]) -> Dict[str, Any]:
    device_serial = _safe_get(device_entry, "device")
    ts = _safe_get(device_entry, "ts")
    payload = _safe_get(device_entry, "payload", {}) or {}

    try:
        ams_units = parse_ams(payload) or []
    except Exception:
        logger.exception("parse_ams failed for device %s", device_serial)
        ams_units = []

    normalized_ams = []
    for u in ams_units:
        try:
            normalized_ams.append(_normalize_ams_unit(u))
        except Exception:
            logger.exception("Failed to normalize AMS unit for device %s: %s", device_serial, u)

    return {
        "device_serial": device_serial,
        "ts": ts,
        "online": bool(payload),
        # Firmware/version info (best-effort)
            "firmware": (
                (payload.get("upgrade_state") or {}).get("ota_new_version_number")
                or payload.get("ver")
                or payload.get("version")
                or payload.get("fw")
                or payload.get("fw_version")
                or _safe_get(payload, "device", {}).get("ver") if isinstance(_safe_get(payload, "device", {}), dict) else None
                or _safe_get(payload, "device", {}).get("online", {}).get("version") if isinstance(_safe_get(payload, "device", {}), dict) else None
            ),
            # Signal quality (wifi RSSI, etc.) — present as dBm or numeric string in various keys
            "signal": _rssi_to_percent(
                payload.get("wifi_signal")
                or payload.get("signal")
                or _safe_get(payload, "device", {}).get("wifi_signal") if isinstance(_safe_get(payload, "device", {}), dict) else None
            ),
        "ams_units": normalized_ams,
    }


def normalize_live_state(live_state: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    devices: List[Dict[str, Any]] = []
    for device_id, entry in (live_state or {}).items():
        try:
            devices.append(normalize_device(entry))
        except Exception:
            logger.exception("Failed to normalize device %s", device_id)
            devices.append({
                "device_serial": device_id,
                "ts": entry.get("ts") if isinstance(entry, dict) else None,
                "online": False,
                "ams_units": [],
            })
    return {"devices": devices}


def has_real_ams_from_payload(payload: Any) -> bool:
    """Bestimme, ob ein Gerät ein echtes AMS hat, nur anhand des Payloads.

    Regeln (vereinfachte Form):
    - Wenn das geparste Ergebnis aus `parse_ams` mindestens eine Einheit enthält -> True
    - Wenn payload.get("ams_exist_bits_raw") == "1" -> True
    - Wenn payload.get("ams") ein dict ist und humidity_raw vorhanden ist -> True
    """
    if not isinstance(payload, dict):
        return False
    try:
        parsed = parse_ams(payload) or []
        if isinstance(parsed, (list, tuple)) and len(parsed) > 0:
            return True
    except Exception:
        # Falls Parser versagt, weiter mit rohchecks
        logger.debug("parse_ams failed in has_real_ams_from_payload, falling back to raw checks")

    if payload.get("ams_exist_bits_raw") == "1":
        return True
    ams_obj = payload.get("ams")
    if isinstance(ams_obj, dict) and ams_obj.get("humidity_raw") is not None:
        return True
    return False


def device_has_real_ams_from_live_state(device_id: str) -> bool:
    from app.services import live_state as live_state_module

    state = live_state_module.get_live_state(device_id)
    if not state:
        return False
    payload = state.get("payload") or {}
    return has_real_ams_from_payload(payload)


def global_has_real_ams() -> bool:
    from app.services import live_state as live_state_module

    all_state = live_state_module.get_all_live_state()
    for _, entry in (all_state or {}).items():
        if has_real_ams_from_payload(entry.get("payload") or {}):
            return True
    return False
