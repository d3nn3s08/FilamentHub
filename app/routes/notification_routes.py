import json
import asyncio
from typing import Any, Dict, List, Set

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from sqlmodel import Session, select

from app.database import get_session, engine
from app.models.settings import Setting

router = APIRouter()

DEFAULT_NOTIFICATIONS: List[Dict[str, Any]] = [
    {
        "id": "print_done",
        "label": "Druck abgeschlossen",
        "message": "Der Druck wurde erfolgreich abgeschlossen.",
        "type": "success",
        "persistent": True,
        "enabled": True,
    },
    {
        "id": "filament_empty",
        "label": "Filament leer",
        "message": "Filamentvorrat ist leer.",
        "type": "error",
        "persistent": True,
        "enabled": True,
    },
    {
        "id": "ams_error",
        "label": "AMS Fehler",
        "message": "Es liegt ein Fehler im AMS vor.",
        "type": "warn",
        "persistent": True,
        "enabled": True,
    },
    {
        "id": "job_no_tracking",
        "label": "Job ohne Filament-Tracking",
        "message": "Job '{job_name}' auf Drucker '{printer_name}' wurde ohne Filament-Tracking beendet. Bitte Spule zuordnen und Verbrauch nachtragen.",
        "type": "warn",
        "persistent": True,
        "enabled": True,
    },
    {
        "id": "job_failed",
        "label": "Job fehlgeschlagen",
        "message": "Job '{job_name}' auf Drucker '{printer_name}' ist fehlgeschlagen (Status: {status}).",
        "type": "error",
        "persistent": True,
        "enabled": True,
    },
    {
        "id": "job_aborted",
        "label": "Job abgebrochen",
        "message": "Job '{job_name}' auf Drucker '{printer_name}' wurde abgebrochen (Status: {status}).",
        "type": "warn",
        "persistent": True,
        "enabled": True,
    },
    {
        "id": "ams_tray_error",
        "label": "AMS Tray Fehler",
        "message": "Problem mit AMS-Spulenfach auf Drucker '{printer_name}' erkannt.",
        "type": "error",
        "persistent": True,
        "enabled": False,
    },
    {
        "id": "ams_humidity_high",
        "label": "AMS Luftfeuchtigkeit hoch",
        "message": "AMS auf Drucker '{printer_name}' hat zu hohe Luftfeuchtigkeit ({humidity}% > 60%).",
        "type": "warn",
        "persistent": True,
        "enabled": False,
    },
    {
        "id": "job_no_spool",
        "label": "Job ohne Spule gestartet",
        "message": "Job '{job_name}' auf Drucker '{printer_name}' wurde ohne Spulenzuordnung gestartet.",
        "type": "warn",
        "persistent": True,
        "enabled": False,
    },
]

notification_ws_clients: Set[WebSocket] = set()


