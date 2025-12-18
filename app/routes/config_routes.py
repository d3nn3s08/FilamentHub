import json
import logging
from copy import deepcopy
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.settings import Setting


router = APIRouter()
logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "name": "FilamentHub",
    "version": "0.0.0",
    "debug": {
        "system_health": {
            "enabled": True,
            "warn_latency_ms": 600,
            "error_latency_ms": 1200,
        },
        "runtime": {
            "enabled": True,
            "poll_interval_ms": 2000,
        },
    },
    "logging": {
        "level": "basic",
        "file_enabled": False,
    },
    "logging_status": {},
    "scanner": {
        "pro": {
            "deep_probe": False,
            "fingerprint_enabled": False,
        }
    },
    "fingerprint": {
        "enabled": False,
        "ports": [8883, 6000, 7125],
        "timeout_ms": 1500,
    },
    "json_inspector": {
        "max_size_mb": 5,
        "max_depth": 50,
        "allow_override": False,
    },
}


def _merge_dict(defaults: dict, override: dict) -> dict:
    merged = deepcopy(defaults)
    if not isinstance(override, dict):
        return merged
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _to_bool(val, default: bool, key: str):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        v = val.strip().lower()
        if v in TRUE_VALUES:
            return True
        if v in FALSE_VALUES:
            return False
    logger.warning("Config fallback applied for %s", key)
    return default


def _to_int(val, default: int, key: str):
    try:
        return int(val)
    except Exception:
        logger.warning("Config fallback applied for %s", key)
        return default


def _get_ports_from_str(val, default_ports: list[int]) -> list[int]:
    if isinstance(val, list):
        raw = val
    elif isinstance(val, str):
        raw = [p.strip() for p in val.split(",")]
    else:
        raw = []
    ports_valid = []
    for p in raw:
        try:
            port_int = int(p)
            if 1 <= port_int <= 65535:
                ports_valid.append(port_int)
        except Exception:
            continue
    return ports_valid or default_ports


def _persist_setting(session: Session, key: str, value: str, overwrite: bool = False) -> None:
    existing = session.exec(select(Setting).where(Setting.key == key)).first()
    if existing:
        if overwrite:
            existing.value = value
        else:
            return
    else:
        session.add(Setting(key=key, value=value))
    session.commit()


def _ensure_settings_seed(session: Session, merged: dict) -> None:
    runtime = merged.get("debug", {}).get("runtime", {})
    scanner_pro = merged.get("scanner", {}).get("pro", {})
    fp = merged.get("fingerprint", {})
    log_cfg = merged.get("logging", {})
    health_cfg = merged.get("debug", {}).get("system_health", {})
    json_inspector = merged.get("json_inspector", {})
    seeds = {
        "debug.system_health.enabled": "true" if health_cfg.get("enabled", True) else "false",
        "debug.system_health.warn_latency_ms": str(health_cfg.get("warn_latency_ms", 600)),
        "debug.system_health.error_latency_ms": str(health_cfg.get("error_latency_ms", 1200)),
        "debug.runtime.enabled": "true" if runtime.get("enabled", True) else "false",
        "debug.runtime.poll_interval_ms": str(runtime.get("poll_interval_ms", 2000)),
        "scanner.pro.deep_probe": "true" if scanner_pro.get("deep_probe", False) else "false",
        "scanner.pro.fingerprint_enabled": "true" if scanner_pro.get("fingerprint_enabled", False) else "false",
        "fingerprint.enabled": "true" if fp.get("enabled", False) else "false",
        "fingerprint.timeout_ms": str(fp.get("timeout_ms", 1500)),
        "fingerprint.ports": json.dumps(fp.get("ports", DEFAULT_CONFIG["fingerprint"]["ports"])),
        "logging.level": log_cfg.get("level", DEFAULT_CONFIG["logging"]["level"]),
        "logging.file_enabled": "true" if log_cfg.get("file_enabled", False) else "false",
        "json_inspector.max_size_mb": str(json_inspector.get("max_size_mb", DEFAULT_CONFIG["json_inspector"]["max_size_mb"])),
        "json_inspector.max_depth": str(json_inspector.get("max_depth", DEFAULT_CONFIG["json_inspector"]["max_depth"])),
        "json_inspector.allow_override": "true" if json_inspector.get("allow_override", False) else "false",
    }
    for k, v in seeds.items():
        _persist_setting(session, k, v, overwrite=False)


