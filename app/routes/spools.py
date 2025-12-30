from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, Session
from typing import List

from app.database import get_session
import app.services.live_state as live_state_module
from app.models.printer import Printer
from app.models.spool import Spool, SpoolCreateSchema, SpoolUpdateSchema, SpoolReadSchema
from app.services.spool_number_service import assign_spool_number
from app.services.ams_normalizer import device_has_real_ams_from_live_state

router = APIRouter(prefix="/api/spools", tags=["Spools"])


@router.get("/", response_model=List[SpoolRead])
def list_spools(session: Session = Depends(get_session)):
    result = session.exec(select(Spool)).all()
    return result


@router.get("/{spool_id}", response_model=SpoolRead)
def get_spool(spool_id: str, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    return spool


@router.post("/", response_model=SpoolRead)
def create_spool(data: SpoolCreate, session: Session = Depends(get_session)):
    spool = Spool.from_orm(data)
    session.add(spool)
    session.commit()
    session.refresh(spool)
    return spool


@router.put("/{spool_id}", response_model=SpoolRead)
def update_spool(spool_id: str, data: SpoolCreate, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(spool, key, value)

    session.add(spool)
    session.commit()
    session.refresh(spool)
    return spool


@router.delete("/{spool_id}")
def delete_spool(spool_id: str, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    session.delete(spool)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{spool_id}/assign", response_model=SpoolReadSchema)
def assign_spool_to_slot(
    spool_id: str,
    printer_id: str,
    slot_number: int,
    session: Session = Depends(get_session)
):
    """
    Weist eine Spule einem AMS-Slot zu

    POST /api/spools/{spool_id}/assign?printer_id=xxx&slot_number=1
    """
    # Validierung: Slot muss 1-4 sein
    if slot_number not in [1, 2, 3, 4]:
        raise HTTPException(status_code=400, detail="Slot muss 1-4 sein")

    # Finde Spule
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")

    # Prüfe: Drucker/AMS existiert und ist im Live-State vorhanden
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail=f"Drucker {printer_id} nicht gefunden")
    # Wenn kein cloud_serial (AMS Identifikator) vorhanden, keine manuelle AMS-Zuweisung erlauben
    if not printer.cloud_serial:
        raise HTTPException(status_code=400, detail="Manuelle Zuweisung erfordert einen konfigurierten AMS (cloud_serial fehlt)")
    # Prüfe über den Normalizer, ob das Gerät laut Live-Payload ein echtes AMS hat
    if not device_has_real_ams_from_live_state(printer.cloud_serial):
        raise HTTPException(status_code=400, detail="Manuelle Zuweisung erfordert ein echtes AMS (kein AMS erkannt)")

    # Prüfe ob Spule bereits zugewiesen
    if spool.printer_id is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Spule ist bereits Drucker '{spool.printer_id}' Slot {spool.ams_slot} zugewiesen"
        )

    # Prüfe ob Slot frei
    stmt = select(Spool).where(
        Spool.printer_id == printer_id,
        Spool.ams_slot == slot_number
    )
    existing = session.exec(stmt).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Slot {slot_number} ist bereits mit Spule belegt"
        )

    # Zuweisen
    spool.printer_id = printer_id
    spool.ams_slot = slot_number

    session.add(spool)
    session.commit()
    session.refresh(spool)

    return _serialize_spool(spool)


@router.post("/{spool_id}/unassign", response_model=SpoolReadSchema)
def unassign_spool(spool_id: str, session: Session = Depends(get_session)):
    """
    Entfernt eine Spule aus einem AMS-Slot

    POST /api/spools/{spool_id}/unassign
    """
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")

    # Merke letzten Slot
    if spool.ams_slot is not None:
        spool.last_slot = spool.ams_slot

    # Entferne Zuweisung
    spool.printer_id = None
    spool.ams_slot = None

    # Status-Logik: Spule zurück ins Lager
    # Wenn Spule nicht leer ist und Status "Aktiv" war, zurück auf "Lager" setzen
    if not spool.is_empty and spool.status == "Aktiv":
        spool.status = "Lager"
        # is_open bleibt True, da Spule bereits geöffnet wurde

    session.add(spool)
    session.commit()
    session.refresh(spool)

    return _serialize_spool(spool)


def _serialize_spool(spool: Spool) -> dict:
    """
    Erzeuge die API-Repräsentation einer Spule und berechne
    canonical Felder: remaining_weight_g, total_weight_g, remaining_percent.
    """
    # Basis-Serialization
    base = SpoolReadSchema.model_validate(spool).model_dump()

    # Berechne total und remaining (in Gramm) falls möglich
    try:
        wf = float(spool.weight_full) if spool.weight_full is not None else None
        we = float(spool.weight_empty) if spool.weight_empty is not None else None
        wc = float(spool.weight_current) if spool.weight_current is not None else None
    except Exception:
        wf = we = wc = None

    total = None
    remaining = None
    if wf is not None and we is not None:
        total = wf - we
        if wc is not None:
            remaining = wc - we

    remaining_percent = None
    if remaining is not None and total and total > 0:
        remaining_percent = round(max(0.0, min(100.0, (remaining / total) * 100.0)), 1)

    # Set canonical fields
    base["remaining_weight_g"] = remaining
    base["total_weight_g"] = total
    base["remaining_percent"] = remaining_percent

    # Für Abwärtskompatibilität auch das alte Feld setzen, aber nur wenn berechnet
    if remaining_percent is not None:
        base["remain_percent"] = remaining_percent

    return base