def _persist_config(session: Session, notifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    serialized = json.dumps(notifications, ensure_ascii=False)
    setting = session.exec(select(Setting).where(Setting.key == "notifications_config")).first()
    if setting:
        setting.value = serialized
    else:
        setting = Setting(key="notifications_config", value=serialized)
        session.add(setting)
    session.commit()
    return json.loads(serialized)


def ensure_notification_config(session: Session) -> List[Dict[str, Any]]:
    setting = session.exec(select(Setting).where(Setting.key == "notifications_config")).first()

    # Bestehende Config laden
    existing_notifications = []
    if setting and setting.value:
        try:
            data = json.loads(setting.value)
            if isinstance(data, list):
                existing_notifications = data
        except Exception:
            pass

    # Merge: Neue Defaults hinzufügen die noch nicht existieren
    existing_ids = {n.get("id") for n in existing_notifications}
    merged = list(existing_notifications)  # Kopie der bestehenden

    for default_notif in DEFAULT_NOTIFICATIONS:
        if default_notif.get("id") not in existing_ids:
            # Neue Notification aus Defaults hinzufügen
            merged.append(default_notif)

    # Wenn etwas hinzugefügt wurde, speichern
    if len(merged) > len(existing_notifications):
        return _persist_config(session, merged)

    return existing_notifications if existing_notifications else _persist_config(session, DEFAULT_NOTIFICATIONS)


def _validate_notifications(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, dict) and "notifications" in raw:
        raw = raw.get("notifications")
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="Ungültiges Format, erwartete Liste von Notifications.")

    validated: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Jede Notification muss ein Objekt sein.")
        notif_id = str(item.get("id", "")).strip()
        message = str(item.get("message", "")).strip()
        if not notif_id or not message:
            raise HTTPException(status_code=400, detail="Notification benötigt mindestens id und message.")
        validated.append(
            {
                "id": notif_id,
                "label": str(item.get("label", notif_id)).strip() or notif_id,
                "message": message,
                "type": str(item.get("type", "info")).strip() or "info",
                "persistent": bool(item.get("persistent", False)),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return validated


async def broadcast_notification(notification: Dict[str, Any]) -> None:
    dead: Set[WebSocket] = set()
    payload = {"event": "notification_trigger", "payload": notification}
    for ws in list(notification_ws_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        try:
            await ws.close()
        except Exception:
            pass
        notification_ws_clients.discard(ws)


@router.get("/api/notifications-config")
def get_notifications_config(session: Session = Depends(get_session)):
    return {"notifications": ensure_notification_config(session)}


@router.post("/api/notifications-config")
async def save_notifications_config(request: Request, session: Session = Depends(get_session)):
    payload = await request.json()
    validated = _validate_notifications(payload)
    persisted = _persist_config(session, validated)
    return {"notifications": persisted}


@router.post("/api/notifications-trigger")
async def trigger_notification(payload: Dict[str, Any], session: Session = Depends(get_session)):
    notif_id = str(payload.get("id", "")).strip()
    if not notif_id:
        raise HTTPException(status_code=400, detail="Notification id fehlt.")
    notifications = ensure_notification_config(session)
    notification = next((n for n in notifications if n.get("id") == notif_id), None)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification nicht gefunden.")
    if not notification.get("enabled", True):
        raise HTTPException(status_code=400, detail="Notification ist deaktiviert.")

    await broadcast_notification(notification)
    return {"success": True, "notification": notification}


@router.websocket("/api/notifications/ws")
async def notifications_websocket(websocket: WebSocket):
    await websocket.accept()
    notification_ws_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        notification_ws_clients.discard(websocket)


# ===== Helper für synchrones Triggern =====
def trigger_notification_sync(notification_id: str, **context) -> None:
    """
    Synchrone Funktion zum Triggern einer Notification.
    Kann von Services (job_tracking, etc.) aufgerufen werden.

    Args:
        notification_id: Die ID der Notification (z.B. "job_failed")
        **context: Zusätzliche Kontext-Daten (job_name, printer_name, etc.)
    """
    try:
        with Session(engine) as session:
            notifications = ensure_notification_config(session)
            notification = next((n for n in notifications if n.get("id") == notification_id), None)

            if not notification:
                # Notification nicht definiert - ignorieren
                return

            if not notification.get("enabled", True):
                # Notification ist deaktiviert - ignorieren
                return

            # Kontext-Daten zur Message hinzufügen falls vorhanden
            message = notification.get("message", "")
            if context:
                # Ersetze Platzhalter in der Message (z.B. {job_name}, {printer_name})
                try:
                    message = message.format(**context)
                except (KeyError, ValueError):
                    # Falls Platzhalter fehlen, originale Message verwenden
                    pass

            # Erstelle Notification-Payload
            notif_payload = {
                **notification,
                "message": message,
                "context": context
            }

            # Broadcast async (fire and forget)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Wenn Loop läuft, schedule als Task
                    asyncio.create_task(broadcast_notification(notif_payload))
                else:
                    # Wenn kein Loop läuft, create new one
                    asyncio.run(broadcast_notification(notif_payload))
            except RuntimeError:
                # Kein Event Loop - ignorieren (z.B. in Tests)
                pass
    except Exception as e:
        # Fehler beim Triggern sollte nicht den Hauptprozess stoppen
        import logging
        logging.getLogger(__name__).error(f"Fehler beim Triggern von Notification '{notification_id}': {e}")