def _validate_config(raw: dict) -> dict:
    cfg = _merge_dict(DEFAULT_CONFIG, raw if isinstance(raw, dict) else {})

    # System Health
    sh = cfg.get("debug", {}).get("system_health", {})
    enabled = _to_bool(sh.get("enabled"), DEFAULT_CONFIG["debug"]["system_health"]["enabled"], "debug.system_health.enabled")
    warn_latency = _to_int(sh.get("warn_latency_ms"), DEFAULT_CONFIG["debug"]["system_health"]["warn_latency_ms"], "debug.system_health.warn_latency_ms")
    if warn_latency < 100:
        logger.warning("Config fallback applied for debug.system_health.warn_latency_ms")
        warn_latency = DEFAULT_CONFIG["debug"]["system_health"]["warn_latency_ms"]
    error_latency = _to_int(
        sh.get("error_latency_ms"),
        DEFAULT_CONFIG["debug"]["system_health"]["error_latency_ms"],
        "debug.system_health.error_latency_ms",
    )
    min_error = max(warn_latency + 100, DEFAULT_CONFIG["debug"]["system_health"]["error_latency_ms"])
    if error_latency <= warn_latency:
        logger.warning("Config fallback applied for debug.system_health.error_latency_ms")
        error_latency = min_error
    cfg["debug"]["system_health"] = {
        "enabled": enabled,
        "warn_latency_ms": warn_latency,
        "error_latency_ms": error_latency,
    }

    # Logging
    log_cfg = cfg.get("logging", {})
    level_raw = (log_cfg.get("level") or "").lower()
    if level_raw not in {"off", "basic", "verbose"}:
        logger.warning("Config fallback applied for logging.level")
        level_raw = DEFAULT_CONFIG["logging"]["level"]
    file_enabled = _to_bool(log_cfg.get("file_enabled"), DEFAULT_CONFIG["logging"]["file_enabled"], "logging.file_enabled")
    cfg["logging"] = {"level": level_raw, "file_enabled": file_enabled}
    cfg["logging_status"] = {}

    # Runtime
    rt = cfg.get("debug", {}).get("runtime", {})
    runtime_enabled = _to_bool(rt.get("enabled"), DEFAULT_CONFIG["debug"]["runtime"]["enabled"], "debug.runtime.enabled")
    poll_interval = _to_int(rt.get("poll_interval_ms"), DEFAULT_CONFIG["debug"]["runtime"]["poll_interval_ms"], "debug.runtime.poll_interval_ms")
    if poll_interval < 500:
        logger.warning("Config fallback applied for debug.runtime.poll_interval_ms")
        poll_interval = DEFAULT_CONFIG["debug"]["runtime"]["poll_interval_ms"]
    cfg["debug"]["runtime"] = {
        "enabled": runtime_enabled,
        "poll_interval_ms": poll_interval,
    }

    # Scanner Pro
    scanner_pro = cfg.get("scanner", {}).get("pro", {})
    deep_probe = _to_bool(scanner_pro.get("deep_probe"), DEFAULT_CONFIG["scanner"]["pro"]["deep_probe"], "scanner.pro.deep_probe")
    fingerprint_enabled = _to_bool(
        scanner_pro.get("fingerprint_enabled"),
        DEFAULT_CONFIG["scanner"]["pro"]["fingerprint_enabled"],
        "scanner.pro.fingerprint_enabled",
    )
    cfg["scanner"]["pro"] = {
        "deep_probe": deep_probe,
        "fingerprint_enabled": fingerprint_enabled,
    }

    # Fingerprint intern
    fp_cfg = cfg.get("fingerprint", {})
    fp_enabled = _to_bool(fp_cfg.get("enabled"), DEFAULT_CONFIG["fingerprint"]["enabled"], "fingerprint.enabled")
    ports_raw = fp_cfg.get("ports")
    default_ports = DEFAULT_CONFIG["fingerprint"]["ports"]
    ports_valid = []
    if isinstance(ports_raw, list):
        for p in ports_raw:
            try:
                port_int = int(p)
                if 1 <= port_int <= 65535:
                    ports_valid.append(port_int)
            except Exception:
                continue
    if not ports_valid:
        logger.warning("Config fallback applied for fingerprint.ports")
        ports_valid = default_ports
    timeout_ms = _to_int(fp_cfg.get("timeout_ms"), DEFAULT_CONFIG["fingerprint"]["timeout_ms"], "fingerprint.timeout_ms")
    if timeout_ms < 500:
        logger.warning("Config fallback applied for fingerprint.timeout_ms")
        timeout_ms = DEFAULT_CONFIG["fingerprint"]["timeout_ms"]
    cfg["fingerprint"] = {
        "enabled": fp_enabled,
        "ports": ports_valid,
        "timeout_ms": timeout_ms,
    }

    # JSON Inspector
    json_cfg = cfg.get("json_inspector", {})
    max_size_mb = _to_int(json_cfg.get("max_size_mb"), DEFAULT_CONFIG["json_inspector"]["max_size_mb"], "json_inspector.max_size_mb")
    if max_size_mb < 1 or max_size_mb > 100:
        logger.warning("Config fallback applied for json_inspector.max_size_mb")
        max_size_mb = DEFAULT_CONFIG["json_inspector"]["max_size_mb"]
    max_depth = _to_int(json_cfg.get("max_depth"), DEFAULT_CONFIG["json_inspector"]["max_depth"], "json_inspector.max_depth")
    if max_depth < 1 or max_depth > 500:
        logger.warning("Config fallback applied for json_inspector.max_depth")
        max_depth = DEFAULT_CONFIG["json_inspector"]["max_depth"]
    allow_override = _to_bool(json_cfg.get("allow_override"), DEFAULT_CONFIG["json_inspector"]["allow_override"], "json_inspector.allow_override")
    cfg["json_inspector"] = {
        "max_size_mb": max_size_mb,
        "max_depth": max_depth,
        "allow_override": allow_override,
    }

    # Derived block for UI (back-compat, read-only)
    cfg["config_manager"] = {
        "health_enabled": cfg["debug"]["system_health"]["enabled"],
        "health_latency_warn_ms": cfg["debug"]["system_health"]["warn_latency_ms"],
        "health_latency_error_ms": cfg["debug"]["system_health"]["error_latency_ms"],
        "log_level": cfg["logging"]["level"],
        "log_to_file": cfg["logging"]["file_enabled"],
        "runtime_enabled": cfg["debug"]["runtime"]["enabled"],
        "runtime_poll_interval_ms": cfg["debug"]["runtime"]["poll_interval_ms"],
        "scanner_deep_probe": cfg["scanner"]["pro"]["deep_probe"],
        "scanner_fingerprint": cfg["scanner"]["pro"]["fingerprint_enabled"],
    }

    return cfg


