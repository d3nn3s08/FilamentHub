from fastapi import FastAPI, Query
from app.routes.debug_routes import get_logs, delete_logs

app = FastAPI()

@app.get("/api/debug/logs")
def api_get_logs(module: str = Query("app"), limit: int = Query(100)):
    return get_logs(module=module, limit=limit)

@app.delete("/api/debug/logs")
def api_delete_logs(module: str = Query("app")):
    return delete_logs(module=module)
import logging
import yaml
import os
from app.logging.runtime import reconfigure_logging

# Logging-Konfiguration aus config.yaml
def get_logging_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
    if not os.path.exists(config_path):
        return {
            "enabled": True,
            "level": "INFO",
            "keep_days": 14,
            "max_size_mb": 10,
            "backup_count": 3,
            "modules": {},
        }
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    logging_cfg = config.get("logging", {})
    return {
        "enabled": logging_cfg.get("enabled", True),
        "level": logging_cfg.get("level", "INFO"),
        "keep_days": logging_cfg.get("keep_days", 14),
        "max_size_mb": logging_cfg.get("max_size_mb", 10),
        "backup_count": logging_cfg.get("backup_count", 3),
        "modules": logging_cfg.get("modules", {}),
    }

log_settings = get_logging_config()
reconfigure_logging(log_settings)
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logging.getLogger().addHandler(console_handler)
# WICHTIG: Access-Logs explizit NICHT in app.log
for h in list(logging.getLogger("uvicorn.access").handlers):
    logging.getLogger("uvicorn.access").removeHandler(h)
from app.admin import enable_admin


def init_admin():
    import os

    logger = logging.getLogger("app")
    admin_hash = os.getenv("ADMIN_PASSWORD_HASH")
    if admin_hash:
        try:
            enable_admin(admin_hash)
            logger.info("Admin enabled via environment variable")
        except Exception:
            logger.exception("Failed to enable admin from environment variable")
    else:
        logger.info("Admin disabled (no ADMIN_PASSWORD_HASH)")


# Initialisiere optionalen Admin-Modus (einmalig)
init_admin()
from fastapi import FastAPI, Request, WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from services.printer_service import PrinterService
from app.services import mqtt_runtime
from app.monitoring.runtime_monitor import record_request
import time

# -----------------------------------------------------
# ROUTER & MODULE IMPORTS
# -----------------------------------------------------
from app.database import init_db

from app.routes.hello import router as hello_router
from app.routes.materials import router as materials_router
from app.routes.spools import router as spools_router
from app.routes.spool_numbers import router as spool_numbers_router  # NEU: Spulen-Nummern-System
from app.routes.log_routes import router as log_router
from app.routes.system_routes import router as system_router
from app.routes.debug_routes import router as debug_router
from app.routes.service_routes import router as service_router
from app.routes.database_routes import router as database_router
from app.routes.scanner_routes import router as scanner_router, debug_printer_router
from app.routes.mqtt_routes import router as mqtt_router
from app.routes.performance_routes import router as performance_router
from app.routes.printers import router as printers_router
from app.routes.jobs import router as jobs_router
from app.routes.statistics_routes import router as statistics_router

from app.routes.bambu_routes import router as bambu_router
from app.routes.admin_routes import router as admin_router
from app.routes.admin_coverage_routes import router as admin_coverage_router
from app.routes.settings_routes import router as settings_router
from app.routes.debug_ams_routes import router as debug_ams_router
from app.routes.debug_system_routes import router as debug_system_router
from app.routes.debug_performance_routes import router as debug_performance_router
from app.routes.debug_network_routes import router as debug_network_router
from app.routes.notification_routes import router as notification_router
from app.routes.config_routes import router as config_router
from app.routes import debug_log_routes
from app.routes import mqtt_runtime_routes
from app.routes.live_state_routes import router as live_state_router
from app.routes.ams_routes import router as ams_router

from app.websocket.log_stream import stream_log
from sqlmodel import Session, select
from app.database import engine
from app.models.printer import Printer


# -----------------------------------------------------
# FASTAPI APP
# -----------------------------------------------------

app = FastAPI(
    title="FilamentHub",
    description="Filament Management System fuer Bambu, Klipper & Standalone",
    version="0.1.0"
)

# -----------------------------------------------------
# MIDDLEWARE: RUNTIME / REQUEST MONITORING
# -----------------------------------------------------
@app.middleware("http")
async def runtime_metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    try:
        record_request(duration_ms)
    except Exception:
        pass
    return response

# -----------------------------------------------------
# TESTENDPUNKT & HEALTH CHECK
# -----------------------------------------------------
@app.get('/ping')
async def ping():
    return {'status': 'ok'}

@app.get('/health')
async def health():
    """Health check endpoint for Docker container monitoring"""
    return {'status': 'healthy', 'service': 'filamenthub'}

app.add_event_handler("startup", init_db)


@app.on_event("startup")
def log_startup_complete():
    logger = logging.getLogger("app")
    logger.info("[APP] Startup abgeschlossen – FilamentHub ist bereit")


# -----------------------------------------------------
# STATIC + TEMPLATES
# -----------------------------------------------------
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend/static"), name="frontend_static")
templates = Jinja2Templates(directory="frontend/templates")



