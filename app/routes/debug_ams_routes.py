from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlmodel import Session, select

from app.services.ams_parser import parse_ams
from app.services.universal_mapper import UniversalMapper
from app.services.ams_normalizer import normalize_live_state
from app.services.live_state import get_all_live_state
from app.database import get_session
from app.models.printer import Printer
from app.models.spool import Spool

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def _stub_raw_payload():
    # Synthetischer Payload für Debug; kann später durch echten Printer-Feed ersetzt werden
    return {
        "ams": {
            "modules": [
                {
                    "ams_id": 0,
                    "active_tray": 1,
                    "tray_count": 4,
                    "trays": [
                        {"tray_id": 0, "tray_uuid": "UUID-A0-S0", "material": "PLA"},
                        {"tray_id": 1, "tray_uuid": "UUID-A0-S1", "material": "PETG"},
                        {"tray_id": 2, "tray_uuid": None, "material": None},
                        {"tray_id": 3, "tray_uuid": "UUID-A0-S3", "material": "ABS"},
                    ],
                },
                {
                    "ams_id": 1,
                    "active_tray": 2,
                    "tray_count": 4,
                    "trays": [
                        {"tray_id": 0, "tray_uuid": "UUID-A1-S0", "material": "PA"},
                        {"tray_id": 1, "tray_uuid": "UUID-A1-S1", "material": None},
                        {"tray_id": 2, "tray_uuid": "UUID-A1-S2", "material": "TPU"},
                        {"tray_id": 3, "tray_uuid": None, "material": None},
                    ],
                },
            ]
        }
    }


@router.get("/debug/ams", response_class=HTMLResponse)
async def debug_ams_page(request: Request):
    return templates.TemplateResponse(
        "debug_ams.html",
        {"request": request, "title": "AMS Debug View", "active_page": "debug"},
    )


@router.get("/api/debug/ams")
async def debug_ams_api():
    raw = _stub_raw_payload()
    parsed = parse_ams(raw)
    mapper = UniversalMapper()
    mapped_out = mapper.map(raw)
    mapped_units = getattr(mapped_out, "ams_units", None)
    return JSONResponse(
        {
            "raw": raw,
            "parsed": parsed,
            "mapped": mapped_units,
        }
    )


def _build_printer_maps(session: Session) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    name_map: dict[str, str] = {}
    model_map: dict[str, str] = {}
    id_map: dict[str, str] = {}

    for printer in session.exec(select(Printer)).all():
        serial = str(printer.cloud_serial or "").strip()
        if not serial:
            continue
        if printer.name:
            name_map[serial] = printer.name
        if printer.model:
            model_map[serial] = printer.model
        id_map[serial] = printer.id
    return name_map, model_map, id_map


def _build_spool_matches(session: Session) -> list[dict]:
    rows: list[dict] = []
    stmt = select(Spool).where(Spool.printer_id.is_not(None), Spool.ams_slot.is_not(None))
    for spool in session.exec(stmt).all():
        rows.append(
            {
                "id": spool.id,
                "spool_number": spool.spool_number,
                "name": spool.name,
                "vendor": spool.vendor,
                "printer_id": spool.printer_id,
                "ams_id": spool.ams_id,
                "ams_slot": spool.ams_slot,
                "last_slot": spool.last_slot,
                "tag_uid": spool.tag_uid,
                "tray_uuid": spool.tray_uuid,
                "tray_type": spool.tray_type,
                "remain_percent": spool.remain_percent,
                "last_seen_in_ams_type": spool.last_seen_in_ams_type,
                "last_seen_timestamp": spool.last_seen_timestamp,
                "weight_current": spool.weight_current,
                "weight_full": spool.weight_full,
                "is_empty": spool.is_empty,
            }
        )
    return rows


@router.get("/api/debug/diagnostics")
async def debug_diagnostics_api(session: Session = Depends(get_session)):
    live = get_all_live_state() or {}
    printer_name_map, printer_model_map, printer_id_map = _build_printer_maps(session)
    normalized = normalize_live_state(
        live,
        printer_name_by_serial=printer_name_map,
        printer_model_by_serial=printer_model_map,
        printer_id_by_serial=printer_id_map,
    )

    per_device = []
    for serial, entry in live.items():
        payload = entry.get("payload") if isinstance(entry, dict) else {}
        parsed = parse_ams(payload or {}) if isinstance(payload, dict) else []
        mapped_units = getattr(UniversalMapper().map(payload or {}), "ams_units", None)
        per_device.append(
            {
                "serial": serial,
                "printer_name": entry.get("printer_name") if isinstance(entry, dict) else None,
                "raw": entry,
                "parsed": parsed,
                "mapped": mapped_units,
            }
        )

    return JSONResponse(
        {
            "captured_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "device_count": len(live),
            "devices": per_device,
            "normalized": normalized,
            "db_matches": _build_spool_matches(session),
        }
    )
