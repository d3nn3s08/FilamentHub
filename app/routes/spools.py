from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import select, Session
from typing import List

from app.database import get_session
from app.models.spool import Spool, SpoolCreateSchema, SpoolUpdateSchema, SpoolReadSchema
from app.services.spool_number_service import assign_spool_number

router = APIRouter(prefix="/api/spools", tags=["Spools"])

def _normalize_spool_payload(data: SpoolCreateSchema | SpoolUpdateSchema, *, is_update: bool = False) -> dict:
    payload = data.model_dump(exclude_unset=True)
    # Color wird jetzt persistiert (Teil des Nummern-Systems)
    # payload.pop("color", None) - ENTFERNT
    # alias weight -> weight_current
    if "weight" in payload:
        payload["weight_current"] = payload.pop("weight")
    # normalize printer_slot strings like "AMS-2"
    slot = payload.get("printer_slot")
    if isinstance(slot, str):
        digits = "".join(filter(str.isdigit, slot))
        payload["printer_slot"] = int(digits) if digits else None
    ams_slot = payload.get("ams_slot")
    if isinstance(ams_slot, str):
        digits = "".join(filter(str.isdigit, ams_slot))
        payload["ams_slot"] = int(digits) if digits else None
    if not is_update:
        payload.setdefault("weight_full", 1000)
        payload.setdefault("weight_empty", 250)
        # Falls kein aktuelles Gewicht explizit gesetzt wurde, auf weight_full setzen
        if payload.get("weight_current") is None:
            payload["weight_current"] = payload.get("weight_full")
        # Neue Spulen: remain_percent auf 100% setzen (nicht leer)
        if payload.get("remain_percent") is None:
            payload["remain_percent"] = 100.0
        # Neue Spulen: is_open auf True setzen (geöffnet)
        if "is_open" not in payload:
            payload["is_open"] = True
    return payload


@router.get("/", response_model=List[SpoolReadSchema])
def list_spools(session: Session = Depends(get_session)):
    result = session.exec(select(Spool)).all()
    return [SpoolReadSchema.model_validate(s) for s in result]


@router.get("/unnumbered", response_model=List[SpoolReadSchema])
def list_unnumbered_spools(session: Session = Depends(get_session)):
    """
    Gibt alle Spulen zurück, die KEINE Nummer haben

    Nützlich für Benachrichtigungen: "Neue Spule im AMS erkannt - Bitte Nummer vergeben"
    """
    stmt = select(Spool).where(Spool.spool_number.is_(None))
    result = session.exec(stmt).all()
    return [SpoolReadSchema.model_validate(s) for s in result]


@router.get("/{spool_id}", response_model=SpoolReadSchema)
def get_spool(spool_id: str, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    return SpoolReadSchema.model_validate(spool)


@router.post("/", response_model=SpoolReadSchema, status_code=status.HTTP_201_CREATED)
def create_spool(data: SpoolCreateSchema, session: Session = Depends(get_session)):
    # Prüfe auf Duplikate nur wenn label gesetzt ist
    if data.label:
        exists = session.exec(select(Spool).where(Spool.label == data.label, Spool.material_id == data.material_id)).first()
        if exists:
            raise HTTPException(status_code=409, detail="Spule mit dieser Bezeichnung existiert bereits")
    try:
        payload = _normalize_spool_payload(data)
        spool = Spool(**payload)

        # NEU: Automatisch Spulen-Nummer zuweisen
        assign_spool_number(spool, session)

        session.add(spool)
        session.commit()
        session.refresh(spool)
        return SpoolReadSchema.model_validate(spool)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Validierung: {e}")


@router.put("/{spool_id}", response_model=SpoolReadSchema)
def update_spool(spool_id: str, data: SpoolUpdateSchema, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    update_data = _normalize_spool_payload(data, is_update=True)
    for key, value in update_data.items():
        setattr(spool, key, value)

    # AUTOMATISCHE NUMMERN-FREIGABE: Wenn Spule leer wird, Nummer entfernen
    if spool.is_empty and spool.spool_number is not None:
        spool.spool_number = None

    try:
        session.add(spool)
        session.commit()
        session.refresh(spool)
        return SpoolReadSchema.model_validate(spool)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Validierung: {e}")


@router.delete("/{spool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spool(spool_id: str, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    session.delete(spool)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
