from typing import Any, Dict, Optional


AMS_TYPE_LITE = "AMS_LITE"
AMS_TYPE_FULL = "AMS_FULL"
AMS_TYPE_EXTERNAL = "EXTERNAL"


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