def _settings_map(session: Session) -> dict:
    data = {}
    for row in session.exec(select(Setting)).all():
        data[row.key] = row.value
    return data


def _load_config(session: Session | None = None) -> dict:
    config_path = Path(__file__).resolve().parents[2] / "config.json"
    if not config_path.exists():
        return deepcopy(DEFAULT_CONFIG)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        merged = _validate_config(data)
        if session:
            settings = _settings_map(session)
            # Overlay runtime settings from DB if present
            runtime_enabled = _to_bool(
                settings.get("debug.runtime.enabled"),
                merged["debug"]["runtime"]["enabled"],
                "debug.runtime.enabled",
            )
            runtime_poll = _to_int(
                settings.get("debug.runtime.poll_interval_ms"),
                merged["debug"]["runtime"]["poll_interval_ms"],
                "debug.runtime.poll_interval_ms",
            )
            if runtime_poll < 500:
                runtime_poll = DEFAULT_CONFIG["debug"]["runtime"]["poll_interval_ms"]
            merged["debug"]["runtime"] = {"enabled": runtime_enabled, "poll_interval_ms": runtime_poll}

            # System health overlay
            health_enabled = _to_bool(
                settings.get("debug.system_health.enabled"),
                merged["debug"]["system_health"]["enabled"],
                "debug.system_health.enabled",
            )
            warn_latency = _to_int(
                settings.get("debug.system_health.warn_latency_ms"),
                merged["debug"]["system_health"]["warn_latency_ms"],
                "debug.system_health.warn_latency_ms",
            )
            if warn_latency < 100:
                warn_latency = merged["debug"]["system_health"]["warn_latency_ms"]
            error_latency = _to_int(
                settings.get("debug.system_health.error_latency_ms"),
                merged["debug"]["system_health"]["error_latency_ms"],
                "debug.system_health.error_latency_ms",
            )
            min_error = max(warn_latency + 100, DEFAULT_CONFIG["debug"]["system_health"]["error_latency_ms"])
            if error_latency <= warn_latency:
                error_latency = min_error
            merged["debug"]["system_health"] = {
                "enabled": health_enabled,
                "warn_latency_ms": warn_latency,
                "error_latency_ms": error_latency,
            }

            deep_probe = _to_bool(
                settings.get("scanner.pro.deep_probe"), merged["scanner"]["pro"]["deep_probe"], "scanner.pro.deep_probe"
            )
            fp_enabled = _to_bool(
                settings.get("scanner.pro.fingerprint_enabled"),
                merged["scanner"]["pro"]["fingerprint_enabled"],
                "scanner.pro.fingerprint_enabled",
            )
            merged["scanner"]["pro"] = {"deep_probe": deep_probe, "fingerprint_enabled": fp_enabled}

            fp_enabled_setting = _to_bool(
                settings.get("fingerprint.enabled"), merged["fingerprint"]["enabled"], "fingerprint.enabled"
            )
            fp_ports = _get_ports_from_str(settings.get("fingerprint.ports"), merged["fingerprint"]["ports"])
            fp_timeout = _to_int(
                settings.get("fingerprint.timeout_ms"), merged["fingerprint"]["timeout_ms"], "fingerprint.timeout_ms"
            )
            if fp_timeout < 500:
                fp_timeout = merged["fingerprint"]["timeout_ms"]
            merged["fingerprint"] = {"enabled": fp_enabled_setting, "ports": fp_ports, "timeout_ms": fp_timeout}

            # Logging overlay
            level_setting = (settings.get("logging.level") or "").lower()
            if level_setting in {"off", "basic", "verbose"}:
                merged["logging"]["level"] = level_setting
            file_setting_raw = settings.get("logging.file_enabled")
            if file_setting_raw is not None:
                merged["logging"]["file_enabled"] = _to_bool(
                    file_setting_raw, merged["logging"]["file_enabled"], "logging.file_enabled"
                )

            # JSON Inspector overlay
            json_max_size = _to_int(
                settings.get("json_inspector.max_size_mb"),
                merged["json_inspector"]["max_size_mb"],
                "json_inspector.max_size_mb"
            )
            if json_max_size < 1 or json_max_size > 100:
                json_max_size = merged["json_inspector"]["max_size_mb"]
            json_max_depth = _to_int(
                settings.get("json_inspector.max_depth"),
                merged["json_inspector"]["max_depth"],
                "json_inspector.max_depth"
            )
            if json_max_depth < 1 or json_max_depth > 500:
                json_max_depth = merged["json_inspector"]["max_depth"]
            json_allow_override = _to_bool(
                settings.get("json_inspector.allow_override"),
                merged["json_inspector"]["allow_override"],
                "json_inspector.allow_override"
            )
            merged["json_inspector"] = {
                "max_size_mb": json_max_size,
                "max_depth": json_max_depth,
                "allow_override": json_allow_override,
            }

            merged["config_manager"] = {
                "health_enabled": merged["debug"]["system_health"]["enabled"],
                "health_latency_warn_ms": merged["debug"]["system_health"]["warn_latency_ms"],
                "health_latency_error_ms": merged["debug"]["system_health"]["error_latency_ms"],
                "log_level": merged["logging"]["level"],
                "log_to_file": merged["logging"]["file_enabled"],
                "runtime_enabled": merged["debug"]["runtime"]["enabled"],
                "runtime_poll_interval_ms": merged["debug"]["runtime"]["poll_interval_ms"],
                "scanner_deep_probe": merged["scanner"]["pro"]["deep_probe"],
                "scanner_fingerprint": merged["scanner"]["pro"]["fingerprint_enabled"],
            }
            _ensure_settings_seed(session, merged)
        return merged
    except Exception:
        logger.warning("Config fallback applied for config.json")
        return deepcopy(DEFAULT_CONFIG)


