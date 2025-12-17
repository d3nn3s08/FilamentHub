from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from typing import List, Dict, Any
import socket
import httpx
import os
from app.database import get_session
from app.models.printer import Printer, PrinterCreate, PrinterRead

# Hinweis: kleine Kommentar-Änderung, um Dateisystem-Änderung und Reload zu triggern

router = APIRouter(prefix="/api/printers", tags=["printers"])

UPLOAD_DIR = os.path.join("app", "static", "uploads", "printers")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_image_url(printer_id: str) -> str | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = os.path.join(UPLOAD_DIR, f"{printer_id}{ext}")
        if os.path.exists(candidate):
            return f"/static/uploads/printers/{printer_id}{ext}"
    return None


@router.get("/", response_model=List[PrinterRead])
def get_all_printers(session: Session = Depends(get_session)):
    """Alle Drucker abrufen"""
    printers = session.exec(select(Printer)).all()
    result = []
    for printer in printers:
        online = False
        # Verbindungstest je nach Typ
        try:
            if printer.printer_type in ["bambu", "bambu_lab"]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                res = sock.connect_ex((printer.ip_address, printer.port or 6000))
                sock.close()
                online = (res == 0)
            elif printer.printer_type == "klipper":
                port = printer.port or 7125
                url = f"http://{printer.ip_address}:{port}/server/info"
                try:
                    r = httpx.get(url, timeout=1)
                    online = r.status_code == 200
                except Exception:
                    online = False
            elif printer.printer_type == "manual":
                online = None
        except Exception:
            online = False
        # Dict mit Online-Status zurückgeben
        p_dict = printer.dict()
        p_dict["online"] = online
        p_dict["image_url"] = get_image_url(printer.id)
        result.append(p_dict)
    return result


@router.get("/{printer_id}", response_model=PrinterRead)
def get_printer(printer_id: str, session: Session = Depends(get_session)):
    """Einzelnen Drucker abrufen"""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    p_dict = printer.dict()
    p_dict["image_url"] = get_image_url(printer.id)
    return p_dict


@router.get("/{printer_id}/credentials", response_model=Dict[str, Any], summary="Get Printer Credentials")
def get_printer_credentials(printer_id: str, session: Session = Depends(get_session)):
    """
    Lade Drucker Credentials (MQTT-relevant) aus der Datenbank.
    Liefert nur die Felder, die für MQTT-Connections benötigt werden.
    """
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail=f"Drucker mit ID {printer_id} nicht gefunden")

    return {
        "success": True,
        "printer_id": printer.id,
        "name": printer.name,
        "api_key": printer.api_key,
        "cloud_serial": printer.cloud_serial,
        "ip_address": printer.ip_address,
        "port": printer.port,
        "printer_type": printer.printer_type,
        "mqtt_version": printer.mqtt_version,
        "model": printer.model
    }


@router.post("/")
def create_printer(printer: PrinterCreate, session: Session = Depends(get_session)):
    """Neuen Drucker anlegen"""
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

    # Größe prüfen (max 1 MB)
    data = await file.read()
    if len(data) > 1_000_000:
        raise HTTPException(status_code=400, detail="Bild zu groß (max 1 MB)")

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
                pass

    file_path = os.path.join(UPLOAD_DIR, f"{printer_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(data)

    image_url = f"/static/uploads/printers/{printer_id}{ext}"
    return {"success": True, "image_url": image_url}


@router.delete("/{printer_id}")
def delete_printer(printer_id: str, session: Session = Depends(get_session)):
    """Drucker löschen"""
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")
    
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
