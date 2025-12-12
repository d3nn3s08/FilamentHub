import os
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional
import yaml

router = APIRouter(prefix="/api/logs", tags=["Logs"])

LOG_ROOT = "logs"


# -----------------------------
# Config laden
# -----------------------------
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# -----------------------------
# Hilfsfunktionen
# -----------------------------
def get_log_file(module: str, date: str = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    path = os.path.join(LOG_ROOT, module, f"{date}.log")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Keine Logdatei gefunden.")

    return path


def read_log_lines(path: str, limit: Optional[int] = None):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if limit:
        return lines[-limit:]

    return lines


# -----------------------------
# API ROUTES
# -----------------------------

@router.get("/modules")
def get_modules():
    config = load_config()
    modules = config["logging"]["modules"]
    return {m: modules[m]["enabled"] for m in modules}


@router.get("/today")
def get_today_log(
    module: str = Query(..., description="app | bambu | klipper | errors"),
    limit: Optional[int] = Query(None, description="Letzte X Zeilen")
):
    if module == "app":
        path = os.path.join(LOG_ROOT, "app", "app.log")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Keine Logdatei gefunden.")
    else:
        path = get_log_file(module)
    return {
        "module": module,
        "file": os.path.basename(path),
        "lines": read_log_lines(path, limit)
    }


@router.get("/date/{date}")
def get_log_by_date(
    date: str,
    module: str = Query(...),
    limit: Optional[int] = None
):
    path = get_log_file(module, date)
    return {
        "module": module,
        "file": os.path.basename(path),
        "lines": read_log_lines(path, limit)
    }


@router.get("/errors/latest")
def latest_error():
    try:
        path = get_log_file("errors")
        lines = read_log_lines(path)
        return {"latest_error": lines[-20:]}
    except:
        return {"latest_error": []}
