from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from typing import List, Dict, Any
import logging
import os
import socket
import httpx
from app.database import get_session
from app.models.printer import Printer, PrinterCreate, PrinterRead
from app.models.spool import Spool
from app.services import mqtt_runtime
from app.services.ams_normalizer import (
    device_has_real_ams_from_live_state,
    global_has_real_ams,
    has_ams_lite_from_payload,
)
from services.printer_service import get_printer_service

# Hinweis: kleine Kommentar-Änderung, um Dateisystem-Änderung und Reload zu triggern

router = APIRouter(prefix="/api/printers", tags=["printers"])
logger = logging.getLogger("app")

# Cache für has_real_ams (30s TTL) – wird alle 12s vom Frontend abgefragt
import time as _time
_ams_cache: dict = {"value": None, "ts": 0.0}
_ams_lite_cache: dict = {"value": None, "ts": 0.0}
_AMS_CACHE_TTL = 30.0

UPLOAD_DIR = os.path.join("app", "static", "uploads", "printers")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_image_url(printer_id: str) -> str | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = os.path.join(UPLOAD_DIR, f"{printer_id}{ext}")
        if os.path.exists(candidate):
            return f"/static/uploads/printers/{printer_id}{ext}"
    return None


@router.get("/", response_model=List[PrinterRead])
def get_all_printers(live: bool = False, session: Session = Depends(get_session)):
    """
    Alle Drucker abrufen.
    - live=false (default): schnelle Checks mit 0.3s Timeout
    - live=true: Live-Check mit kurzem Timeout
    """
    printers = session.exec(select(Printer)).all()
    result = []
    
    # Get printer service for online status
    try:
        printer_service = get_printer_service()
    except RuntimeError:
        printer_service = None
    
    for printer in printers:
        online: bool = False
        
        # Check online status from PrinterService (MQTT connection state)
        # [BETA] Klipper-Support: Klipper nutzt "klipper_{id}" als Key (keine cloud_serial)
        if printer_service:
            if printer.printer_type == "klipper":
                _key = f"klipper_{printer.id}"
            elif printer.cloud_serial:
                _key = printer.cloud_serial
            else:
                _key = None
            if _key:
                status = printer_service.get_status(_key)
                online = bool(status.get("connected", False))

        p_dict = printer.dict()
        p_dict["online"] = online
        p_dict["image_url"] = get_image_url(printer.id)
        # has_real_ams determined from live_state payloads
        p_dict["has_real_ams"] = False
        if printer.cloud_serial:
            try:
                p_dict["has_real_ams"] = device_has_real_ams_from_live_state(printer.cloud_serial)
            except Exception:
                logger.exception("Failed to resolve real AMS for printer_id=%s", printer.id)
                p_dict["has_real_ams"] = False
        result.append(p_dict)
    return result


@router.get("/has_real_ams", response_model=dict)
def get_global_has_real_ams(session: Session = Depends(get_session)):
    """
    Global indicator for real AMS presence (excluding AMS Lite).
    Cached for 30s to avoid repeated DB + live-state queries.
    """
    global _ams_cache
    now = _time.monotonic()
    if _ams_cache["value"] is not None and (now - _ams_cache["ts"]) < _AMS_CACHE_TTL:
        return {"value": _ams_cache["value"]}

    try:
        from app.services import live_state as live_state_module
        from app.services.ams_normalizer import has_real_ams_from_payload
        
        # Get all printers from DB with their cloud_serials and names
        printers = session.exec(select(Printer)).all()
        model_map: Dict[str, str] = {}
        name_map: Dict[str, str] = {}
        
        for printer in printers:
            if printer.cloud_serial:
                # Use explicit model if available
                if printer.model:
                    model_map[printer.cloud_serial] = printer.model
                # Also store name for fallback extraction
                if printer.name:
                    name_map[printer.cloud_serial] = printer.name
        
        # Check all live state devices
        all_state = live_state_module.get_all_live_state()
        for device_id, entry in (all_state or {}).items():
            # Get printer model: from DB first, fallback to name extraction
            printer_model = model_map.get(device_id)
            
            # Fallback: Extract printer_model from printer.name if not in DB
            if not printer_model and device_id in name_map:
                printer_name = name_map[device_id]
                name_upper = printer_name.upper()
                if "A1" in name_upper and "MINI" in name_upper:
                    printer_model = "A1MINI"
                elif "X1C" in name_upper:
                    printer_model = "X1C"
            
            # Check if this device has real AMS (not AMS Lite)
            payload = entry.get("payload") or {}
            if has_real_ams_from_payload(payload, printer_model=printer_model):
                _ams_cache.update({"value": True, "ts": _time.monotonic()})
                return {"value": True}

        _ams_cache.update({"value": False, "ts": _time.monotonic()})
        return {"value": False}
    except Exception:
        logger.exception("Failed to resolve global real AMS state")
        return {"value": False}


