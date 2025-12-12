from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

from app.services.ams_parser import parse_ams
from app.services.universal_mapper import UniversalMapper

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
