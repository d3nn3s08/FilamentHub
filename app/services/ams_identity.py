from typing import Any, Dict, Optional


AMS_TYPE_LITE = "AMS_LITE"
AMS_TYPE_FULL = "AMS_FULL"
AMS_TYPE_EXTERNAL = "EXTERNAL"


def normalize_ams_identifier(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    compact = raw.replace("-", "").replace(" ", "")
    if compact and set(compact) == {"0"}:
        return None
    return raw


def has_real_ams_identifier(value: Any) -> bool:
    return normalize_ams_identifier(value) is not None


def feeder_type_from_name(name: Optional[str]) -> str:
    raw = str(name or "").strip().lower()
    if "lite" in raw:
        return AMS_TYPE_LITE
    if "ams" in raw:
        return AMS_TYPE_FULL
    return AMS_TYPE_FULL


def firmware_name_by_id(report_payload: Dict[str, Any], firmware_id: Any) -> Optional[str]:
    try:
        upgrade_state = (report_payload.get("upgrade_state") or {})
        if not upgrade_state and isinstance(report_payload.get("print"), dict):
            upgrade_state = report_payload["print"].get("upgrade_state") or {}
        mc_for_ams = upgrade_state.get("mc_for_ams_firmware") or {}
        firmware_list = mc_for_ams.get("firmware") or []
        target_id = int(firmware_id)
        for item in firmware_list:
            if isinstance(item, dict) and int(item.get("id", -1)) == target_id:
                return item.get("name")
    except Exception:
        return None
    return None


def feeder_type_for_ams_unit(ams_id: Any, report_payload: Optional[Dict[str, Any]] = None) -> str:
    if int(ams_id or 0) == 254:
        return AMS_TYPE_EXTERNAL
    if isinstance(report_payload, dict):
        fw_name = firmware_name_by_id(report_payload, ams_id)
        if fw_name:
            return feeder_type_from_name(fw_name)
    return AMS_TYPE_FULL


def feeder_key(feeder_type: Optional[str], feeder_id: Any) -> str:
    normalized_type = str(feeder_type or AMS_TYPE_FULL).strip().upper()
    try:
        normalized_id = int(feeder_id)
    except Exception:
        normalized_id = feeder_id
    return f"{normalized_type}:{normalized_id}"


def normalize_feeder_key(feeder_type: Optional[str], feeder_id: Any) -> Optional[str]:
    if feeder_id is None:
        return None

    raw_type = str(feeder_type or "").strip().upper() or None
    raw_id = feeder_id

    if isinstance(raw_id, str):
        compact = raw_id.strip()
        if not compact:
            return None
        if ":" in compact:
            embedded_type, embedded_id = compact.split(":", 1)
            if not raw_type:
                raw_type = embedded_type.strip().upper() or None
            raw_id = embedded_id.strip()
        else:
            raw_id = compact

    return feeder_key(raw_type or AMS_TYPE_FULL, raw_id)
