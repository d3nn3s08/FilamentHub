import time
import time
import os
import psutil
import yaml
import logging
import inspect
import platform
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_session
from app.routes.config_routes import _load_config

router = APIRouter(prefix="/api/system", tags=["System Status"])

START_TIME = time.time()


# -----------------------------
# CONFIG LADEN
# -----------------------------
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    try:
        logger = logging.getLogger('app')
        caller = None
        try:
            fr = inspect.stack()[1]
            caller = f"{fr.filename}:{fr.lineno} in {fr.function}"
        except Exception:
            caller = "unknown"
        logger.info(f"Writing config.yaml (system_routes.save_config) called from {caller}")
    except Exception:
        pass
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


class ModeUpdate(BaseModel):
    mode: str


# -----------------------------
# UPTIME FORMATTIERUNG
# -----------------------------
def format_uptime(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# -----------------------------
# DRUCKER-ERKENNUNG (Dummy)
# Wird später erweitert
# -----------------------------
def detect_printer_mode(config):
    return config.get("integrations", {}).get("mode", "bambu")


# -----------------------------
# SYSTEMSTATUS API
# -----------------------------
@router.get("/status")
def system_status():
    cfg_yaml = load_config()
    cfg_settings = None
    try:
        with next(get_session()) as session:
            cfg_settings = _load_config(session)
    except Exception:
        cfg_settings = None

    # APP BLOCK
    app_info = {
        "name": cfg_yaml["app"]["name"],
        "version": cfg_yaml["app"]["version"],
        "environment": cfg_yaml["app"]["environment"],
        "uptime": format_uptime(time.time() - START_TIME),
    }

    # LOGGING BLOCK
    logging_cfg = (cfg_settings or {}).get("logging") or cfg_yaml.get("logging", {})
    logging_status = (cfg_settings or {}).get("logging_status", {})
    logging_info = {
        "level": logging_cfg.get("level", cfg_yaml.get("logging", {}).get("level", "basic")),
        "modules": {},
    }
    if logging_status:
        logging_info["modules"] = {name: bool(val) for name, val in logging_status.items()}
    else:
        logging_info["modules"] = {
            name: cfg.get("enabled", False) for name, cfg in cfg_yaml.get("logging", {}).get("modules", {}).items()
        }

    # SYSTEM BLOCK (CPU/RAM/DISK)
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(".")
    
    system_info = {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "cpu_count": psutil.cpu_count(),
        "ram_percent": vm.percent,
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_used_gb": round(vm.used / (1024**3), 2),
        "ram_free_gb": round(vm.available / (1024**3), 2),
        "disk_percent": round((disk.used / disk.total) * 100, 1),
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine()
    }


    # ECHTER ONLINE-STATUS AUS DB
    import socket
    import httpx
    from app.models.printer import Printer
    from sqlmodel import select
    bambu_status = "offline"
    klipper_status = "offline"
    bambu_active = 0
    klipper_active = 0
    mode = detect_printer_mode(cfg_yaml)
    try:
        with next(get_session()) as session:
            printers = session.exec(select(Printer).where(Printer.active == True)).all()  # noqa: E712
            for p in printers:
                if p.printer_type in ["bambu", "bambu_lab"]:
                    bambu_active += 1
                if p.printer_type == "klipper":
                    klipper_active += 1
                if p.printer_type in ["bambu", "bambu_lab"]:
                    # Live-Test wie in printers.py
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2)
                        res = sock.connect_ex((p.ip_address, p.port or 6000))
                        sock.close()
                        if res == 0:
                            bambu_status = "online"
                    except Exception:
                        pass
                if p.printer_type == "klipper":
                    port = p.port or 7125
                    url = f"http://{p.ip_address}:{port}/server/info"
                    try:
                        r = httpx.get(url, timeout=2)
                        if r.status_code == 200:
                            klipper_status = "online"
                    except Exception:
                        pass
    except Exception:
        pass
    printer_info = {
        "bambu": bambu_status,
        "klipper": klipper_status,
        "mode": mode,
        "bambu_active": bambu_active,
        "klipper_active": klipper_active,
    }

    return {
        "app": app_info,
        "logging": logging_info,
        "system": system_info,
        "printers": printer_info
    }


@router.post("/mode")
def set_mode(update: ModeUpdate):
    allowed = {"bambu", "klipper", "dual", "standalone"}
    mode = update.mode.lower()
    if mode not in allowed:
        raise HTTPException(status_code=400, detail=f"Ungültiger Modus. Erlaubt: {', '.join(allowed)}")
    cfg = load_config()
    cfg.setdefault("integrations", {})
    cfg["integrations"]["mode"] = mode
    save_config(cfg)
    return {"success": True, "mode": mode}