@router.get("/api/config/current")
async def get_current_config(session: Session = Depends(get_session)):
    """
    Read-only config export for the Config Manager (Pro).
    """
    return _load_config(session)


# GET alias for /api/config (same payload as /current)
@router.get("/api/config")
async def get_config_alias(session: Session = Depends(get_session)):
    return await get_current_config(session)


def _validate_payload(payload: dict) -> dict:
    data = payload or {}
    out = {}
    if "logging" in data and isinstance(data.get("logging"), dict):
        data = {
            **data,
            "logging.level": data["logging"].get("level"),
            "logging.file_enabled": data["logging"].get("file_enabled"),
        }
    if "debug.system_health" in data and isinstance(data.get("debug.system_health"), dict):
        data = {
            **data,
            "debug.system_health.enabled": data["debug.system_health"].get("enabled"),
            "debug.system_health.warn_latency_ms": data["debug.system_health"].get("warn_latency_ms"),
            "debug.system_health.error_latency_ms": data["debug.system_health"].get("error_latency_ms"),
        }
    if "debug.system_health.enabled" in data:
        out["debug.system_health.enabled"] = _to_bool(data.get("debug.system_health.enabled"), True, "debug.system_health.enabled")
    if "debug.system_health.warn_latency_ms" in data:
        warn = _to_int(data.get("debug.system_health.warn_latency_ms"), 600, "debug.system_health.warn_latency_ms")
        if warn < 100:
            warn = 600
        out["debug.system_health.warn_latency_ms"] = warn
    if "debug.system_health.error_latency_ms" in data:
        err = _to_int(data.get("debug.system_health.error_latency_ms"), 1200, "debug.system_health.error_latency_ms")
        warn = out.get("debug.system_health.warn_latency_ms", 600)
        min_err = max(warn + 100, 1200)
        if err <= warn:
            err = min_err
        out["debug.system_health.error_latency_ms"] = err

    if "logging.level" in data:
        level_raw = (data.get("logging.level") or "").lower()
        out["logging.level"] = level_raw if level_raw in {"off", "basic", "verbose"} else DEFAULT_CONFIG["logging"]["level"]
    if "logging.file_enabled" in data:
        out["logging.file_enabled"] = _to_bool(data.get("logging.file_enabled"), False, "logging.file_enabled")

    if "debug.runtime.enabled" in data:
        out["debug.runtime.enabled"] = _to_bool(data.get("debug.runtime.enabled"), True, "debug.runtime.enabled")
    if "debug.runtime.poll_interval_ms" in data:
        poll = _to_int(data.get("debug.runtime.poll_interval_ms"), 2000, "debug.runtime.poll_interval_ms")
        if poll < 500:
            poll = 2000
        out["debug.runtime.poll_interval_ms"] = poll

    if "scanner.pro.deep_probe" in data:
        out["scanner.pro.deep_probe"] = _to_bool(data.get("scanner.pro.deep_probe"), False, "scanner.pro.deep_probe")
    if "scanner.pro.fingerprint_enabled" in data:
        out["scanner.pro.fingerprint_enabled"] = _to_bool(
            data.get("scanner.pro.fingerprint_enabled"), False, "scanner.pro.fingerprint_enabled"
        )

    if "fingerprint.enabled" in data:
        out["fingerprint.enabled"] = _to_bool(data.get("fingerprint.enabled"), False, "fingerprint.enabled")
    if "fingerprint.timeout_ms" in data:
        to_val = _to_int(data.get("fingerprint.timeout_ms"), 1500, "fingerprint.timeout_ms")
        if to_val < 500:
            to_val = 1500
        out["fingerprint.timeout_ms"] = to_val
    if "fingerprint.ports" in data:
        ports_val = data.get("fingerprint.ports")
        ports = []
        if isinstance(ports_val, list):
            ports = [int(p) for p in ports_val if isinstance(p, (int, float)) and 1 <= int(p) <= 65535]
        else:
            try:
                ports = [int(x.strip()) for x in str(ports_val).split(",") if x.strip()]
            except Exception:
                ports = []
        ports = [p for p in ports if 1 <= p <= 65535]
        if not ports:
            ports = DEFAULT_CONFIG["fingerprint"]["ports"]
        out["fingerprint.ports"] = ports

    if "json_inspector.max_size_mb" in data:
        size_val = _to_int(data.get("json_inspector.max_size_mb"), DEFAULT_CONFIG["json_inspector"]["max_size_mb"], "json_inspector.max_size_mb")
        if size_val < 1 or size_val > 100:
            size_val = DEFAULT_CONFIG["json_inspector"]["max_size_mb"]
        out["json_inspector.max_size_mb"] = size_val
    if "json_inspector.max_depth" in data:
        depth_val = _to_int(data.get("json_inspector.max_depth"), DEFAULT_CONFIG["json_inspector"]["max_depth"], "json_inspector.max_depth")
        if depth_val < 1 or depth_val > 500:
            depth_val = DEFAULT_CONFIG["json_inspector"]["max_depth"]
        out["json_inspector.max_depth"] = depth_val
    if "json_inspector.allow_override" in data:
        out["json_inspector.allow_override"] = _to_bool(data.get("json_inspector.allow_override"), False, "json_inspector.allow_override")

    return out


