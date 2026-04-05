from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models.settings import Setting
from app.routes.admin_routes import admin_required
import json
from pathlib import Path
import logging

router = APIRouter()
logger = logging.getLogger("app")


DEFAULTS = {
    "ams_mode": "single",
    "debug_ws_logging": "false",
    "debug_center_mode": "lite",
    "debug_center_pro_unlocked": "false",
    "cost.electricity_price_kwh": "0.30",
    "language": "de",
    "bambu_username": "",
    "bambu_password": "",
    "bambu_region": "global",
    "experimental_mode": "false",
    # AMS conflict detection defaults
    "ams_conflict_detection_enabled": "false",
    "ams_conflict_tolerance_g": "5",
    # AMS Spulen-Verwaltung
    "ams_spool_auto_create": "true",  # true = still anlegen (wie bisher), false = immer Dialog
    # Experimental tab defaults
    "enable_3mf_title_matching": "true",
    "3mf_score_threshold": "60",
    "enable_file_selection_dialog": "false",
    "enable_multi_color_tracking": "true",
    "enable_ftp_gcode_download": "true",
}
PRO_CONFIG_DEFAULTS = {
    "debug.config.debug_logging_enabled": "false",
    "debug.config.latency_warning_threshold_ms": "600",
    "debug.config.scanner_probe_timeout_ms": "800",
    "debug.config.scanner_allow_duplicates": "false",
    "debug.config.websocket_debug_level": "basic",
}
TRUE_VALUES = {"1", "true", "yes", "on"}
WEBSOCKET_DEBUG_LEVELS = {"off", "basic", "verbose"}
MIN_LATENCY_WARNING_MS = 100
MIN_SCANNER_PROBE_TIMEOUT_MS = 200


def get_setting(session: Session, key: str, default: str | None = None) -> str | None:
    setting = session.exec(select(Setting).where(Setting.key == key)).first()
    if setting:
        return setting.value
    if default is not None:
        setting = Setting(key=key, value=default)
        session.add(setting)
        session.commit()
        session.refresh(setting)
        return setting.value
    return None


def set_setting(session: Session, key: str, value: str) -> None:
    setting = session.exec(select(Setting).where(Setting.key == key)).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        session.add(setting)
    session.commit()


def _normalize_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).lower() in TRUE_VALUES


def _normalize_int(value: str | None, default: int, minimum: int | None = None) -> int:
    try:
        normalized = int(str(value))
    except (TypeError, ValueError):
        logger.exception("Invalid int value for settings: %s", value)
        return default
    if minimum is not None and normalized < minimum:
        return default
    return normalized


def _normalize_float(value: str | None, default: float, minimum: float | None = None) -> float:
    try:
        normalized = float(str(value))
    except (TypeError, ValueError):
        logger.exception("Invalid float value for settings: %s", value)
        return default
    if minimum is not None and normalized < minimum:
        return default
    return normalized


def _normalize_enum(value: str | None, allowed: set[str], default: str) -> str:
    if value is None:
        return default
    normalized = str(value).lower()
    return normalized if normalized in allowed else default


def _load_config_defaults() -> dict:
    config_path = Path(__file__).resolve().parents[2] / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load config defaults from %s", config_path)
        return {}


def _ensure_runtime_settings(session: Session) -> None:
    defaults = _load_config_defaults()
    debug_defaults = defaults.get("debug", {})
    runtime_defaults = debug_defaults.get("runtime", {})
    scanner_defaults = defaults.get("scanner", {}).get("pro", {})
    fingerprint_defaults = defaults.get("fingerprint", {})

    to_init = {
        "debug.runtime.enabled": str(runtime_defaults.get("enabled", True)).lower(),
        "debug.runtime.poll_interval_ms": str(runtime_defaults.get("poll_interval_ms", 2000)),
        "scanner.pro.deep_probe": str(scanner_defaults.get("deep_probe", False)).lower(),
        "scanner.pro.fingerprint_enabled": str(scanner_defaults.get("fingerprint_enabled", False)).lower(),
        "fingerprint.enabled": str(fingerprint_defaults.get("enabled", False)).lower(),
        "fingerprint.timeout_ms": str(fingerprint_defaults.get("timeout_ms", 1500)),
        "cost.electricity_price_kwh": DEFAULTS["cost.electricity_price_kwh"],
    }
    ports_default = fingerprint_defaults.get("ports", [8883, 6000, 7125])
    if not isinstance(ports_default, list):
        ports_default = [8883, 6000, 7125]
    to_init["fingerprint.ports"] = json.dumps(ports_default)

    for key, value in to_init.items():
        if session.exec(select(Setting).where(Setting.key == key)).first():
            continue
        set_setting(session, key, value)


