"""
Helpers to extract current job/print status from Bambu report payloads.
"""
from typing import Any, Dict, Optional

__all__ = ["parse_job"]


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


def _dict_lookup(obj: Dict[str, Any], *keys: str) -> Any:
    current: Any = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def parse_job(report_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract job/print status fields from a device/<serial>/report payload.
    Returns a flat dict with common fields for easy consumption.
    """
    # Primary: PrinterData (mapped) falls back to raw report
    printer_mapped = report_payload.get("printer") if isinstance(report_payload, dict) else None
    if printer_mapped and isinstance(printer_mapped, dict):
        pd = printer_mapped
        temps = pd.get("temperature") or {}
        layer = pd.get("layer") or {}
        job_pd = pd.get("job") or {}
        return {
            "gcode_state": pd.get("state") or pd.get("sub_state"),
            "progress_percent": _to_int(pd.get("progress")),
            "remain_time_s": _to_int(job_pd.get("time_remaining")),
            "gcode_file": job_pd.get("file"),
            "project_id": None,
            "task_id": None,
            "subtask_id": None,
            "job_id": None,
            "profile_id": None,
            "job_attr": None,
            "mc_stage": pd.get("sub_state"),
            "mc_print_stage": pd.get("sub_state"),
            "mc_print_sub_stage": None,
            "upgrade_state": None,
            "upgrade_module": None,
            "upgrade_message": None,
            "job_stage": None,
            "tray_target": None,
            "tray_current": None,
            "tray_previous": None,
            "virtual_tray": None,
            "nozzle_temp": temps.get("nozzle"),
            "bed_temp": temps.get("bed"),
            "layer_current": layer.get("current"),
            "layer_total": layer.get("total"),
        }

    root = _dict_lookup(report_payload, "print") or report_payload

    job_block = root.get("job") or {}
    upgrade_block = {}
    if isinstance(report_payload, dict):
        upgrade_block = report_payload.get("upgrade_state") or {}
    upgrade_block = upgrade_block or root.get("upgrade_state") or {}

    file_name = _first_defined(
        root.get("gcode_file"),
        root.get("file"),
        job_block.get("file"),
        job_block.get("gcode_file"),
    )
    percent = _first_defined(
        _to_int(root.get("percent")),
        _to_int(root.get("mc_percent")),
        _to_int(root.get("gcode_file_prepare_percent")),
    )
    remain_time = _first_defined(
        _to_int(root.get("remain_time")),
        _to_int(root.get("mc_remaining_time")),
    )

    ams_block = root.get("ams") or {}
    tray_target = _to_int(ams_block.get("tray_tar"))
    tray_current = _to_int(ams_block.get("tray_now"))
    tray_prev = _to_int(ams_block.get("tray_pre"))
    virtual_tray = _dict_lookup(root, "vt_tray") or _dict_lookup(root, "vir_slot")
    vt = None
    if isinstance(virtual_tray, dict):
        vt = {
            "id": _to_int(virtual_tray.get("id")),
            "type": virtual_tray.get("tray_type") or virtual_tray.get("tray_id_name") or virtual_tray.get("tray_name"),
            "color": virtual_tray.get("tray_color"),
            "weight": virtual_tray.get("tray_weight"),
            "remain": _to_int(virtual_tray.get("remain")),
        }

    return {
        "gcode_state": _first_defined(root.get("gcode_state"), root.get("print_state"), root.get("state")),
        "progress_percent": percent,
        "remain_time_s": remain_time,
        "gcode_file": file_name,
        "project_id": root.get("project_id"),
        "task_id": root.get("task_id"),
        "subtask_id": root.get("subtask_id"),
        "job_id": root.get("job_id"),
        "profile_id": root.get("profile_id"),
        "job_attr": root.get("job_attr"),
        "mc_stage": root.get("mc_stage"),
        "mc_print_stage": root.get("mc_print_stage"),
        "mc_print_sub_stage": root.get("mc_print_sub_stage"),
        "upgrade_state": upgrade_block.get("status"),
        "upgrade_module": upgrade_block.get("module"),
        "upgrade_message": upgrade_block.get("message"),
        "job_stage": job_block.get("cur_stage"),
        "tray_target": tray_target,
        "tray_current": tray_current,
        "tray_previous": tray_prev,
        "virtual_tray": vt,
    }


def main() -> None:
    """
    Simple CLI:
    python -m app.services.job_parser report.json > job.json
    """
    import json
    import sys

    if len(sys.argv) < 2:
        data = json.load(sys.stdin)
    else:
        with open(sys.argv[1], "r", encoding="utf-8") as handle:
            data = json.load(handle)

    parsed = parse_job(data)
    json.dump(parsed, sys.stdout, indent=2, ensure_ascii=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