@router.get("/has_ams_lite", response_model=dict)
def get_global_has_ams_lite(session: Session = Depends(get_session)):
    """
    Global indicator for AMS Lite presence.
    Cached for 30s to avoid repeated DB + live-state queries.
    """
    global _ams_lite_cache
    now = _time.monotonic()
    if _ams_lite_cache["value"] is not None and (now - _ams_lite_cache["ts"]) < _AMS_CACHE_TTL:
        return {"value": _ams_lite_cache["value"]}

    try:
        from app.services import live_state as live_state_module

        printers = session.exec(select(Printer)).all()
        model_map: Dict[str, str] = {}
        name_map: Dict[str, str] = {}

        for printer in printers:
            if printer.cloud_serial:
                if printer.model:
                    model_map[printer.cloud_serial] = printer.model
                if printer.name:
                    name_map[printer.cloud_serial] = printer.name

        all_state = live_state_module.get_all_live_state()
        for device_id, entry in (all_state or {}).items():
            printer_model = model_map.get(device_id)

            if not printer_model and device_id in name_map:
                printer_name = name_map[device_id]
                name_upper = printer_name.upper()
                if "A1" in name_upper and "MINI" in name_upper:
                    printer_model = "A1MINI"
                elif "A1" in name_upper:
                    printer_model = "A1"

            payload = entry.get("payload") or {}
            if has_ams_lite_from_payload(payload, printer_model=printer_model):
                _ams_lite_cache.update({"value": True, "ts": _time.monotonic()})
                return {"value": True}

        _ams_lite_cache.update({"value": False, "ts": _time.monotonic()})
        return {"value": False}
    except Exception:
        logger.exception("Failed to resolve global AMS Lite state")
        return {"value": False}


@router.get("/{printer_id}", response_model=PrinterRead)
def get_printer(printer_id: str, session: Session = Depends(get_session)):
    """Einzelnen Drucker abrufen"""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    p_dict = printer.dict()
    p_dict["image_url"] = get_image_url(printer.id)
    p_dict["has_real_ams"] = False
    if printer.cloud_serial:
        try:
            p_dict["has_real_ams"] = device_has_real_ams_from_live_state(printer.cloud_serial)
        except Exception:
            logger.exception("Failed to resolve real AMS for printer_id=%s", printer.id)
            p_dict["has_real_ams"] = False
    return p_dict




@router.get("/{printer_id}/credentials", response_model=Dict[str, Any], summary="Get Printer Credentials")
def get_printer_credentials(printer_id: str, session: Session = Depends(get_session)):
    """
    Lade Drucker Credentials (MQTT-relevant) aus der Datenbank.
    API Keys werden hier bewusst nicht mehr im Klartext ausgeliefert.
    """
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail=f"Drucker mit ID {printer_id} nicht gefunden")

    return {
        "success": True,
        "printer_id": printer.id,
        "name": printer.name,
        "cloud_serial": printer.cloud_serial,
        "ip_address": printer.ip_address,
        "port": printer.port,
        "printer_type": printer.printer_type,
        "mqtt_version": printer.mqtt_version,
        "model": printer.model,
        "has_api_key": bool(printer.api_key),
    }


