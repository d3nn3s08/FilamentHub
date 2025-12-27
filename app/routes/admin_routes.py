from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile
from starlette.status import HTTP_401_UNAUTHORIZED
from sqlmodel import Session, select
from app.database import get_session
from app.models.settings import Setting, UserFlag
import importlib
import json
import logging
import os
import subprocess
import secrets
import time
from datetime import datetime
import bcrypt
from typing import Dict, Optional, Tuple, Union

router = APIRouter()

# Admin Panel (vollständig, geschützt)
@router.get("/admin", response_class=HTMLResponse)
def admin_panel_page(request: Request):
    token = request.cookies.get("admin_token")
    _cleanup_expired_tokens()
    if not is_token_active(token):
        audit("admin_access_denied", {"path": "/admin", "ip": client_ip(request)})
        return templates.TemplateResponse("admin_login.html", {"request": request})
    audit("admin_access", {"path": "/admin", "ip": client_ip(request)})
    return templates.TemplateResponse("admin_panel.html", {"request": request})

templates = Jinja2Templates(directory="frontend/templates")

# --- SECURITY CONFIG ---

# Load and normalize ADMIN_PASSWORD_HASH from environment. Must be present.
def load_admin_password_hash() -> bytes:
    try:
        raw = os.environ["ADMIN_PASSWORD_HASH"]
    except KeyError:
        raise RuntimeError("ADMIN_PASSWORD_HASH must be set in environment")
    if not isinstance(raw, str):
        # If already bytes-like, ensure bytes
        return raw if isinstance(raw, (bytes, bytearray)) else str(raw).encode("utf-8")
    # Normalize $2y$ -> $2b$ without changing rest of the hash
    if raw.startswith("$2y$"):
        raw = "$2b$" + raw[4:]
    return raw.encode("utf-8")

# Ensure loaded at import time (app start) and fail fast if missing
ADMIN_PASSWORD_HASH = load_admin_password_hash()

# token store: token -> expiry_timestamp
admin_tokens: Dict[str, int] = {}
TOKEN_TTL = 3600  # seconds

# In-memory rate limit store for login attempts per IP
# Structure: { ip: {"count": int, "last_ts": float, "blocked_until": float} }
failed_logins: Dict[str, dict] = {}
# max 5 failed attempts -> block for 10 minutes
MAX_FAILED = 5
BLOCK_SECONDS = 10 * 60

# Cookie security: read from environment, default to False for local/HTTP deployments
COOKIE_SECURE = os.environ.get("ADMIN_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")

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
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded
    client = request.client
    return client.host if client else "unknown"
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


# --- Security helper functions ---
def verify_admin_password(password: str) -> bool:
    try:
        if not password:
            return False
        return bool(bcrypt.checkpw(password.encode("utf-8"), ADMIN_PASSWORD_HASH))
    except Exception:
        # don't leak errors or secrets
        return False


def create_admin_token() -> Tuple[str, int]:
    token = secrets.token_hex(16)
    expiry = int(time.time()) + TOKEN_TTL
    admin_tokens[token] = expiry
    return token, expiry


def _cleanup_expired_tokens():
    now = int(time.time())
    expired = [t for t, exp in admin_tokens.items() if exp <= now]
    for t in expired:
        del admin_tokens[t]


def is_token_active(token: Optional[str]) -> bool:
    if not token:
        return False
    expiry = admin_tokens.get(token)
    if not expiry:
        return False
    if expiry <= int(time.time()):
        # expired: remove
        try:
            del admin_tokens[token]
        except KeyError:
            pass
        return False
    return True


def admin_required(request: Request):
    token = request.cookies.get("admin_token")
    _cleanup_expired_tokens()
    if not is_token_active(token):
        audit("admin_auth_required_failed", {"ip": client_ip(request)})
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Nicht autorisiert")

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
    if not is_token_active(token):
        audit("admin_access_denied", {"path": "/admin/notifications", "ip": client_ip(request)})
        return templates.TemplateResponse("admin_login.html", {"request": request})
    audit("admin_access", {"path": "/admin/notifications", "ip": client_ip(request)})
    return templates.TemplateResponse("admin_notifications.html", {"request": request})

