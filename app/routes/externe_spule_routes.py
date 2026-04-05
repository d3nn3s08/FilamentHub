from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["External Spool"])

templates = Jinja2Templates(directory="frontend/templates")

@router.get("/externe-spule", response_class=HTMLResponse)
async def externe_spule_page(request: Request):
    """
    Seite für Drucker ohne AMS - Manuelle Spulenverwaltung
    """
    return templates.TemplateResponse(
        "externe_spule.html",
        {
            "request": request,
            "active_page": "externe_spule",
            "page_title": "Externe Spule",
            "page_subtitle": "Filament-Management ohne AMS - Manuelle Spulen laden & tracken",
            "app_version": "1.0.0",
            "design_version": "1.0.0"
        }
    )