@router.post("/")
def create_printer(printer: PrinterCreate, session: Session = Depends(get_session)):
    """Neuen Drucker anlegen"""
    # ============================================================
    # BAMBU PRINTER SERIES (REQUIRED)
    #
    # Bambu-Lab-Drucker liefern serienabhängig unterschiedliche
    # Live-Felder (ETA, Prozent, AMS, mc_*).
    #
    # Die Serie MUSS beim Anlegen explizit gesetzt werden.
    # Auto-Erkennung ist absichtlich deaktiviert.
    # ============================================================
    # Duplicate-Check per IP + Typ (Lite)
    if printer.ip_address and printer.printer_type:
        exists = session.exec(
            select(Printer).where(
                Printer.ip_address == printer.ip_address,
                Printer.printer_type == printer.printer_type
            )
        ).first()
        if exists:
            existing = exists.dict()
            existing["status"] = "exists"
            existing["image_url"] = get_image_url(exists.id)
            return existing
    # Für Bambu muss eine Seriennummer und Access Code vorhanden sein
    if printer.printer_type in ["bambu", "bambu_lab"]:
        if not printer.cloud_serial or not printer.api_key:
            raise HTTPException(status_code=400, detail="Seriennummer und Access Code sind erforderlich")
        if not printer.series:
            raise HTTPException(
                status_code=400,
                detail="Bambu printers require an explicit series (A/X/P/H)"
            )
        series_code = str(printer.series).strip().upper()
        series_to_model = {
            "A": "A1",
            "X": "X1C",
            "P": "P1",
            "H": "H1",
        }
        if series_code not in series_to_model:
            raise HTTPException(
                status_code=400,
                detail="Bambu printers require an explicit series (A/X/P/H)"
            )
        printer.series = series_code
        printer.model = series_to_model[series_code]

    # Setze Standard-MQTT-Port für Bambu auf 8883, falls nicht angegeben
    if printer.printer_type in ["bambu", "bambu_lab"] and not printer.port:
        printer.port = 8883

    db_printer = Printer.model_validate(printer)
    session.add(db_printer)
    session.commit()
    session.refresh(db_printer)
    p_dict = db_printer.dict()
    p_dict["image_url"] = get_image_url(db_printer.id)
    p_dict["status"] = "created"
    return p_dict


@router.put("/{printer_id}", response_model=PrinterRead)
def update_printer(printer_id: str, printer: PrinterCreate, session: Session = Depends(get_session)):
    """Drucker aktualisieren"""
    db_printer = session.get(Printer, printer_id)
    if not db_printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    old_auto_connect = bool(getattr(db_printer, "auto_connect", False))
    # Duplicate-Check bei IP/Typ-Änderung
    if printer.ip_address and printer.printer_type:
        exists = session.exec(
            select(Printer).where(
                Printer.ip_address == printer.ip_address,
                Printer.printer_type == printer.printer_type,
                Printer.id != printer_id
            )
        ).first()
        if exists:
            raise HTTPException(status_code=409, detail="Drucker mit dieser IP/Typ existiert bereits")
    if printer.printer_type in ["bambu", "bambu_lab"]:
        if not printer.cloud_serial or not printer.api_key:
            raise HTTPException(status_code=400, detail="Seriennummer und Access Code sind erforderlich")
    # If Bambu and no port provided, default to 8883
    # (apply after merging data below to cover updates that switch type)
    printer_data = printer.model_dump(exclude_unset=True)
    for key, value in printer_data.items():
        setattr(db_printer, key, value)
    if db_printer.printer_type in ["bambu", "bambu_lab"] and not db_printer.port:
        db_printer.port = 8883
    
    session.add(db_printer)
    session.commit()
    session.refresh(db_printer)
    new_auto_connect = bool(getattr(db_printer, "auto_connect", False))
    if old_auto_connect != new_auto_connect:
        logger.info(
            "Auto-connect flag changed (%s→%s) for printer %s",
            old_auto_connect,
            new_auto_connect,
            printer_id,
        )
        try:
            mqtt_runtime.apply_auto_connect(db_printer)
        except Exception as exc:
            logger.exception("Failed to apply auto-connect change for printer %s: %s", printer_id, exc)
    p_dict = db_printer.dict()
    p_dict["image_url"] = get_image_url(db_printer.id)
    return p_dict


