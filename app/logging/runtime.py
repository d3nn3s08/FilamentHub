import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Tuple

LOG_DIR = Path("logs/app")
LOG_FILE = LOG_DIR / "app.log"
MANAGED_LOGGERS = ["", "uvicorn.error", "uvicorn"]
MODULES = ["app", "bambu", "errors", "klipper", "mqtt"]
_CURRENT_HANDLERS: Dict[str, RotatingFileHandler] = {}
LOG_FORMATTER = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")


def _get_level(level_str: str) -> int:
    lvl = (level_str or "").upper()
    if lvl in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        return getattr(logging, lvl)
    return logging.INFO


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_old_logs(keep_days: int) -> None:
    if keep_days <= 0:
        return
    cutoff = time.time() - keep_days * 86400
    pattern = LOG_DIR.glob("app.log.*")
    for file_path in pattern:
        try:
            if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                file_path.unlink()
        except Exception:
            pass


def _clear_handlers() -> None:
    for logger_name, handler in list(_CURRENT_HANDLERS.items()):
        logger_obj = logging.getLogger(logger_name)
        if handler in logger_obj.handlers:
            logger_obj.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    _CURRENT_HANDLERS.clear()


def _build_handler(level: int, max_size_mb: int, backup_count: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(LOG_FORMATTER)
    return handler


def _install_handlers(level: int, max_size_mb: int, backup_count: int) -> None:
    _ensure_log_dir()
    for logger_name in MANAGED_LOGGERS:
        handler = _build_handler(level, max_size_mb, backup_count)
        logger_obj = logging.getLogger(logger_name)
        logger_obj.addHandler(handler)
        _CURRENT_HANDLERS[logger_name] = handler


def _configure_modules(level: int, logging_enabled: bool, modules_cfg: dict) -> Dict[str, bool]:
    statuses: Dict[str, bool] = {}
    for module_name in MODULES:
        module_entry = modules_cfg.get(module_name, {})
        module_enabled = bool(module_entry.get("enabled", False))
        final_enabled = logging_enabled and module_enabled
        module_logger = logging.getLogger(module_name)
        module_logger.disabled = not final_enabled
        module_logger.setLevel(level if final_enabled else logging.CRITICAL + 10)
        statuses[module_name] = final_enabled
    return statuses


def reconfigure_logging(logging_config: dict) -> Dict[str, bool]:
    enabled = bool(logging_config.get("enabled", True))
    level = _get_level(logging_config.get("level", "INFO"))
    max_size_mb = max(1, int(logging_config.get("max_size_mb", 10)))
    backup_count = max(1, int(logging_config.get("backup_count", 3)))
    keep_days = int(logging_config.get("keep_days", 0))
    modules_cfg = logging_config.get("modules", {})

    _clear_handlers()
    if enabled:
        _install_handlers(level, max_size_mb, backup_count)
        _cleanup_old_logs(keep_days)

    root_logger = logging.getLogger()
    root_logger.setLevel(level if enabled else logging.CRITICAL + 10)
    for logger_name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(logger_name).setLevel(level if enabled else logging.CRITICAL + 10)

    statuses = _configure_modules(level, enabled, modules_cfg)
    statuses["app"] = enabled
    return statuses
