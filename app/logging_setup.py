import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
LOGGERS = ("app", "mqtt", "bambu", "services", "database", "errors")


def _get_level(level_str: str) -> int:
    level = (level_str or "").upper()
    return getattr(logging, level, logging.INFO)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _build_handler(path: Path, level: int, max_size_mb: int, backup_count: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler._fh_managed = True
    return handler


def _clear_managed_handlers(logger: logging.Logger) -> None:
    keep = []
    for handler in list(logger.handlers):
        if getattr(handler, "_fh_managed", False):
            try:
                handler.close()
            except Exception:
                logging.getLogger("errors").exception("Failed to close managed log handler")
        else:
            keep.append(handler)
    logger.handlers = keep


def configure_logging(logging_config: Dict) -> Dict[str, bool]:
    enabled = bool(logging_config.get("enabled", True))
    level = _get_level(logging_config.get("level", "INFO"))
    max_size_mb = max(1, int(logging_config.get("max_size_mb", 10)))
    backup_count = max(1, int(logging_config.get("backup_count", 3)))
    modules_cfg = logging_config.get("modules", {})

    logs_root = Path(logging_config.get("paths", {}).get("logs", "logs"))
    app_log = logs_root / "app" / "app.log"
    mqtt_log = logs_root / "mqtt" / "mqtt.log"
    errors_log = logs_root / "errors" / "errors.log"

    _ensure_dir(app_log.parent)
    _ensure_dir(mqtt_log.parent)
    _ensure_dir(errors_log.parent)

    root_logger = logging.getLogger()
    _clear_managed_handlers(root_logger)
    root_logger.setLevel(level if enabled else logging.CRITICAL + 10)

    statuses: Dict[str, bool] = {}
    for logger_name in LOGGERS:
        module_enabled = bool(modules_cfg.get(logger_name, {}).get("enabled", True))
        final_enabled = enabled and module_enabled
        logger_obj = logging.getLogger(logger_name)
        _clear_managed_handlers(logger_obj)
        logger_obj.disabled = not final_enabled
        logger_obj.setLevel(level if final_enabled else logging.CRITICAL + 10)
        logger_obj.propagate = True
        statuses[logger_name] = final_enabled

    if enabled:
        app_handler = _build_handler(app_log, level, max_size_mb, backup_count)
        mqtt_handler = _build_handler(mqtt_log, level, max_size_mb, backup_count)
        errors_handler = _build_handler(errors_log, logging.ERROR, max_size_mb, backup_count)
        logging.getLogger("app").addHandler(app_handler)
        logging.getLogger("bambu").addHandler(app_handler)
        logging.getLogger("services").addHandler(app_handler)
        logging.getLogger("database").addHandler(app_handler)
        logging.getLogger("mqtt").addHandler(mqtt_handler)
        root_logger.addHandler(errors_handler)

    return statuses
