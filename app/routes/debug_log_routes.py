import os
from typing import List
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/debug", tags=["Debug Logs"])

LOG_PATH = os.path.join("logs", "app", "app.log")
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

def _tail_lines(path: str, limit: int) -> List[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []
    if limit <= 0:
        return []
    return lines[-limit:]

def _parse_level(line: str) -> str:
    upper = line.upper()
    if " ERROR" in upper or upper.startswith("ERROR"):
        return "error"
    if " WARN" in upper or " WARNING" in upper or upper.startswith("WARN"):
        return "warning"
    return "info"

@router.get("/logs")
async def debug_logs(limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT), level: str | None = None):
    try:
        lines = _tail_lines(LOG_PATH, limit)
        level_norm = (level or "").lower()
        allowed = {"info", "warning", "error"}
        logs = []
        for line in lines:
            ts = ""
            msg = line.strip("\n")
            parts = msg.split(" ", 2)
            if len(parts) >= 2:
                ts = f"{parts[0]} {parts[1]}"
            lvl = _parse_level(line)
            if level_norm in allowed and lvl != level_norm:
                continue
            logs.append({"ts": ts, "level": lvl, "message": msg})
        return {"ok": True, "logs": logs}
    except Exception:
        return {"ok": False, "logs": []}
