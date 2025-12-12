from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_401_UNAUTHORIZED
from sqlmodel import Session, select
from app.database import get_session
from app.models.settings import Setting, UserFlag
import os
import subprocess
import importlib
import json
import logging
from datetime import datetime

router = APIRouter()

# Admin Panel (vollständig, geschützt)
@router.get("/admin", response_class=HTMLResponse)
def admin_panel_page(request: Request):
    token = request.cookies.get("admin_token")
    if token not in admin_tokens:
        audit("admin_access_denied", {"path": "/admin", "ip": client_ip(request)})
        return templates.TemplateResponse("admin_login.html", {"request": request})
    audit("admin_access", {"path": "/admin", "ip": client_ip(request)})
    return templates.TemplateResponse("admin_panel.html", {"request": request})

templates = Jinja2Templates(directory="frontend/templates")
admin_tokens = set()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# --- Audit Logger ---
_audit_logger = logging.getLogger("admin.audit")
if not _audit_logger.handlers:
    os.makedirs(os.path.join("logs", "admin"), exist_ok=True)
    from logging.handlers import TimedRotatingFileHandler
    audit_file = os.path.join("logs", "admin", "admin_audit.log")
    audit_handler = TimedRotatingFileHandler(
        audit_file,
        when="midnight",
        backupCount=14,
        encoding="utf-8",
        utc=False,
    )
    audit_handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(audit_handler)
    _audit_logger.setLevel(logging.INFO)
def audit(event: str, details: dict):
    try:
        payload = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "event": event,
            "details": details or {}
        }
        _audit_logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass

def client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for") or request.client.host
# --- Migration auslösen (Alembic upgrade head) ---
@router.post("/api/admin/migrate")
def run_migration(request: Request):
    admin_required(request)
    audit("admin_migrate_start", {"ip": client_ip(request)})
    try:
        result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True, check=True)
        audit("admin_migrate_success", {"ip": client_ip(request), "stdout": (result.stdout or "")[:500]})
        return {"success": True, "output": result.stdout}
    except subprocess.CalledProcessError as e:
        audit("admin_migrate_error", {"ip": client_ip(request), "stderr": (e.stderr or str(e))[:500]})
        return {"success": False, "error": e.stderr or str(e)}

# --- Eintrag löschen (Tabelle + ID) ---
@router.post("/api/admin/delete")
async def delete_entry(request: Request, session: Session = Depends(get_session)):
    admin_required(request)
    data = await request.json()
    table = data.get("table")
    id_ = data.get("id")
    if not table or not id_:
        audit("admin_delete_invalid", {"ip": client_ip(request), "table": table, "id": id_})
        return {"success": False, "error": "Tabelle und ID erforderlich."}
    # Mapping Tabellenname zu Model
    model_map = {
        "material": "app.models.material.Material",
        "spool": "app.models.spool.Spool",
        "printer": "app.models.printer.Printer",
        "job": "app.models.job.Job",
        "userflag": "app.models.settings.UserFlag",
        "setting": "app.models.settings.Setting"
    }
    if table not in model_map:
        audit("admin_delete_unknown_table", {"ip": client_ip(request), "table": table})
        return {"success": False, "error": "Unbekannte Tabelle."}
    module_name, class_name = model_map[table].rsplit('.', 1)
    model_cls = getattr(importlib.import_module(module_name), class_name)
    obj = session.get(model_cls, id_)
    if not obj:
        audit("admin_delete_not_found", {"ip": client_ip(request), "table": table, "id": id_})
        return {"success": False, "error": f"Kein Eintrag mit ID {id_} in {table}."}
    session.delete(obj)
    session.commit()
    audit("admin_delete_success", {"ip": client_ip(request), "table": table, "id": id_})
    return {"success": True}


# Admin Notifications Seite schützen
@router.get("/admin/notifications", response_class=HTMLResponse)
def admin_notifications_page(request: Request):
    token = request.cookies.get("admin_token")
    if token not in admin_tokens:
        audit("admin_access_denied", {"path": "/admin/notifications", "ip": client_ip(request)})
        return templates.TemplateResponse("admin_login.html", {"request": request})
    audit("admin_access", {"path": "/admin/notifications", "ip": client_ip(request)})
    return templates.TemplateResponse("admin_notifications.html", {"request": request})

@router.post("/api/admin/login")
async def admin_login(request: Request):
    form = await request.form()
    password = form.get("password")
    if password == ADMIN_PASSWORD:
        import secrets
        token = secrets.token_hex(16)
        admin_tokens.add(token)
        response = JSONResponse({"success": True})
        response.set_cookie("admin_token", token, httponly=True)
        audit("admin_login_success", {"ip": client_ip(request)})
        return response
    audit("admin_login_failed", {"ip": client_ip(request)})
    return JSONResponse({"success": False, "error": "Falsches Passwort"}, status_code=HTTP_401_UNAUTHORIZED)


# Logout: HttpOnly-Cookie serverseitig löschen und Token invalidieren
@router.post("/api/admin/logout")
async def admin_logout(request: Request):
    token = request.cookies.get("admin_token")
    if token and token in admin_tokens:
        admin_tokens.discard(token)
    response = JSONResponse({"success": True})
    # Cookie sofort löschen
    response.delete_cookie("admin_token", path="/")
    return response


def admin_required(request: Request):
    token = request.cookies.get("admin_token")
    if token not in admin_tokens:
        audit("admin_auth_required_failed", {"ip": client_ip(request)})
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Nicht autorisiert")

# Begrüßungstext laden
@router.get("/api/admin/greeting")
def get_greeting_text(request: Request, session: Session = Depends(get_session)):
    admin_required(request)
    audit("admin_greeting_get", {"ip": client_ip(request)})
    setting = session.exec(select(Setting).where(Setting.key == "greeting_text")).first()
    return {"greeting_text": setting.value if setting else ""}

# Begrüßungstext speichern
@router.post("/api/admin/greeting")
async def set_greeting_text(request: Request, session: Session = Depends(get_session)):
    admin_required(request)
    data = await request.json()
    text = data.get("greeting_text", "")
    audit("admin_greeting_set", {"ip": client_ip(request), "len": len(text or "")})
    setting = session.exec(select(Setting).where(Setting.key == "greeting_text")).first()
    if setting:
        setting.value = text
    else:
        setting = Setting(key="greeting_text", value=text)
        session.add(setting)
    session.commit()
    return {"success": True}

# User-Flag abfragen (ob Popup schon gesehen)
@router.get("/api/user/flag/{user_id}/{flag}")
def get_user_flag(user_id: str, flag: str, session: Session = Depends(get_session)):
    userflag = session.exec(select(UserFlag).where(UserFlag.user_id == user_id, UserFlag.flag == flag)).first()
    audit("admin_userflag_get", {"user_id": user_id, "flag": flag})
    return {"value": userflag.value if userflag else False}

# User-Flag setzen (z.B. nach erstem Popup)
@router.post("/api/user/flag/{user_id}/{flag}")
async def set_user_flag(user_id: str, flag: str, request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    value = data.get("value", True)
    userflag = session.exec(select(UserFlag).where(UserFlag.user_id == user_id, UserFlag.flag == flag)).first()
    if userflag:
        userflag.value = value
    else:
        userflag = UserFlag(user_id=user_id, flag=flag, value=value)
        session.add(userflag)
    session.commit()
    audit("admin_userflag_set", {"user_id": user_id, "flag": flag, "value": bool(value)})
    return {"success": True}
