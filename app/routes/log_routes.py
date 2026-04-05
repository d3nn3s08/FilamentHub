from typing import Dict, List, TypedDict, Any

from fastapi import APIRouter, Query

from app.routes import debug_routes

router = APIRouter(prefix="/api/logs", tags=["Logs"])

LOG_MODULES = ("app", "mqtt", "errors", "bambu", "services", "database")


class LogEntry(TypedDict, total=False):
    timestamp: str
    level: str
    module: str
    message: str


class LogFetchResult(TypedDict):
    logs: List[LogEntry]
    count: int
    module: str


def _normalize_module(module: str) -> str:
    module_key = (module or "app").lower()
    return module_key if module_key in LOG_MODULES else "app"


def _format_lines(logs: List[LogEntry]) -> List[str]:
    lines: List[str] = []
    for entry in logs:
        ts = entry.get("timestamp", "")
        level = entry.get("level", "")
        module = entry.get("module", "")
        message = entry.get("message", "")
        lines.append(f"{ts} [{level}] {module} - {message}".strip())
    return lines


def _fetch_logs(module: str, limit: int = 200) -> LogFetchResult:
    normalized = _normalize_module(module)
    data: Any = debug_routes.get_logs(module=normalized, limit=limit)
    if not isinstance(data, dict):
        return {"logs": [], "count": 0, "module": normalized}
    logs = data.get("logs", []) or []
    count = int(data.get("count", len(logs))) if isinstance(data, dict) else len(logs)
    return {"logs": logs, "count": count, "module": normalized}


@router.get("/modules")
def get_modules():
    counts: Dict[str, int] = {}
    for module in LOG_MODULES:
        data = _fetch_logs(module=module, limit=200)
        counts[module] = data["count"]
    return {"deprecated": True, "modules": list(LOG_MODULES), "counts": counts, "use": "/api/debug/logs"}


@router.get("/today")
def get_today_log(module: str = Query("app")):
    data = _fetch_logs(module=module, limit=200)
    return {
        "deprecated": True,
        "module": data["module"],
        "count": data["count"],
        "lines": _format_lines(data["logs"]),
        "logs": data["logs"],
        "use": "/api/debug/logs",
    }


@router.get("/date/{date}")
def get_log_by_date(date: str, module: str = Query("app")):
    data = _fetch_logs(module=module, limit=200)
    return {
        "deprecated": True,
        "module": data["module"],
        "date": date,
        "count": data["count"],
        "lines": _format_lines(data["logs"]),
        "logs": data["logs"],
        "use": "/api/debug/logs",
    }


@router.get("/errors/latest")
def latest_error():
    data = _fetch_logs(module="errors", limit=200)
    lines = _format_lines(data["logs"])
    latest = lines[-1] if lines else ""
    return {"deprecated": True, "latest": latest, "use": "/api/debug/logs"}
