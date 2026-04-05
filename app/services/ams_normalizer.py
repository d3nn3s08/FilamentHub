import logging
from typing import Any, Dict, List, Optional, Mapping

from app.services.ams_parser import AMSUnit, Tray, parse_ams, is_ams_lite_firmware, parse_vt_tray

logger = logging.getLogger("services")


def _safe_get(d: Optional[Dict[str, Any]], k: str, default: Any = None) -> Any:
    if not isinstance(d, dict):
        return default
    return d.get(k, default)


def _extract_printer_model_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Extract printer model from MQTT payload if not available from DB.
    
    Tries multiple locations where model info might be stored:
    - device.hw.model
    - machine_type
    - model_id
    - etc.
    """
    if not isinstance(payload, dict):
        return None
    
    # Try common MQTT payload locations
    if isinstance(payload.get("device"), dict):
        device_info = payload["device"]
        model = device_info.get("hw", {}).get("model") if isinstance(device_info.get("hw"), dict) else None
        if model:
            return str(model).upper()
    
    # Try machine_type
    machine_type = payload.get("machine_type")
    if machine_type:
        return str(machine_type).upper()
    
    # Try model field directly
    model = payload.get("model")
    if model:
        return str(model).upper()
    
    return None


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


def calc_remaining_grams(tray: Mapping[str, Any]) -> Optional[float]:
    """
    Calculate remaining filament weight in grams from AMS tray data.

    Priority:
    1. Direct remain_weight from AMS
    2. Calculate from total_len (RFID) × remain_percent
    3. Fallback to tray_weight × remain_percent (less accurate)
    """
    # 1) Direkter AMS-Wert (wenn vorhanden, am genauesten)
    remain_weight = tray.get("remain_weight")
    if remain_weight is not None:
        try:
            return float(remain_weight)
        except (TypeError, ValueError):
            pass

    # 2) Berechnung aus total_len (RFID-Länge) und remain_percent
    # Dies ist genauer als tray_weight, da total_len spulenspezifisch ist
    total_len = tray.get("total_len")
    remain_percent = tray.get("remain")
    if total_len is not None and remain_percent is not None:
        try:
            import math
            # Bambu PLA Standard-Parameter
            DIAMETER_MM = 1.75
            DENSITY_G_CM3 = 1.24
            SPOOL_WEIGHT_G = 140.0

            # Berechne Gesamt-Filamentgewicht aus Länge
            length_mm = float(total_len)
            radius_mm = DIAMETER_MM / 2.0
            volume_mm3 = math.pi * (radius_mm ** 2) * length_mm
            filament_mass_g = (volume_mm3 / 1000.0) * DENSITY_G_CM3

            # Verbleibendes Gewicht = Filament × Prozent (ohne Spulengewicht!)
            remaining_g = filament_mass_g * (float(remain_percent) / 100.0)
            return round(remaining_g, 1)
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    # 3) Fallback: tray_weight × remain_percent (ungenau, da tray_weight nicht spezifisch ist)
    tray_weight = tray.get("tray_weight")
    if tray_weight is not None and remain_percent is not None:
        try:
            return round(float(tray_weight) * (float(remain_percent) / 100.0), 1)
        except (TypeError, ValueError):
            pass

    # 4) Kein valider Wert
    return None


def calc_slot_state(remain_percent: Optional[float]) -> str:
    if remain_percent is None:
        return "unknown"
    if remain_percent <= 0:
        return "empty"
    return "loaded"


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
        remain = _to_float(tray.get("remain") or tray.get("remain_percent"))

    total_len = None
    if isinstance(tray, dict):
        total_len = _to_int(tray.get("total_len"))

    nozzle_min = None
    nozzle_max = None
    if isinstance(tray, dict):
        nozzle_min = _to_float(tray.get("nozzle_temp_min") or tray.get("nozzle_min") or tray.get("nozzle_temp_min"))
        nozzle_max = _to_float(tray.get("nozzle_temp_max") or tray.get("nozzle_max") or tray.get("nozzle_temp_max"))

    remain_weight = None
    if isinstance(tray, dict):
        remain_weight = _to_float(tray.get("remain_weight") or tray.get("remain_weight_g"))

    tray_weight = None
    if isinstance(tray, dict):
        tray_weight = _to_float(tray.get("tray_weight"))

    remaining_grams = None
    if isinstance(tray, dict):
        remaining_grams = calc_remaining_grams(tray)

    # Extract material information (was missing!)
    tray_type = None
    tray_sub_brands = None
    tray_color = None
    if isinstance(tray, dict):
        tray_type = tray.get("tray_type")
        tray_sub_brands = tray.get("tray_sub_brands")
        tray_color = tray.get("tray_color")

    return {
        "slot": slot,
        "tray_uuid": tray.get("tray_uuid") if isinstance(tray, dict) else None,
        "tag_uid": tray.get("tag_uid") if isinstance(tray, dict) else None,
        "remain_weight": remain_weight,
        "tray_weight": tray_weight,
        "remain_percent": remain,
        "remaining_grams": remaining_grams,
        "total_len": total_len,
        "nozzle_temp_min": nozzle_min,
        "nozzle_temp_max": nozzle_max,
        # Add material information
        "tray_type": tray_type,
        "tray_sub_brands": tray_sub_brands,
        "tray_color": tray_color,
    }


def _normalize_ams_unit(ams_unit: AMSUnit, printer_serial: str, printer_name: str, printer_model: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    trays = ams_unit.get("trays") or []
    # AMS Lite detection: Check firmware name first, then fallback to printer model
    is_ams_lite = False
    
    # Method 1: Check mc_for_ams_firmware.firmware[0].name
    if payload:
        is_ams_lite = is_ams_lite_firmware(payload)
    
    # Method 2: Fallback to printer model (A1MINI has AMS Lite)
    if not is_ams_lite and printer_model:
        is_ams_lite = printer_model.upper() in ("A1MINI", "A1 MINI")
    
    return {
        "printer_serial": printer_serial,
        "printer_name": printer_name,
        "ams_id": ams_unit.get("ams_id"),
        "temp": ams_unit.get("temp"),
        "humidity": ams_unit.get("humidity"),
        "active_tray": ams_unit.get("active_tray"),
        "trays": [_normalize_tray(t) for t in trays],
        "is_ams_lite": is_ams_lite,
    }


def normalize_device(device_entry: Dict[str, Any], printer_name: Optional[str] = None, printer_model: Optional[str] = None, printer_id: Optional[str] = None) -> Dict[str, Any]:
    device_serial = str(_safe_get(device_entry, "device") or "unknown")
    ts = _safe_get(device_entry, "ts")
    payload = _safe_get(device_entry, "payload", {}) or {}
    printer_name_resolved = printer_name if printer_name is not None else device_serial
    
    # Fallback: If no printer_model from DB, try to extract from payload
    if not printer_model:
        printer_model = _extract_printer_model_from_payload(payload)

    try:
        ams_units = parse_ams(payload) or []
    except Exception:
        logger.exception("parse_ams failed for device %s", device_serial)
        ams_units = []
    
    # Also parse vt_tray (external spool holder) if present
    # WICHTIG: vt_tray ist NICHT automatisch AMS Lite!
    # - X1C/P1P/P1S: vt_tray = externer Spool-Halter (zusätzlich zum regulären AMS)
    # - A1/A1 Mini: vt_tray = der einzige Filament-Halter (= AMS Lite)
    try:
        vt_tray_unit = parse_vt_tray(payload)
        if vt_tray_unit:
            ams_units.append(vt_tray_unit)
    except Exception:
        logger.exception("parse_vt_tray failed for device %s", device_serial)

    # Bestimme ob dieses Gerät ein AMS Lite Gerät ist (A1/A1 Mini)
    is_ams_lite_device = printer_model and printer_model.upper() in ("A1MINI", "A1 MINI", "A1")
    
    normalized_ams = []
    for u in ams_units:
        try:
            is_vt_tray = u.get("ams_id") == 254
            normalized = _normalize_ams_unit(u, device_serial, printer_name_resolved, printer_model, payload)
            
            # vt_tray ist nur AMS Lite wenn es ein A1/A1 Mini ist
            # Bei X1C/P1P ist vt_tray ein externer Spool-Halter, KEIN AMS Lite
            if is_vt_tray and is_ams_lite_device:
                normalized["is_ams_lite"] = True
            elif is_vt_tray:
                # X1C/P1P: vt_tray als "external_spool" markieren, nicht als AMS Lite
                normalized["is_ams_lite"] = False
                normalized["is_external_spool"] = True  # Neues Flag für externen Spool-Halter
            
            normalized_ams.append(normalized)
        except Exception:
            logger.exception("Failed to normalize AMS unit for device %s: %s", device_serial, u)

    return {
        "device_serial": device_serial,
        "printer_id": printer_id,  # Add printer_id for multi-printer filtering
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


def normalize_live_state(
    live_state: Optional[Dict[str, Dict[str, Any]]],
    printer_name_by_serial: Optional[Dict[str, str]] = None,
    printer_model_by_serial: Optional[Dict[str, str]] = None,
    printer_id_by_serial: Optional[Dict[str, str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    devices: List[Dict[str, Any]] = []
    for device_id, entry in (live_state or {}).items():
        try:
            device_serial = _safe_get(entry, "device") or device_id
            printer_name = None
            if printer_name_by_serial and device_serial is not None:
                printer_name = printer_name_by_serial.get(device_serial)
            if printer_name is None:
                printer_name = device_serial or str(device_id)
            printer_model = None
            if printer_model_by_serial and device_serial is not None:
                printer_model = printer_model_by_serial.get(device_serial)
            printer_id = None
            if printer_id_by_serial and device_serial is not None:
                printer_id = printer_id_by_serial.get(device_serial)
            devices.append(normalize_device(entry, printer_name=printer_name, printer_model=printer_model, printer_id=printer_id))
        except Exception:
            logger.exception("Failed to normalize device %s", device_id)
            devices.append({
                "device_serial": device_id,
                "printer_id": None,
                "ts": entry.get("ts") if isinstance(entry, dict) else None,
                "online": False,
                "ams_units": [],
            })
    return {"devices": devices}


def normalize_all_live_state(
    printer_name_by_serial: Optional[Dict[str, str]] = None,
    printer_model_by_serial: Optional[Dict[str, str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    from app.services import live_state as live_state_module

    live = live_state_module.get_all_live_state()
    return normalize_live_state(live, printer_name_by_serial=printer_name_by_serial, printer_model_by_serial=printer_model_by_serial)


def has_real_ams_from_payload(payload: Any, printer_model: Optional[str] = None) -> bool:
    """Bestimme, ob ein Gerät ein echtes AMS hat (nicht AMS Lite), nur anhand des Payloads.

    WICHTIG: Gibt False für AMS Lite (A1 Mini) zurück - nur reguläre AMS zählen!
    
    Regeln (vereinfachte Form):
    - Wenn das geparste Ergebnis aus `parse_ams` mindestens eine Einheit enthält -> True
    - Wenn payload.get("ams_exist_bits_raw") == "1" -> True
    - Wenn payload.get("ams") ein dict ist und humidity_raw vorhanden ist -> True
    - ABER: Wenn printer_model == "A1MINI" -> False (AMS Lite zählt nicht!)
    """
    if not isinstance(payload, dict):
        return False
    
    # Exclude AMS Lite (A1 Mini) - diese sind kein "echtes" AMS für Übersicht
    if printer_model and printer_model.upper() in ("A1MINI", "A1 MINI"):
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


def device_has_real_ams_from_live_state(device_id: str, printer_model: Optional[str] = None) -> bool:
    """Check if device has real AMS (not AMS Lite).
    
    Falls back to extracting printer_model from printer_name if not provided.
    """
    from app.services import live_state as live_state_module

    state = live_state_module.get_live_state(device_id)
    if not state:
        return False
        
    # Fallback: Try to extract printer_model from printer_name in live state
    if not printer_model:
        printer_name = state.get("printer_name", "")
        if printer_name:
            name_upper = printer_name.upper()
            if "A1" in name_upper and "MINI" in name_upper:
                printer_model = "A1MINI"
    
    payload = state.get("payload") or {}
    return has_real_ams_from_payload(payload, printer_model=printer_model)


def global_has_real_ams() -> bool:
    """Check if there's at least one regular AMS (not AMS Lite) online."""
    from app.services import live_state as live_state_module

    all_state = live_state_module.get_all_live_state()
    for _, entry in (all_state or {}).items():
        # Fallback: Try to extract printer_model from printer_name
        printer_model = None
        printer_name = entry.get("printer_name", "")
        if printer_name:
            name_upper = printer_name.upper()
            if "A1" in name_upper and "MINI" in name_upper:
                printer_model = "A1MINI"
        
        if has_real_ams_from_payload(entry.get("payload") or {}, printer_model=printer_model):
            return True
    return False
