from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Depends

from app.database import get_session
from sqlmodel import select
from app.models.printer import Printer
from app.services import mqtt_runtime
from app.services.live_state import get_live_state, get_all_live_state

router = APIRouter(prefix="/api/live-state", tags=["LiveState"])

OFFLINE_TIMEOUT = 60  # Sekunden ohne MQTT-Nachricht bis "Offline" (vorher 15s, zu aggressiv)


# [BETA] Klipper-Support: Liefert den live_state-Key je nach Druckertyp
# Bambu → cloud_serial, Klipper → "klipper_{printer.id}"
def _get_live_key(printer: "Printer") -> Optional[str]:
    if getattr(printer, "printer_type", None) == "klipper":
        return f"klipper_{printer.id}"
    return printer.cloud_serial


def _parse_last_seen(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _get_printer_service(request: Request):
    return getattr(request.app.state, "printer_service", None)


def _build_live_entry(
    printer: Printer,
    live_entry: Optional[Dict[str, Any]],
    printer_service: Any,
    runtime_status: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    cloud_serial = printer.cloud_serial
    payload = live_entry.get("payload") if isinstance(live_entry, dict) else None
    last_seen = None
    mqtt_connected = False

    # [BETA] Klipper-Support: live_key für PrinterService-Lookup (statt cloud_serial direkt)
    # Bambu: live_key == cloud_serial → kein Unterschied
    # Klipper: live_key == "klipper_{id}" → findet Eintrag des Pollers
    live_key = _get_live_key(printer)
    if printer_service and live_key:
        entry = printer_service.printers.get(live_key)
        if isinstance(entry, dict):
            last_seen = entry.get("last_seen")
            mqtt_connected = bool(entry.get("connected", False))

    # [BETA] Klipper-Support: Fallback auf live_state-Timestamp wenn PrinterService last_seen fehlt
    if last_seen is None and getattr(printer, "printer_type", None) == "klipper" and isinstance(live_entry, dict):
        ts = live_entry.get("ts")
        if ts:
            last_seen = ts
            mqtt_connected = True

    # runtime_status-Check bleibt unverändert (Bambu MQTT)
    if runtime_status.get("cloud_serial") == cloud_serial:
        mqtt_connected = bool(runtime_status.get("connected", False))

    last_dt = _parse_last_seen(last_seen)
    cache_age_sec = None
    printer_online = False
    offline_reason = None
    if last_dt:
        cache_age_sec = int((now - last_dt).total_seconds())
        printer_online = cache_age_sec <= OFFLINE_TIMEOUT
        if not printer_online:
            offline_reason = "timeout"
    else:
        offline_reason = "never_seen"

    auto_connect_enabled = bool(getattr(printer, "auto_connect", False))
    reconnecting = bool(auto_connect_enabled and not mqtt_connected)

    return {
        "printer_id": printer.id,
        "printer_name": printer.name,
        # [BETA] Klipper-Support: device nutzt live_key ("klipper_123" oder cloud_serial)
        "device": live_key,
        "cloud_serial": cloud_serial,
        "auto_connect_enabled": auto_connect_enabled,
        "mqtt_connected": mqtt_connected,
        "printer_online": printer_online,
        "last_seen": last_seen,
        "cache_age_sec": cache_age_sec,
        "offline_reason": offline_reason,
        "reconnecting": reconnecting,
        "payload": payload,
        "ts": last_seen,
    }


@router.get("/{device_id}")
async def get_live_state_endpoint(device_id: str, request: Request, session=Depends(get_session)) -> Any:
    live = get_live_state(device_id)
    printer_service = _get_printer_service(request)
    now = datetime.now(timezone.utc)
    runtime_status = mqtt_runtime.status()

    printer = session.exec(select(Printer).where(Printer.cloud_serial == device_id)).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Live state not found")

    return _build_live_entry(printer, live, printer_service, runtime_status, now)


@router.get("/")
async def list_live_state(request: Request, session=Depends(get_session)) -> Any:
    live = get_all_live_state()
    printer_service = _get_printer_service(request)
    now = datetime.now(timezone.utc)
    runtime_status = mqtt_runtime.status()

    result: Dict[str, Any] = {}
    printers = session.exec(select(Printer)).all()
    for printer in printers:
        # [BETA] Klipper-Support: _get_live_key() statt cloud_serial,
        # damit Klipper-Drucker nicht mehr übersprungen werden
        live_key = _get_live_key(printer)
        if not live_key:
            continue
        if getattr(printer, "active", True) is not True:
            continue
        entry = _build_live_entry(printer, live.get(live_key), printer_service, runtime_status, now)
        # Klipper-Drucker immer einschließen (auch "never_seen"), damit das Frontend "Offline" anzeigen kann
        # Bambu-Drucker ohne jegliche Aktivität weiterhin überspringen
        is_klipper = getattr(printer, "printer_type", None) == "klipper"
        if not is_klipper and entry.get("offline_reason") == "never_seen" and not entry.get("payload"):
            continue
        # [BETA] Klipper-Support: Key = "klipper_{id}" für Klipper, cloud_serial für Bambu
        result[live_key] = entry

    return result


# [BETA] Klipper-Support: Temperatur-Verlauf Endpoint (vor /{device_id} um Route-Konflikt zu vermeiden)
@router.get("/klipper/{printer_id}/temp-history")
def get_klipper_temp_history_route(printer_id: str):
    from services.klipper_polling_service import get_klipper_temp_history
    return {"history": get_klipper_temp_history(printer_id)}
