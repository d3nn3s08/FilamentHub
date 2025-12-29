"""Helpers to extract AMS data from Bambu report payloads."""
from typing import Any, Dict, List, Optional, TypedDict

__all__ = ["Tray", "AMSUnit", "parse_ams", "parse_active_tray"]


class Tray(TypedDict, total=False):
    tray_id: int
    name: Optional[str]
    material: Optional[str]
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
    return Tray(
        tray_id=_first_defined(_to_int(raw.get("tray_id")), _to_int(raw.get("id")), 0),
        name=_first_defined(raw.get("tray_name"), raw.get("name")),
        material=_first_defined(raw.get("tray_sub_brands"), raw.get("tray_type"), raw.get("material")),
        color=_first_defined(raw.get("tray_color"), raw.get("color")),
        remain=_first_defined(_to_float(raw.get("remain")), _to_float(raw.get("remain_percent")), _to_float(raw.get("remain_weight"))),
        humidity=raw.get("humidity"),
        temp=_first_defined(_to_float(raw.get("temp")), _to_float(raw.get("temperature"))),
        status=raw.get("status"),
        **{
            "tag_uid": raw.get("tag_uid"),
            "tray_uuid": raw.get("tray_uuid"),
            "total_len": _to_int(raw.get("total_len"))
        }
    )


def parse_ams(report_payload: Dict[str, Any]) -> List[AMSUnit]:
    """Extract AMS units and trays from a device/<serial>/report payload."""
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
