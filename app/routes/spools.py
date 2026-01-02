from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import select, Session, col
from typing import List

from app.database import get_session
import app.services.live_state as live_state_module
from app.models.printer import Printer
from app.models.spool import Spool, SpoolCreateSchema, SpoolUpdateSchema, SpoolReadSchema
from app.models.material import Material
from app.services.spool_number_service import assign_spool_number
from app.services.ams_normalizer import device_has_real_ams_from_live_state
from app.services.filament_weights import compute_spool_remaining

router = APIRouter(prefix="/api/spools", tags=["Spools"])


def _is_bambu_material(material: Material | None) -> bool:
    return bool(material and material.is_bambu is True)


def _get_material(session: Session, material_id: str | None, cache: dict[str, Material]) -> Material | None:
    if not material_id:
        return None
    if material_id in cache:
        return cache[material_id]
    material = session.get(Material, material_id)
    if material:
        cache[material_id] = material
    return material

def _normalize_spool_payload(
    data: SpoolCreateSchema | SpoolUpdateSchema,
    session: Session,
    *,
    is_update: bool = False,
    spool: Spool | None = None,
) -> dict:
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
    material_cache: dict[str, Material] = {}
    material_id = payload.get("material_id") or (spool.material_id if spool else None)
    material = _get_material(session, material_id, material_cache)
    is_bambu = _is_bambu_material(material)

    if is_bambu and material:
        if material.spool_weight_full is not None:
            payload["weight_full"] = material.spool_weight_full
        if material.spool_weight_empty is not None:
            payload["weight_empty"] = material.spool_weight_empty

    if not is_update and not is_bambu:
        payload.setdefault("weight_full", 750)
        payload.setdefault("weight_empty", 20)
        # Falls kein aktuelles Gewicht explizit gesetzt wurde, auf weight_full setzen
        if payload.get("weight_current") is None:
            payload["weight_current"] = payload.get("weight_full")
        # Neue Spulen: is_open auf True setzen (geoeffnet)
        if "is_open" not in payload:
            payload["is_open"] = True
    return payload


@router.get("/", response_model=List[SpoolReadSchema])
def list_spools(session: Session = Depends(get_session)):
    result = session.exec(select(Spool)).all()
    material_cache: dict[str, Material] = {}
    return [_serialize_spool(s, session, material_cache) for s in result]


@router.get("/unnumbered", response_model=List[SpoolReadSchema])
def list_unnumbered_spools(session: Session = Depends(get_session)):
    """
    Gibt alle Spulen zurück, die KEINE Nummer haben

    Nützlich für Benachrichtigungen: "Neue Spule im AMS erkannt - Bitte Nummer vergeben"
    """
    stmt = select(Spool).where(col(Spool.spool_number).is_(None))
    result = session.exec(stmt).all()
    return [SpoolReadSchema.model_validate(s) for s in result]


@router.get("/{spool_id}", response_model=SpoolReadSchema)
def get_spool(spool_id: str, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    material_cache: dict[str, Material] = {}
    return _serialize_spool(spool, session, material_cache)


@router.post("/", response_model=SpoolReadSchema, status_code=status.HTTP_201_CREATED)
def create_spool(data: SpoolCreateSchema, session: Session = Depends(get_session)):
    # Prüfe auf Duplikate nur wenn label gesetzt ist
    if data.label:
        exists = session.exec(select(Spool).where(Spool.label == data.label, Spool.material_id == data.material_id)).first()
        if exists:
            raise HTTPException(status_code=409, detail="Spule mit dieser Bezeichnung existiert bereits")
    try:
        payload = _normalize_spool_payload(data, session)
        spool = Spool(**payload)

        # NEU: Automatisch Spulen-Nummer zuweisen
        assign_spool_number(spool, session)

        session.add(spool)
        session.commit()
        session.refresh(spool)
        material_cache: dict[str, Material] = {}
        return _serialize_spool(spool, session, material_cache)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Validierung: {e}")


@router.put("/{spool_id}", response_model=SpoolReadSchema)
def update_spool(spool_id: str, data: SpoolUpdateSchema, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    update_data = _normalize_spool_payload(data, session, is_update=True, spool=spool)
    # Schutz: Nummer darf nur freigegeben werden, wenn Spule leer ist
    if "spool_number" in update_data and update_data.get("spool_number") is None:
        next_is_empty = update_data.get("is_empty", spool.is_empty)
        if not next_is_empty:
            update_data.pop("spool_number", None)
    for key, value in update_data.items():
        setattr(spool, key, value)

    # AUTOMATISCHE NUMMERN-FREIGABE: Wenn Spule leer wird, Nummer entfernen
    if spool.is_empty and spool.spool_number is not None:
        spool.spool_number = None

    try:
        session.add(spool)
        session.commit()
        session.refresh(spool)
        material_cache: dict[str, Material] = {}
        return _serialize_spool(spool, session, material_cache)
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

    material_cache: dict[str, Material] = {}
    return _serialize_spool(spool, session, material_cache)


@router.post("/{spool_id}/unassign", response_model=SpoolReadSchema)
def unassign_spool(spool_id: str, session: Session = Depends(get_session)):
    """
    Entfernt eine Spule aus einem AMS-Slot
    
    WICHTIG: weight_current bleibt IMMER erhalten.
    AMS ist eine Live-Datenquelle, kein Eigentümer der Spule.

    POST /api/spools/{spool_id}/unassign
    """
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")

    # Merke letzten Slot
    if spool.ams_slot is not None:
        spool.last_slot = spool.ams_slot

    # Entferne AMS-Zuweisung
    spool.printer_id = None
    spool.ams_slot = None
    spool.ams_source = None
    spool.assigned = False

    # Status-Logik: Spule zurück ins Lager
    # Wenn Spule nicht leer ist und Status "Aktiv" war, zurück auf "Lager" setzen
    if not spool.is_empty and spool.status == "Aktiv":
        spool.status = "Lager"
        # is_open bleibt True, da Spule bereits geöffnet wurde

    # weight_current NICHT ändern - bleibt erhalten!
    # Das garantiert, dass das Lager den letzten bekannten Filamentwert zeigt

    session.add(spool)
    session.commit()
    session.refresh(spool)

    material_cache: dict[str, Material] = {}
    return _serialize_spool(spool, session, material_cache)


def _serialize_spool(spool: Spool, session: Session, material_cache: dict[str, Material]) -> dict:
    """
    Erzeuge die API-Repruemstentation einer Spule und berechne
    canonical Felder: remaining_weight_g, total_weight_g, remaining_percent.
    """
    # Basis-Serialization
    base = SpoolReadSchema.model_validate(spool).model_dump()

    material = _get_material(session, spool.material_id, material_cache)
    remaining, total, remaining_percent = compute_spool_remaining(spool, material)

    # Set canonical fields
    base["remaining_weight_g"] = spool.weight_current
    base["total_weight_g"] = total
    base["remaining_percent"] = remaining_percent

    # For backward compatibility keep old field if computed
    if remaining_percent is not None:
        base["remain_percent"] = remaining_percent

    return base

