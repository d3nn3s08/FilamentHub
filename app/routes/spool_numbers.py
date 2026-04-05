"""
Neue API-Endpoints für Spulen-Nummern-System

Diese Routes erweitern die bestehenden Spulen-APIs um:
- Suche nach Spulen-Nummer
- Live-Suche für Quick-Assign
- Manuelle AMS-Slot-Zuweisung
- Spule von Slot entfernen
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, Session, or_
from typing import List, Optional
from datetime import datetime

from app.database import get_session
from app.models.spool import Spool, SpoolReadSchema
from app.models.printer import Printer
from pydantic import BaseModel


router = APIRouter(prefix="/api/spools", tags=["Spool Numbers"])


# === SUCHE ===

@router.get("/by-number/{spool_number}", response_model=SpoolReadSchema)
def get_spool_by_number(spool_number: int, session: Session = Depends(get_session)):
    """
    Findet Spule nach Spulen-Nummer

    Args:
        spool_number: Spulen-Nummer (z.B. 3 für "Spule #3")

    Returns:
        Spool-Objekt

    Raises:
        404: Spule nicht gefunden
    """
    spool = session.exec(
        select(Spool).where(Spool.spool_number == spool_number)
    ).first()

    if not spool:
        raise HTTPException(
            status_code=404,
            detail=f"Spule #{spool_number} nicht gefunden"
        )

    return SpoolReadSchema.model_validate(spool)


@router.get("/search", response_model=List[SpoolReadSchema])
def search_spools(
    term: str = "",
    unassigned: bool = False,
    printer_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Live-Suche in Spulen (OHNE JOINs - sehr schnell!)

    Sucht in denormalisierten Feldern: spool_number, name, vendor, color

    Query-Parameter:
        - term: Suchbegriff (optional)
        - unassigned: true = nur nicht zugewiesene Spulen
        - printer_id: Nur Spulen eines bestimmten Druckers

    Returns:
        Liste von Spulen

    Beispiele:
        GET /api/spools/search?term=6
        → Findet #6, #16, #26

        GET /api/spools/search?term=PLA&unassigned=true
        → Findet alle freien PLA-Spulen

        GET /api/spools/search?term=black
        → Findet alle schwarzen Spulen
    """
    stmt = select(Spool)

    # Filter: Nur nicht zugewiesen
    if unassigned:
        stmt = stmt.where(
            Spool.printer_id.is_(None),
            Spool.ams_slot.is_(None)
        )

    # Filter: Bestimmter Drucker
    if printer_id:
        stmt = stmt.where(Spool.printer_id == printer_id)

    # Suchterm (sucht in Nummer, Name, Vendor, Farbe)
    if term:
        search_pattern = f"%{term}%"

        # Prüfe ob term eine Zahl ist (exakte Nummern-Suche)
        if term.isdigit():
            term_int = int(term)
            stmt = stmt.where(
                or_(
                    Spool.spool_number == term_int,
                    Spool.name.like(search_pattern),
                    Spool.vendor.like(search_pattern),
                    Spool.color.like(search_pattern)
                )
            )
        else:
            # Text-Suche
            stmt = stmt.where(
                or_(
                    Spool.name.like(search_pattern),
                    Spool.vendor.like(search_pattern),
                    Spool.color.like(search_pattern)
                )
            )

    # Sortierung nach Nummer
    stmt = stmt.order_by(Spool.spool_number)

    spools = session.exec(stmt).all()
    return [SpoolReadSchema.model_validate(s) for s in spools]


# === AMS-ZUWEISUNG ===

class AssignRequest(BaseModel):
    printer_id: str
    slot_number: int