@router.get("/api/settings")
def get_settings(_: None = Depends(admin_required), session: Session = Depends(get_session)):
    _ensure_runtime_settings(session)
    ams_mode = get_setting(session, "ams_mode", DEFAULTS["ams_mode"]) or DEFAULTS["ams_mode"]
    debug_ws_logging = get_setting(session, "debug_ws_logging", DEFAULTS["debug_ws_logging"]) or DEFAULTS["debug_ws_logging"]
    debug_center_mode = get_setting(session, "debug_center_mode", DEFAULTS["debug_center_mode"]) or DEFAULTS["debug_center_mode"]
    pro_unlocked = get_setting(session, "debug_center_pro_unlocked", DEFAULTS["debug_center_pro_unlocked"]) or DEFAULTS["debug_center_pro_unlocked"]
    electricity_price = get_setting(session, "cost.electricity_price_kwh", DEFAULTS["cost.electricity_price_kwh"]) or DEFAULTS["cost.electricity_price_kwh"]
    debug_logging_enabled = get_setting(session, "debug.config.debug_logging_enabled", PRO_CONFIG_DEFAULTS["debug.config.debug_logging_enabled"]) or PRO_CONFIG_DEFAULTS["debug.config.debug_logging_enabled"]
    latency_warning_threshold = get_setting(session, "debug.config.latency_warning_threshold_ms", PRO_CONFIG_DEFAULTS["debug.config.latency_warning_threshold_ms"]) or PRO_CONFIG_DEFAULTS["debug.config.latency_warning_threshold_ms"]
    scanner_probe_timeout = get_setting(session, "debug.config.scanner_probe_timeout_ms", PRO_CONFIG_DEFAULTS["debug.config.scanner_probe_timeout_ms"]) or PRO_CONFIG_DEFAULTS["debug.config.scanner_probe_timeout_ms"]
    scanner_allow_duplicates = get_setting(session, "debug.config.scanner_allow_duplicates", PRO_CONFIG_DEFAULTS["debug.config.scanner_allow_duplicates"]) or PRO_CONFIG_DEFAULTS["debug.config.scanner_allow_duplicates"]
    websocket_debug_level = get_setting(session, "debug.config.websocket_debug_level", PRO_CONFIG_DEFAULTS["debug.config.websocket_debug_level"]) or PRO_CONFIG_DEFAULTS["debug.config.websocket_debug_level"]
    language = get_setting(session, "language", DEFAULTS["language"]) or DEFAULTS["language"]
    bambu_username = get_setting(session, "bambu_username", DEFAULTS["bambu_username"]) or DEFAULTS["bambu_username"]
    bambu_password = get_setting(session, "bambu_password", DEFAULTS["bambu_password"]) or DEFAULTS["bambu_password"]
    bambu_region = get_setting(session, "bambu_region", DEFAULTS["bambu_region"]) or DEFAULTS["bambu_region"]
    experimental_mode = get_setting(session, "experimental_mode", DEFAULTS["experimental_mode"]) or DEFAULTS["experimental_mode"]
    ams_conflict_enabled = get_setting(session, "ams_conflict_detection_enabled", DEFAULTS["ams_conflict_detection_enabled"]) or DEFAULTS["ams_conflict_detection_enabled"]
    ams_conflict_tolerance = get_setting(session, "ams_conflict_tolerance_g", DEFAULTS["ams_conflict_tolerance_g"]) or DEFAULTS["ams_conflict_tolerance_g"]
    # Experimental tab values
    enable_3mf_title_matching = get_setting(session, "enable_3mf_title_matching", DEFAULTS["enable_3mf_title_matching"]) or DEFAULTS["enable_3mf_title_matching"]
    three_mf_score_threshold = get_setting(session, "3mf_score_threshold", DEFAULTS["3mf_score_threshold"]) or DEFAULTS["3mf_score_threshold"]
    enable_file_selection_dialog = get_setting(session, "enable_file_selection_dialog", DEFAULTS["enable_file_selection_dialog"]) or DEFAULTS["enable_file_selection_dialog"]
    enable_multi_color_tracking = get_setting(session, "enable_multi_color_tracking", DEFAULTS["enable_multi_color_tracking"]) or DEFAULTS["enable_multi_color_tracking"]
    enable_ftp_gcode_download = get_setting(session, "enable_ftp_gcode_download", DEFAULTS["enable_ftp_gcode_download"]) or DEFAULTS["enable_ftp_gcode_download"]
    return {
        "ams_mode": ams_mode if ams_mode in {"single", "multi"} else DEFAULTS["ams_mode"],
        "debug_ws_logging": _normalize_bool(debug_ws_logging, default=False),
        "debug_center_mode": debug_center_mode if debug_center_mode in {"lite", "pro"} else DEFAULTS["debug_center_mode"],
        "debug_center_pro_unlocked": _normalize_bool(pro_unlocked, default=False),
        "cost.electricity_price_kwh": _normalize_float(electricity_price, default=float(DEFAULTS["cost.electricity_price_kwh"]), minimum=0.0),
        "language": language if language in {"de", "en"} else DEFAULTS["language"],
        "bambu_username": bambu_username or "",
        "bambu_password": "***" if bambu_password else "",  # never expose plaintext
        "bambu_region": bambu_region if bambu_region in {"global", "china"} else DEFAULTS["bambu_region"],
        "experimental_mode": _normalize_bool(experimental_mode, default=False),
        "ams_conflict_detection_enabled": _normalize_bool(ams_conflict_enabled, default=True),
        "ams_conflict_tolerance_g": _normalize_int(ams_conflict_tolerance, default=int(DEFAULTS["ams_conflict_tolerance_g"]), minimum=0),
        # Experimental tab return values
        "enable_3mf_title_matching": _normalize_bool(enable_3mf_title_matching, default=True),
        "3mf_score_threshold": _normalize_int(three_mf_score_threshold, default=int(DEFAULTS["3mf_score_threshold"]), minimum=0),
        "enable_file_selection_dialog": _normalize_bool(enable_file_selection_dialog, default=False),
        "enable_multi_color_tracking": _normalize_bool(enable_multi_color_tracking, default=True),
        "enable_ftp_gcode_download": _normalize_bool(enable_ftp_gcode_download, default=True),
        "debug.config.debug_logging_enabled": _normalize_bool(debug_logging_enabled, default=False),
        "debug.config.latency_warning_threshold_ms": _normalize_int(
            latency_warning_threshold,
            default=int(PRO_CONFIG_DEFAULTS["debug.config.latency_warning_threshold_ms"]),
            minimum=MIN_LATENCY_WARNING_MS,
        ),
        "debug.config.scanner_probe_timeout_ms": _normalize_int(
            scanner_probe_timeout,
            default=int(PRO_CONFIG_DEFAULTS["debug.config.scanner_probe_timeout_ms"]),
            minimum=MIN_SCANNER_PROBE_TIMEOUT_MS,
        ),
        "debug.config.scanner_allow_duplicates": _normalize_bool(scanner_allow_duplicates, default=False),
        "debug.config.websocket_debug_level": _normalize_enum(
            websocket_debug_level, WEBSOCKET_DEBUG_LEVELS, PRO_CONFIG_DEFAULTS["debug.config.websocket_debug_level"]
        ),
    }


