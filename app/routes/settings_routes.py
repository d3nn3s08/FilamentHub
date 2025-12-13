from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.settings import Setting

router = APIRouter()


DEFAULTS = {
    "ams_mode": "single",
    "debug_ws_logging": "false",
    "debug_center_mode": "lite",
    "debug_center_pro_unlocked": "false",
}


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


@router.get("/api/settings")
def get_settings(session: Session = Depends(get_session)):
    ams_mode = get_setting(session, "ams_mode", DEFAULTS["ams_mode"]) or DEFAULTS["ams_mode"]
    debug_ws_logging = get_setting(session, "debug_ws_logging", DEFAULTS["debug_ws_logging"]) or DEFAULTS["debug_ws_logging"]
    debug_center_mode = get_setting(session, "debug_center_mode", DEFAULTS["debug_center_mode"]) or DEFAULTS["debug_center_mode"]
    pro_unlocked = get_setting(session, "debug_center_pro_unlocked", DEFAULTS["debug_center_pro_unlocked"]) or DEFAULTS["debug_center_pro_unlocked"]
    return {
        "ams_mode": ams_mode if ams_mode in {"single", "multi"} else DEFAULTS["ams_mode"],
        "debug_ws_logging": str(debug_ws_logging).lower() in {"1", "true", "yes"},
        "debug_center_mode": debug_center_mode if debug_center_mode in {"lite", "pro"} else DEFAULTS["debug_center_mode"],
        "debug_center_pro_unlocked": str(pro_unlocked).lower() in {"1", "true", "yes"},
    }


@router.put("/api/settings")
async def update_settings(payload: dict, session: Session = Depends(get_session)):
    allowed_keys = {"ams_mode", "debug_ws_logging", "debug_center_mode", "debug_center_pro_unlocked"}
    if not any(k in payload for k in allowed_keys):
        raise HTTPException(status_code=400, detail="Keine gueltigen Settings uebergeben.")

    if "ams_mode" in payload:
        mode = str(payload.get("ams_mode")).lower()
        if mode not in {"single", "multi"}:
            raise HTTPException(status_code=400, detail="ams_mode muss single oder multi sein.")
        set_setting(session, "ams_mode", mode)

    if "debug_ws_logging" in payload:
        val = payload.get("debug_ws_logging")
        normalized = "true" if str(val).lower() in {"1", "true", "yes", "on"} else "false"
        set_setting(session, "debug_ws_logging", normalized)

    if "debug_center_mode" in payload:
        mode = str(payload.get("debug_center_mode", "")).lower()
        if mode not in {"lite", "pro"}:
            raise HTTPException(status_code=400, detail="debug_center_mode muss lite oder pro sein.")
        set_setting(session, "debug_center_mode", mode)

    if "debug_center_pro_unlocked" in payload:
        val = payload.get("debug_center_pro_unlocked")
        normalized = "true" if str(val).lower() in {"1", "true", "yes", "on"} else "false"
        set_setting(session, "debug_center_pro_unlocked", normalized)

    return get_settings(session)
