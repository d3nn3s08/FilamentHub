from fastapi import APIRouter, HTTPException
import json

# Nutzt den in mqtt_routes gefüllten Message-Puffer
try:
    from app.routes.mqtt_routes import message_buffer, MQTTMessage  # type: ignore
except Exception:
    # Fallback, falls mqtt_routes den Import verweigert
    message_buffer = []
    MQTTMessage = None  # type: ignore

router = APIRouter(prefix="/api/bambu", tags=["Bambu"])


@router.get("/ams/latest")
def get_latest_ams():
    """
    Liefert die letzte MQTT-Nachricht zum AMS (Topic enthält '/ams') aus dem lokalen Puffer.
    Nur als schneller Status-Snapshot gedacht; benötigt laufenden MQTT-Listener.
    """
    # Suche nach der letzten AMS-Nachricht (rückwärts durchs Buffer)
    for msg in reversed(message_buffer):
        if "/ams" in (msg.topic or ""):
            parsed = None
            try:
                parsed = json.loads(msg.payload)
            except Exception:
                parsed = None

            return {
                "found": True,
                "topic": msg.topic,
                "timestamp": msg.timestamp,
                "raw_payload": msg.payload,
                "parsed": parsed,
            }

    raise HTTPException(status_code=404, detail="Keine AMS-MQTT-Nachricht im Puffer gefunden")
