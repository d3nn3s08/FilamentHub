import os
from pathlib import Path
from typing import List, Dict, Optional


MODULE_WHITELIST = {"app", "bambu", "klipper", "mqtt", "scanner", "admin"}
LOG_ROOT = Path("logs")
MAX_LIMIT = 1000


class LogAccessError(Exception):
    pass


def resolve_log_path(module: str) -> Path:
    if module not in MODULE_WHITELIST:
        raise ValueError("Invalid module")
    # Prevent any path tricks
    if "/" in module or "\\" in module or ".." in module:
        raise ValueError("Invalid module")
    filename = f"{module}.log"
    return LOG_ROOT / module / filename


def list_modules() -> List[str]:
    return sorted(MODULE_WHITELIST)


def _line_matches(line: str, level: Optional[str], search: Optional[str]) -> bool:
    if level:
        lvl = level.upper()
        if lvl not in line.upper():
            return False
    if search:
        if search.lower() not in line.lower():
            return False
    return True


def read_logs(
    module: str,
    limit: int = 200,
    offset: int = 0,
    level: Optional[str] = None,
    search: Optional[str] = None,
    allow_admin: bool = False,
) -> Dict[str, object]:
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT
    if offset < 0:
        offset = 0
    if module == "admin" and not allow_admin:
        raise LogAccessError("Admin logs require elevated access")
    path = resolve_log_path(module)
    if not path.exists():
        return {"module": module, "items": [], "count": 0}

    matched: List[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not _line_matches(line, level, search):
                    continue
                matched.append(line)
    except FileNotFoundError:
        return {"module": module, "items": [], "count": 0}
    except Exception:
        # Fail safe: do not raise to API level
        return {"module": module, "items": [], "count": 0}

    total = len(matched)
    sliced = matched[offset : offset + limit] if offset < total else []
    return {"module": module, "items": sliced, "count": total}