@router.post("/api/admin/login")
async def admin_login(request: Request):
    form = await request.form()
    password_data: Union[str, UploadFile, None] = form.get("password")
    ip = client_ip(request)

    if isinstance(password_data, UploadFile):
        await password_data.close()
        audit("admin_login_failed", {"ip": ip, "reason": "password_invalid_type"})
        return JSONResponse({"success": False, "error": "Falsches Passwort"}, status_code=HTTP_401_UNAUTHORIZED)

    password: Optional[str] = password_data

    # check block
    entry = failed_logins.get(ip, {"count": 0, "last_ts": 0.0, "blocked_until": 0.0})
    now = time.time()
    if entry.get("blocked_until", 0) and entry["blocked_until"] > now:
        audit("admin_login_blocked", {"ip": ip, "blocked_until": entry["blocked_until"]})
        return JSONResponse({"success": False, "error": "Zu viele Fehlversuche, bitte später erneut versuchen."}, status_code=429)

    # reset counter if last attempt older than block window
    if entry.get("last_ts") and now - entry.get("last_ts", 0) > BLOCK_SECONDS:
        entry["count"] = 0

    if not password:
        audit("admin_login_failed", {"ip": ip, "reason": "no_password"})
        return JSONResponse({"success": False, "error": "Falsches Passwort"}, status_code=HTTP_401_UNAUTHORIZED)

    if verify_admin_password(password):
        token, expiry = create_admin_token()
        response = JSONResponse({"success": True})
        response.set_cookie("admin_token", token, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=TOKEN_TTL)
        # reset failed attempts on success
        if ip in failed_logins:
            try:
                del failed_logins[ip]
            except KeyError:
                pass
        audit("admin_login_success", {"ip": ip})
        return response

    # failed attempt
    entry["count"] = entry.get("count", 0) + 1
    entry["last_ts"] = now
    if entry["count"] >= MAX_FAILED:
        entry["blocked_until"] = now + BLOCK_SECONDS
        entry["count"] = 0
        audit("admin_login_locked", {"ip": ip, "blocked_until": entry["blocked_until"]})
    else:
        audit("admin_login_failed", {"ip": ip, "count": entry["count"]})

    failed_logins[ip] = entry
    return JSONResponse({"success": False, "error": "Falsches Passwort"}, status_code=HTTP_401_UNAUTHORIZED)


# Logout: HttpOnly-Cookie serverseitig löschen und Token invalidieren
@router.post("/api/admin/logout")
async def admin_logout(request: Request):
    token = request.cookies.get("admin_token")
    if token and token in admin_tokens:
        try:
            del admin_tokens[token]
        except KeyError:
            pass
    response = JSONResponse({"success": True})
    response.delete_cookie("admin_token", path="/")
    return response

# Begrüßungstext laden (öffentlich lesbar)
@router.get("/api/admin/greeting")
def get_greeting_text(request: Request, session: Session = Depends(get_session)):
    # Kein admin_required - jeder darf den Begrüßungstext lesen
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

# Reset Pro-Mode Warnung (Admin)
@router.post("/api/admin/debug/reset-pro-mode")
def reset_pro_mode_warning(request: Request, session: Session = Depends(get_session)):
    """Setzt die Pro-Mode Warnung zurück (Admin-Funktion)"""
    token = request.cookies.get("admin_token")
    _cleanup_expired_tokens()
    if not is_token_active(token):
        audit("admin_reset_promode_denied", {"ip": client_ip(request)})
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Nicht authentifiziert")

    setting = session.get(Setting, "debug.pro_mode_accepted")
    if setting:
        session.delete(setting)
        session.commit()
        audit("admin_reset_promode", {"ip": client_ip(request), "previous_value": setting.value})
        logging.getLogger("app").info("Pro-Mode Warnung wurde vom Admin zurückgesetzt")
        return {"success": True, "message": "Pro-Mode Warnung wurde zurückgesetzt"}
    else:
        audit("admin_reset_promode", {"ip": client_ip(request), "previous_value": None})
        return {"success": True, "message": "Pro-Mode Warnung war bereits zurückgesetzt"}