@router.post("/{printer_id}/image")
async def upload_printer_image(
    printer_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Bild für einen Drucker hochladen und Pfad setzen."""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")

    # Dateityp prüfen
    content_type = (file.content_type or "").lower()
    if content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Nur JPG, PNG oder WEBP erlaubt")

    # Größe prüfen (max 5 MB)
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(status_code=400, detail="Bild zu groß (max 5 MB)")

    # Endung bestimmen
    ext = ".jpg"
    if content_type == "image/png":
        ext = ".png"
    elif content_type == "image/webp":
        ext = ".webp"

    # existierende Dateien entfernen
    for e in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = os.path.join(UPLOAD_DIR, f"{printer_id}{e}")
        if os.path.exists(candidate):
            try:
                os.remove(candidate)
            except Exception:
                logger.exception("Failed to remove printer image %s", candidate)

    file_path = os.path.join(UPLOAD_DIR, f"{printer_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(data)

    image_url = f"/static/uploads/printers/{printer_id}{ext}"
    return {"success": True, "image_url": image_url}


@router.delete("/{printer_id}/image")
async def delete_printer_image(
    printer_id: str,
    session: Session = Depends(get_session)
):
    """Bild eines Druckers löschen"""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")

    # Alle möglichen Bild-Dateien entfernen
    removed = False
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = os.path.join(UPLOAD_DIR, f"{printer_id}{ext}")
        if os.path.exists(candidate):
            try:
                os.remove(candidate)
                removed = True
                logger.info(f"Removed printer image: {candidate}")
            except Exception:
                logger.exception("Failed to remove printer image %s", candidate)

    if not removed:
        raise HTTPException(status_code=404, detail="Kein Bild gefunden")

    return {"success": True, "message": "Bild entfernt"}


@router.delete("/{printer_id}")
def delete_printer(printer_id: str, session: Session = Depends(get_session)):
    """Drucker löschen
    
    WICHTIG: Spulen werden ins Lager zurückgeführt.
    - weight_current bleibt erhalten (kein Datenverlust)
    - printer_id und ams_slot werden gelöscht
    - status = "Lager"
    """
    from sqlmodel import select
    
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    
    # Bringe alle Spulen dieses Druckers zurück ins Lager
    # OHNE weight_current zu löschen!
    spools_in_printer = session.exec(
        select(Spool).where(Spool.printer_id == printer_id)
    ).all()
    
    for spool in spools_in_printer:
        spool.printer_id = None
        spool.ams_slot = None
        spool.status = "Lager"
        # weight_current NICHT ändern - bleibt erhalten!
        session.add(spool)
    
    # Lösche Drucker
    session.delete(printer)
    session.commit()
    return {"success": True, "message": "Drucker gelöscht"}


@router.post("/{printer_id}/test")
async def test_printer_connection(printer_id: str, session: Session = Depends(get_session)):
    """Verbindung zum Drucker testen"""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    
    if printer.printer_type == "manual":
        return {
            "status": "info",
            "message": "Manuelle Drucker haben keine Netzwerk-Verbindung",
            "online": None
        }
    
    try:
        if printer.printer_type in ["bambu", "bambu_lab"]:
            # Test MQTT port (6000)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((printer.ip_address, printer.port or 6000))
            sock.close()
            
            if result == 0:
                return {
                    "status": "success",
                    "message": f"Bambu Lab Drucker erreichbar auf {printer.ip_address}:{printer.port or 6000}",
                    "online": True
                }
            else:
                return {
                    "status": "error",
                    "message": f"Bambu Lab Drucker nicht erreichbar auf {printer.ip_address}:{printer.port or 6000}",
                    "online": False
                }
        
        elif printer.printer_type == "klipper":
            # Test Moonraker API (7125)
            port = printer.port or 7125
            url = f"http://{printer.ip_address}:{port}/server/info"
            
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    klippy_state = data.get("result", {}).get("klippy_state", "unknown")
                    return {
                        "status": "success",
                        "message": f"Klipper Drucker erreichbar - Status: {klippy_state}",
                        "online": True,
                        "klippy_state": klippy_state
                    }
                else:
                    return {
                        "status": "warning",
                        "message": f"Klipper API antwortet mit Status {response.status_code}",
                        "online": False
                    }
        
        return {
            "status": "error",
            "message": "Unbekannter Drucker-Typ",
            "online": False
        }
    
    except socket.timeout:
        return {
            "status": "error",
            "message": "Verbindungs-Timeout - Drucker nicht erreichbar",
            "online": False
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Verbindungsfehler: {str(e)}",
            "online": False
        }


@router.post("/{printer_id}/unload-external")
def unload_external_spool_from_printer(
    printer_id: str,
    session: Session = Depends(get_session)
):
    """
    Entlädt externe Spule von einem Drucker (Alias-Route für /api/spools/unload-external/{printer_id}).
    Setzt status="Lager" und entfernt printer_id Verknüpfung.
    """
    from app.models.spool import Spool
    from app.services.spool_helpers import is_external_tray
    from sqlmodel import select, or_

    # Lade Printer für modellabhängige Tray-Erkennung
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")

    # Finde externe Spule für diesen Drucker
    # Suche nach: printer_id = X UND (location="external" ODER ams_slot=254/255)
    # PLUS Backward-Compatibility: ams_slot=None (alte Daten)

    # Alle Spulen für diesen Drucker holen
    all_spools = session.exec(
        select(Spool).where(Spool.printer_id == printer_id)
    ).all()

    # Filtere externe Spule (modellabhängig)
    spool = None
    for s in all_spools:
        if (s.location == "external" or
            is_external_tray(printer, s.ams_slot) or
            s.ams_slot is None):  # Backward-Compatibility
            spool = s
            break

    if not spool:
        logger.info(f"No external spool found for printer {printer_id}")
        # Debug: zeige alle Spulen für diesen Drucker
        all_spools = session.exec(
            select(Spool).where(Spool.printer_id == printer_id)
        ).all()
        logger.info(f"All spools for printer {printer_id}: {[(s.id, s.status, s.location, s.ams_slot) for s in all_spools]}")
        return {"success": True, "message": "Keine externe Spule geladen"}

    logger.info(f"Unloading spool {spool.id} (status={spool.status}, location={spool.location}) from printer {printer_id}")

    # Update spool
    spool.printer_id = None
    spool.status = "Lager"
    spool.location = "storage"
    spool.ams_slot = None
    
    # WICHTIG: Entferne RFID-Verknüpfung, damit AMS-Sync diese Spule nicht mehr findet
    # Sonst würde der MQTT-Feed die Spule sofort wieder als "Aktiv" markieren
    spool.tag_uid = None
    spool.tray_uuid = None

    session.add(spool)
    session.commit()
    session.refresh(spool)

    logger.info(f"Successfully unloaded spool {spool.id} - new state: printer_id={spool.printer_id}, status={spool.status}, location={spool.location}")

    return {"success": True, "spool_id": spool.id}