@router.put("/api/settings")
async def update_settings(payload: dict, _: None = Depends(admin_required), session: Session = Depends(get_session)):
    _ensure_runtime_settings(session)
    allowed_keys = {
        "ams_mode",
        "debug_ws_logging",
        "debug_center_mode",
        "debug_center_pro_unlocked",
        "cost.electricity_price_kwh",
        "language",
        "bambu_username",
        "bambu_password",
        "bambu_region",
        "experimental_mode",
        "debug.config.debug_logging_enabled",
        "debug.config.latency_warning_threshold_ms",
        "debug.config.scanner_probe_timeout_ms",
        "debug.config.scanner_allow_duplicates",
        "debug.config.websocket_debug_level",
        "ams_conflict_detection_enabled",
        "ams_conflict_tolerance_g",
        # Experimental tab keys
        "enable_3mf_title_matching",
        "3mf_score_threshold",
        "enable_file_selection_dialog",
        "enable_multi_color_tracking",
        "enable_ftp_gcode_download",
    }
    if not any(k in payload for k in allowed_keys):
        raise HTTPException(status_code=400, detail="Keine gueltigen Settings uebergeben.")

    if "ams_mode" in payload:
        mode = str(payload.get("ams_mode")).lower()
        if mode not in {"single", "multi"}:
            raise HTTPException(status_code=400, detail="ams_mode muss single oder multi sein.")
        set_setting(session, "ams_mode", mode)

    if "debug_ws_logging" in payload:
        val = payload.get("debug_ws_logging")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "debug_ws_logging", normalized)

    if "debug_center_mode" in payload:
        mode = str(payload.get("debug_center_mode", "")).lower()
        if mode not in {"lite", "pro"}:
            raise HTTPException(status_code=400, detail="debug_center_mode muss lite oder pro sein.")
        set_setting(session, "debug_center_mode", mode)

    if "debug_center_pro_unlocked" in payload:
        val = payload.get("debug_center_pro_unlocked")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "debug_center_pro_unlocked", normalized)

    if "debug.config.debug_logging_enabled" in payload:
        val = payload.get("debug.config.debug_logging_enabled")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "debug.config.debug_logging_enabled", normalized)

    if "cost.electricity_price_kwh" in payload:
        val = payload.get("cost.electricity_price_kwh")
        if val is None:
            raise HTTPException(status_code=400, detail="cost.electricity_price_kwh darf nicht leer sein.")
        try:
            price = float(val)
        except (TypeError, ValueError):
            logger.exception("Invalid electricity price value: %s", val)
            raise HTTPException(status_code=400, detail="cost.electricity_price_kwh muss eine Zahl sein.")
        if price < 0:
            raise HTTPException(status_code=400, detail="cost.electricity_price_kwh darf nicht negativ sein.")
        set_setting(session, "cost.electricity_price_kwh", str(price))

    if "debug.config.latency_warning_threshold_ms" in payload:
        val = payload.get("debug.config.latency_warning_threshold_ms")
        if val is None:
            raise HTTPException(status_code=400, detail="latency_warning_threshold_ms darf nicht leer sein.")
        try:
            threshold = int(val)
        except (TypeError, ValueError):
            logger.exception("Invalid latency_warning_threshold_ms value: %s", val)
            raise HTTPException(status_code=400, detail="latency_warning_threshold_ms muss eine Zahl sein.")
        if threshold < MIN_LATENCY_WARNING_MS:
            raise HTTPException(
                status_code=400, detail=f"latency_warning_threshold_ms muss >= {MIN_LATENCY_WARNING_MS} sein."
            )
        set_setting(session, "debug.config.latency_warning_threshold_ms", str(threshold))

    if "debug.config.scanner_probe_timeout_ms" in payload:
        val = payload.get("debug.config.scanner_probe_timeout_ms")
        if val is None:
            raise HTTPException(status_code=400, detail="scanner_probe_timeout_ms darf nicht leer sein.")
        try:
            timeout = int(val)
        except (TypeError, ValueError):
            logger.exception("Invalid scanner_probe_timeout_ms value: %s", val)
            raise HTTPException(status_code=400, detail="scanner_probe_timeout_ms muss eine Zahl sein.")
        if timeout < MIN_SCANNER_PROBE_TIMEOUT_MS:
            raise HTTPException(
                status_code=400, detail=f"scanner_probe_timeout_ms muss >= {MIN_SCANNER_PROBE_TIMEOUT_MS} sein."
            )
        set_setting(session, "debug.config.scanner_probe_timeout_ms", str(timeout))

    if "debug.config.scanner_allow_duplicates" in payload:
        val = payload.get("debug.config.scanner_allow_duplicates")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "debug.config.scanner_allow_duplicates", normalized)

    if "debug.config.websocket_debug_level" in payload:
        level = str(payload.get("debug.config.websocket_debug_level", "")).lower()
        if level not in WEBSOCKET_DEBUG_LEVELS:
            raise HTTPException(status_code=400, detail="websocket_debug_level muss off, basic oder verbose sein.")
        set_setting(session, "debug.config.websocket_debug_level", level)

    if "language" in payload:
        lang = str(payload.get("language", "")).lower()
        if lang not in {"de", "en"}:
            raise HTTPException(status_code=400, detail="language muss de oder en sein.")
        set_setting(session, "language", lang)

    if "bambu_username" in payload:
        username = payload.get("bambu_username")
        if username is None:
            set_setting(session, "bambu_username", "")
        else:
            set_setting(session, "bambu_username", str(username))

    if "bambu_password" in payload:
        password = payload.get("bambu_password")
        if password is None:
            set_setting(session, "bambu_password", "")
        else:
            set_setting(session, "bambu_password", str(password))

    if "bambu_region" in payload:
        region = str(payload.get("bambu_region", "")).lower()
        if region not in {"global", "china"}:
            raise HTTPException(status_code=400, detail="bambu_region muss global oder china sein.")
        set_setting(session, "bambu_region", region)

    if "experimental_mode" in payload:
        val = payload.get("experimental_mode")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "experimental_mode", normalized)

    if "ams_conflict_detection_enabled" in payload:
        val = payload.get("ams_conflict_detection_enabled")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "ams_conflict_detection_enabled", normalized)

    if "ams_conflict_tolerance_g" in payload:
        val = payload.get("ams_conflict_tolerance_g")
        if val is None:
            raise HTTPException(status_code=400, detail="ams_conflict_tolerance_g darf nicht leer sein.")
        try:
            tol = int(val)
        except (TypeError, ValueError):
            logger.exception("Invalid ams_conflict_tolerance_g value: %s", val)
            raise HTTPException(status_code=400, detail="ams_conflict_tolerance_g muss eine Zahl sein.")
        if tol < 0:
            raise HTTPException(status_code=400, detail="ams_conflict_tolerance_g darf nicht negativ sein.")
        set_setting(session, "ams_conflict_tolerance_g", str(tol))

    # Experimental tab settings
    if "enable_3mf_title_matching" in payload:
        val = payload.get("enable_3mf_title_matching")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "enable_3mf_title_matching", normalized)

    if "3mf_score_threshold" in payload:
        val = payload.get("3mf_score_threshold")
        if val is None:
            raise HTTPException(status_code=400, detail="3mf_score_threshold darf nicht leer sein.")
        try:
            thr = int(val)
        except (TypeError, ValueError):
            logger.exception("Invalid 3mf_score_threshold value: %s", val)
            raise HTTPException(status_code=400, detail="3mf_score_threshold muss eine Zahl sein.")
        if thr < 0 or thr > 100:
            raise HTTPException(status_code=400, detail="3mf_score_threshold muss zwischen 0 und 100 liegen.")
        set_setting(session, "3mf_score_threshold", str(thr))

    if "enable_file_selection_dialog" in payload:
        val = payload.get("enable_file_selection_dialog")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "enable_file_selection_dialog", normalized)

    if "enable_multi_color_tracking" in payload:
        val = payload.get("enable_multi_color_tracking")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "enable_multi_color_tracking", normalized)

    if "enable_ftp_gcode_download" in payload:
        val = payload.get("enable_ftp_gcode_download")
        normalized = "true" if str(val).lower() in TRUE_VALUES else "false"
        set_setting(session, "enable_ftp_gcode_download", normalized)

    return get_settings(session)