def _persist_payload(session: Session, validated: dict) -> None:
    for key, val in validated.items():
        if isinstance(val, list):
            _persist_setting(session, key, json.dumps(val), overwrite=True)
        elif isinstance(val, bool):
            _persist_setting(session, key, "true" if val else "false", overwrite=True)
        else:
            _persist_setting(session, key, str(val), overwrite=True)


def _level_to_logging(level_str: str) -> int:
    lvl = (level_str or "").lower()
    if lvl == "off":
        return logging.CRITICAL + 10
    if lvl == "verbose":
        return logging.DEBUG
    return logging.INFO


def _apply_logging_settings(merged: dict) -> dict:
    log_cfg = merged.get("logging", {})
    base_level = _level_to_logging(log_cfg.get("level"))
    file_enabled = log_cfg.get("file_enabled", False)

    module_levels = {
        "": base_level,  # root/app
        "bambu": base_level,
        "klipper": base_level,
        "mqtt": base_level,
    }
    statuses = {}
    for name, lvl in module_levels.items():
        logger_obj = logging.getLogger(name)
        logger_obj.setLevel(lvl)
        statuses[name or "app"] = lvl < (logging.CRITICAL + 10)
        # File handler toggle: if disabled, remove file handlers
        if not file_enabled:
            for h in list(logger_obj.handlers):
                if isinstance(h, logging.FileHandler):
                    logger_obj.removeHandler(h)
        # if enabled, keep existing handlers; no new file handler auto-added
    merged["logging_status"] = statuses
    return statuses


@router.put("/api/config")
async def update_config(payload: dict, session: Session = Depends(get_session)):
    validated = _validate_payload(payload)
    if not validated:
        raise HTTPException(status_code=400, detail="No valid keys provided")
    _persist_payload(session, validated)
    merged = _load_config(session)
    _apply_logging_settings(merged)
    return merged


# alias for trailing slash
@router.put("/api/config/")
async def update_config_alias(payload: dict, session: Session = Depends(get_session)):
    return await update_config(payload, session)