@router.post("/{spool_number}/assign")
def assign_to_slot(
    spool_number: int,
    data: AssignRequest,
    session: Session = Depends(get_session)
):
    """
    Weist Spule manuell einem AMS-Slot zu

    Body:
        {
            "printer_id": "uuid",
            "slot_number": 1-4
        }

    Returns:
        {
            "spool_number": 7,
            "printer_id": "uuid",
            "slot": 2,
            "assigned": true
        }

    Raises:
        400: Ungültiger Slot (nicht 1-4)
        404: Spule nicht gefunden
        409: Spule bereits zugewiesen ODER Slot bereits belegt
    """
    # Validierung: Slot 1-4
    if data.slot_number not in [1, 2, 3, 4]:
        raise HTTPException(
            status_code=400,
            detail="Slot muss 1-4 sein"
        )

    # Finde Spule
    spool = session.exec(
        select(Spool).where(Spool.spool_number == spool_number)
    ).first()

    if not spool:
        raise HTTPException(
            status_code=404,
            detail=f"Spule #{spool_number} nicht gefunden"
        )

    # Prüfe ob Spule bereits zugewiesen
    if spool.printer_id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Spule #{spool_number} ist bereits Drucker '{spool.printer_id}' "
                f"Slot {spool.ams_slot} zugewiesen"
            )
        )

    # Prüfe ob Slot frei
    existing = session.exec(
        select(Spool).where(
            Spool.printer_id == data.printer_id,
            Spool.ams_slot == data.slot_number
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Slot {data.slot_number} ist bereits mit Spule #{existing.spool_number} belegt"
        )

    # Prüfe ob Drucker existiert
    printer = session.get(Printer, data.printer_id)
    if not printer:
        raise HTTPException(
            status_code=404,
            detail=f"Drucker {data.printer_id} nicht gefunden"
        )

    # Zuweisen
    spool.printer_id = data.printer_id
    spool.ams_slot = data.slot_number
    spool.updated_at = datetime.utcnow().isoformat()

    # Status-Logik: Nur wenn Spule manuell erstellt wurde (hat spool_number)
    # UND noch nie im AMS war (used_count = 0 oder None)
    # → Warte auf ersten Druck, dann wird Status auf "Aktiv" gesetzt
    # (Status-Änderung erfolgt in mqtt_routes.py beim Job-Start)

    session.add(spool)
    session.commit()
    session.refresh(spool)

    return {
        "spool_number": spool.spool_number,
        "printer_id": data.printer_id,
        "printer_name": printer.name if printer else None,
        "slot": data.slot_number,
        "assigned": True
    }


@router.post("/{spool_number}/unassign")
def unassign_from_slot(
    spool_number: int,
    session: Session = Depends(get_session)
):
    """
    Entfernt Spule von AMS-Slot

    Returns:
        {
            "spool_number": 7,
            "assigned": false,
            "previous_slot": 2
        }

    Raises:
        404: Spule nicht gefunden
    """
    spool = session.exec(
        select(Spool).where(Spool.spool_number == spool_number)
    ).first()

    if not spool:
        raise HTTPException(
            status_code=404,
            detail=f"Spule #{spool_number} nicht gefunden"
        )

    last_slot = spool.ams_slot

    # Entfernen
    spool.printer_id = None
    spool.ams_slot = None
    spool.last_slot = last_slot  # Merke letzten Slot
    spool.updated_at = datetime.utcnow().isoformat()

    # Status-Logik: Spule zurück ins Lager
    # Nur für manuell angelegte Spulen mit Nummer
    if spool.spool_number:
        # NUR wenn Spule NICHT leer ist
        if not spool.is_empty and spool.status == "Aktiv":
            spool.status = "Lager"
            # is_open bleibt True, da Spule bereits geöffnet wurde
        # Wenn is_empty = True → Status bleibt unverändert (z.B. "Leer")

    session.add(spool)
    session.commit()

    return {
        "spool_number": spool.spool_number,
        "assigned": False,
        "previous_slot": last_slot
    }


# === DRUCKER-SPULEN ===

@router.get("/printer/{printer_id}/slots")
def get_printer_slots(
    printer_id: str,
    session: Session = Depends(get_session)
):
    """
    Gibt alle AMS-Slots eines Druckers zurück (1-4)

    Zeigt auch leere Slots an für bessere UI-Darstellung.

    Returns:
        {
            "slots": [
                {
                    "slot": 1,
                    "spool": {...},  # oder null wenn leer
                    "empty": false
                },
                ...
            ]
        }
    """
    # Prüfe ob Drucker existiert
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(
            status_code=404,
            detail=f"Drucker {printer_id} nicht gefunden"
        )

    # Hole zugewiesene Spulen
    spools = session.exec(
        select(Spool)
        .where(Spool.printer_id == printer_id)
        .order_by(Spool.ams_slot)
    ).all()

    # Erstelle Slot-Array (1-4)
    slots = []
    for slot_num in [1, 2, 3, 4]:
        slot_spool = next(
            (s for s in spools if s.ams_slot == slot_num),
            None
        )

        if slot_spool:
            slots.append({
                "slot": slot_num,
                "spool": SpoolReadSchema.model_validate(slot_spool),
                "empty": False
            })
        else:
            slots.append({
                "slot": slot_num,
                "spool": None,
                "empty": True
            })

    return {"slots": slots}
