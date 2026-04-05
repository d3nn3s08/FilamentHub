"""Helpers to extract AMS data from Bambu report payloads."""
from typing import Any, Dict, List, Optional, TypedDict

__all__ = ["Tray", "AMSUnit", "parse_ams", "parse_active_tray"]


class Tray(TypedDict, total=False):
    tray_id: int
    name: Optional[str]
    material: Optional[str]
    tray_type: Optional[str]
    tray_sub_brands: Optional[str]
    tray_color: Optional[str]
    color: Optional[str]
    remain: Optional[float]
    humidity: Optional[float]
    temp: Optional[float]
    status: Optional[str]
    tag_uid: Optional[str]
    tray_uuid: Optional[str]
    total_len: Optional[int]


class AMSUnit(TypedDict, total=False):
    ams_id: int
    active_tray: Optional[int]
    trays: List[Tray]
    humidity: Optional[float]
    temp: Optional[float]
    status: Optional[str]


def _first_defined(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
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


def _dict_lookup(obj: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = obj
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _parse_tray(raw: Dict[str, Any]) -> Tray:
    # Extract possible weight fields from various firmware variants
    _remain_weight = _first_defined(
        _to_float(raw.get("remain_weight")),
        _to_float(raw.get("remain_weight_g")),
        _to_float(raw.get("remain_g")),
    )

    _tray_weight = _first_defined(
        _to_float(raw.get("tray_weight")),
        _to_float(raw.get("tray_weight_g")),
        _to_float(raw.get("total_grams")),
        _to_float(raw.get("total_g")),
        _to_float(raw.get("total")),
    )

    return Tray(
        tray_id=_first_defined(_to_int(raw.get("tray_id")), _to_int(raw.get("id")), 0),
        name=_first_defined(raw.get("tray_name"), raw.get("name")),
        material=_first_defined(raw.get("tray_sub_brands"), raw.get("tray_type"), raw.get("material")),
        tray_type=raw.get("tray_type"),
        tray_sub_brands=raw.get("tray_sub_brands"),
        tray_color=raw.get("tray_color"),
        color=_first_defined(raw.get("tray_color"), raw.get("color")),
        remain=_first_defined(_to_float(raw.get("remain")), _to_float(raw.get("remain_percent")), _to_float(raw.get("remain_weight"))),
        humidity=raw.get("humidity"),
        temp=_first_defined(_to_float(raw.get("temp")), _to_float(raw.get("temperature"))),
        status=raw.get("status"),
        **{
            "tag_uid": raw.get("tag_uid"),
            "tray_uuid": raw.get("tray_uuid"),
            "total_len": _to_int(raw.get("total_len")),
            "remain_weight": _remain_weight,
            "tray_weight": _tray_weight,
        }
    )


def is_ams_lite_firmware(report_payload: Dict[str, Any]) -> bool:
    """Check if device has AMS Lite based on firmware name.
    
    A1 Mini MQTT payload contains:
    upgrade_state.mc_for_ams_firmware.firmware[0].name = "AMS Lite"
    """
    try:
        upgrade_state = _dict_lookup(report_payload, "upgrade_state") or _dict_lookup(report_payload, "print", "upgrade_state") or {}
        mc_for_ams = upgrade_state.get("mc_for_ams_firmware") or {}
        firmware_list = mc_for_ams.get("firmware") or []
        
        if isinstance(firmware_list, list) and len(firmware_list) > 0:
            first_firmware = firmware_list[0]
            if isinstance(first_firmware, dict):
                firmware_name = first_firmware.get("name", "")
                return "AMS Lite" in firmware_name or "ams lite" in firmware_name.lower()
    except Exception:
        pass
    return False


def parse_ams(report_payload: Dict[str, Any]) -> List[AMSUnit]:
    """Extract AMS units and trays from a device/<serial>/report payload.
    
    Supports:
    - Standard AMS with multiple units (ams[].tray[])
    - AMS Lite / single slot AMS (ams with only 1 tray = AMS Lite)
    
    NOTE: vt_tray (virtual/external tray) is NOT part of AMS - it's for the printer's external extruder!
    """
    # Some firmwares nest AMS under "print" -> "ams", others at the root
    ams_root = _dict_lookup(report_payload, "ams") or _dict_lookup(report_payload, "print", "ams") or {}
    ams_list = ams_root.get("ams") or ams_root.get("modules") or []
    if not isinstance(ams_list, list):
        return []

    result: List[AMSUnit] = []
    for ams in ams_list:
        if not isinstance(ams, dict):
            continue
        trays_raw = ams.get("tray") or ams.get("trays") or []
        trays: List[Tray] = []
        if isinstance(trays_raw, list):
            for entry in trays_raw:
                if isinstance(entry, dict):
                    trays.append(_parse_tray(entry))

        result.append(
            AMSUnit(
                ams_id=_first_defined(_to_int(ams.get("ams_id")), _to_int(ams.get("id")), 0),
                active_tray=_first_defined(
                    _to_int(ams.get("active_tray")),
                    _to_int(ams.get("active_slot")),
                    _to_int(ams_root.get("active_tray")),
                    _to_int(ams_root.get("active_slot")),
                    _to_int(ams_root.get("tray_now")),
                    _to_int(ams_root.get("tray_tar")),
                ),
                trays=trays,
                humidity=ams.get("humidity"),
                temp=_first_defined(_to_float(ams.get("temp")), _to_float(ams.get("temperature"))),
                status=ams.get("status"),
            )
        )

    return result


def parse_vt_tray(report_payload: Dict[str, Any]) -> Optional[AMSUnit]:
    """Parse vt_tray (virtual tray / external spool holder) as a single-slot AMS unit.
    
    A1 Mini and other printers have vt_tray for external spools (slot 254).
    This is separate from the regular AMS units.
    """
    vt_tray = _dict_lookup(report_payload, "vt_tray") or _dict_lookup(report_payload, "print", "vt_tray")
    
    if not vt_tray or not isinstance(vt_tray, dict):
        return None
    
    # Parse vt_tray as a single tray
    tray = _parse_tray(vt_tray)
    
    return AMSUnit(
        ams_id=254,  # Virtual tray uses ID 254
        active_tray=254,
        trays=[tray],
        humidity=None,
        temp=None,
        status=None,
    )


def parse_active_tray(report_payload: Dict[str, Any]) -> Optional[int]:
    """Convenience helper to grab the active tray from a report payload."""
    ams_root = report_payload.get("ams") or _dict_lookup(report_payload, "print", "ams") or {}
    return _first_defined(
        _to_int(ams_root.get("active_tray")),
        _to_int(ams_root.get("active_slot")),
        _to_int(ams_root.get("tray_now")),
        _to_int(ams_root.get("tray_tar")),
    )


def main() -> None:
    """Simple CLI: python -m app.services.ams_parser report.json > parsed.json"""
    import json
    import sys

    if len(sys.argv) < 2:
        data = json.load(sys.stdin)
    else:
        with open(sys.argv[1], "r", encoding="utf-8") as handle:
            data = json.load(handle)

    parsed = parse_ams(data)
    json.dump(parsed, sys.stdout, indent=2, ensure_ascii=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