# -----------------------------------------------------
# ROUTES - API
# -----------------------------------------------------
app.include_router(hello_router)
app.include_router(materials_router)
app.include_router(spools_router)
app.include_router(spool_numbers_router)  # NEU: Spulen-Nummern-System
app.include_router(log_router)
app.include_router(system_router)
app.include_router(debug_router)
app.include_router(service_router)
app.include_router(database_router)
app.include_router(scanner_router)
app.include_router(mqtt_router)
app.include_router(performance_router)
app.include_router(printers_router)
app.include_router(jobs_router)
app.include_router(statistics_router)

app.include_router(bambu_router)
app.include_router(admin_router)
app.include_router(admin_coverage_router, prefix="/api/admin")
app.include_router(settings_router)
app.include_router(debug_ams_router)
app.include_router(debug_system_router)
app.include_router(debug_performance_router)
app.include_router(debug_network_router)
app.include_router(debug_printer_router)
app.include_router(notification_router)
app.include_router(config_router)
app.include_router(debug_log_routes.router, prefix="/api/debug", tags=["debug"])

# Runtime MQTT control endpoints (separate from legacy mqtt_routes to avoid collisions)
app.include_router(mqtt_runtime_routes.router, prefix="/api/mqtt/runtime", tags=["mqtt"])

# Live state endpoints for real-time device data
app.include_router(live_state_router)
app.include_router(ams_router)


@app.on_event("startup")
def apply_auto_connect_on_startup():
    logger = logging.getLogger("app")
    try:
        with Session(engine) as session:
            printers = session.exec(select(Printer)).all()
    except Exception as exc:
        logger.exception("Failed to load printers for auto-connect startup: %s", exc)
        return

    for printer in printers:
        if getattr(printer, "auto_connect", False):
            logger.info("Applying auto-connect for printer %s (%s)", printer.name, printer.id)
            try:
                mqtt_runtime.apply_auto_connect(printer)
            except Exception as exc:
                logger.exception("Auto-connect startup failed for printer %s: %s", printer.id, exc)


# -----------------------------------------------------
# ROUTES - FRONTEND
# -----------------------------------------------------
@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        'dashboard.html',
        {
            'request': request,
            'title': 'FilamentHub - Dashboard',
            'active_page': 'dashboard'
        },
    )


@app.get('/materials', response_class=HTMLResponse)
async def materials_page(request: Request):
    return templates.TemplateResponse(
        'materials.html',
        {
            'request': request,
            'title': 'Materialien - FilamentHub',
            'active_page': 'materials'
        },
    )


@app.get('/spools', response_class=HTMLResponse)
async def spools_page(request: Request):
    return templates.TemplateResponse(
        'spools.html',
        {
            'request': request,
            'title': 'Spulen - FilamentHub',
            'active_page': 'spools'
        },
    )


@app.get('/ams', response_class=HTMLResponse)
async def ams_page(request: Request):
    return templates.TemplateResponse(
        'ams.html',
        {
            'request': request,
            'title': 'AMS - FilamentHub',
            'active_page': 'ams'
        },
    )


@app.get('/printers', response_class=HTMLResponse)
async def printers_page(request: Request):
    return templates.TemplateResponse(
        'printers.html',
        {
            'request': request,
            'title': 'Drucker - FilamentHub',
            'active_page': 'printers'
        },
    )


@app.get('/jobs', response_class=HTMLResponse)
async def jobs_page(request: Request):
    return templates.TemplateResponse(
        'jobs.html',
        {
            'request': request,
            'title': 'Druckauftraege - FilamentHub',
            'active_page': 'jobs'
        },
    )


@app.get('/statistics', response_class=HTMLResponse)
async def statistics_page(request: Request):
    return templates.TemplateResponse(
        'statistics.html',
        {
            'request': request,
            'title': 'Statistiken - FilamentHub',
            'active_page': 'statistics'
        },
    )


@app.get('/settings', response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        'settings.html',
        {
            'request': request,
            'title': 'Settings - FilamentHub',
            'active_page': 'settings'
        },
    )


@app.get('/logs', response_class=HTMLResponse)
async def logs_page(request: Request):
    # logs.html bleibt in app/templates
    logs_templates = Jinja2Templates(directory='app/templates')
    return logs_templates.TemplateResponse(
        'logs.html',
        {'request': request},
    )


@app.get('/debug', response_class=HTMLResponse)
async def debug_page(request: Request):
    from app.routes.settings_routes import get_setting, DEFAULTS

    debug_templates = Jinja2Templates(directory='app/templates')
    printers = []
    debug_center_mode = "lite"

    try:
        with Session(engine) as session:
            printers = session.exec(select(Printer)).all()
            debug_center_mode = get_setting(session, "debug_center_mode", DEFAULTS.get("debug_center_mode", "lite")) or "lite"
    except Exception:
        printers = []

    return debug_templates.TemplateResponse(
        'debug.html',
        {
            'request': request,
            'title': 'FilamentHub Debug Center',
            'active_page': 'debug',
            'printers': printers,
            'data_mode': debug_center_mode
        },
    )


@app.get('/ams-help', response_class=HTMLResponse)
async def ams_help_page(request: Request):
    """Simple helper page to visualize AMS slots from the latest report message."""
    help_templates = Jinja2Templates(directory='app/templates')
    return help_templates.TemplateResponse(
        'ams_help.html',
        {'request': request, 'title': 'AMS Helper'},
    )




# Zentraler PrinterService für MQTT → UniversalMapper → PrinterData Pipeline
if not hasattr(app.state, "printer_service"):
    app.state.printer_service = PrinterService()
