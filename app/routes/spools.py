from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import Response
from sqlmodel import select, Session, col
from typing import List
from pydantic import BaseModel

from app.database import get_session
import app.services.live_state as live_state_module
from app.models.printer import Printer
from app.models.spool import Spool, SpoolCreateSchema, SpoolUpdateSchema, SpoolReadSchema
from app.models.material import Material
from app.services.spool_number_service import assign_spool_number
from app.services.ams_normalizer import device_has_real_ams_from_live_state
from app.services.filament_weights import compute_fill_state, compute_spool_remaining


class LoadExternalRequest(BaseModel):
    printer_id: str

router = APIRouter(prefix="/api/spools", tags=["Spools"])

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _set_no_cache(response: Response) -> None:
    for key, value in _NO_CACHE_HEADERS.items():
        response.headers[key] = value



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
    has_rfid = bool(
        payload.get("tag_uid")
        or payload.get("tray_uuid")
        or payload.get("rfid_chip_id")
        or (spool and (spool.tag_uid or spool.tray_uuid or spool.rfid_chip_id))
    )
    is_manual = not has_rfid

    if not is_update and is_manual and not is_bambu:
        payload.setdefault("weight_full", 750)
        payload.setdefault("weight_empty", 20)
        # Nur für manuelle Spulen: Netto-Filament ermitteln
        if payload.get("weight_current") is not None:
            try:
                normalized_weight = float(payload["weight_current"])
            except Exception:
                normalized_weight = None
        else:
            weight_full = payload.get("weight_full")
            weight_empty = payload.get("weight_empty")
            if weight_full is not None and weight_empty is not None:
                normalized_weight = float(weight_full) - float(weight_empty)
            else:
                normalized_weight = None
        if normalized_weight is not None:
            payload["weight_current"] = max(0.0, normalized_weight)
        # Neue Spulen: is_open auf True setzen (geoeffnet)
        if "is_open" not in payload:
            payload["is_open"] = True
    return payload


@router.get("/", response_model=List[SpoolReadSchema])
def list_spools(response: Response, session: Session = Depends(get_session)):
    _set_no_cache(response)
    result = session.exec(select(Spool)).all()
    material_cache: dict[str, Material] = {}
    return [_serialize_spool(s, session, material_cache) for s in result]


@router.get("/unnumbered", response_model=List[SpoolReadSchema])
def list_unnumbered_spools(response: Response, session: Session = Depends(get_session)):
    """
    Gibt alle Spulen zurück, die KEINE Nummer haben

    Nützlich für Benachrichtigungen: "Neue Spule im AMS erkannt - Bitte Nummer vergeben"
    """
    _set_no_cache(response)
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


@router.put("/{spool_id}", response_model=SpoolRead)
def update_spool(spool_id: str, data: SpoolCreate, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    update_data = _normalize_spool_payload(data, session, is_update=True, spool=spool)
    # Wenn die Spule aktuell im AMS ist (ams_slot gesetzt), dann
    # dürfen nur Änderungen an `spool_number` vorgenommen werden.
    # Zusätzlich: Die Nummer darf nur einmalig gesetzt werden. Ist
    # `spool.spool_number` bereits gesetzt, darf sie nicht mehr
    # verändert werden (außer es wird der gleiche Wert erneut gesendet).
    if spool.ams_slot is not None:
        # Wenn keine spool_number im Payload, lehne alle Änderungen ab
        if "spool_number" not in update_data:
            update_data = {}
        else:
            new_num = update_data.get("spool_number")
            # Verbot: Nummer löschen während im AMS
            if new_num is None:
                raise HTTPException(status_code=400, detail="Spool-Nummer kann nicht gelöscht werden, solange Spule im AMS ist")
            # Wenn bereits eine Nummer existiert, darf sie nicht geändert werden
            if spool.spool_number is not None and int(spool.spool_number) != int(new_num):
                raise HTTPException(status_code=400, detail="Spool-Nummer darf nicht geändert werden, wenn Spule im AMS ist")
            # Erlaube nur spool_number im Update (identisch oder erstmalig)
            update_data = {"spool_number": int(new_num)}
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
    
    # WICHTIG: Entferne RFID-Verknüpfung, damit AMS-Sync diese Spule nicht mehr findet
    # Sonst würde der MQTT-Feed die Spule sofort wieder als "Aktiv" markieren
    spool.tag_uid = None
    spool.tray_uuid = None

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
    remaining_weight_g = spool.weight_current

    # Set canonical fields
    base["remaining_weight_g"] = remaining_weight_g
    base["total_weight_g"] = total
    base["remaining_percent"] = remaining_percent
    base["fill_state"] = compute_fill_state(remaining_weight_g)

    # For backward compatibility keep old field if computed
    if remaining_percent is not None:
        base["remain_percent"] = remaining_percent

    return base


@router.post("/{spool_id}/load-external")
def load_external_spool(
    spool_id: str,
    request: LoadExternalRequest,
    session: Session = Depends(get_session)
):
    """
    Lädt eine Spule als externe Spule auf einen Drucker.
    Setzt status="Aktiv" und location="external" und verknüpft mit Drucker.
    Setzt ams_slot modellabhängig (A-Serie: 254, X1/P: 255).
    """
    from app.services.spool_helpers import get_external_tray_id

    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")

    printer = session.get(Printer, request.printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Drucker nicht gefunden")

    # Externe Spulen brauchen modellabhängige Tray-ID (254 für A-Serie, 255 für X1/P)
    external_tray_id = get_external_tray_id(printer)

    # Update spool
    spool.printer_id = request.printer_id
    spool.status = "Aktiv"
    spool.location = "external"
    spool.is_open = True
    spool.ams_slot = external_tray_id  # A-Serie: 254, X1/P: 255

    session.add(spool)
    session.commit()
    session.refresh(spool)

    return {"success": True, "spool_id": spool_id, "printer_id": request.printer_id}


@router.post("/unload-external/{printer_id}")
def unload_external_spool(
    printer_id: str,
    session: Session = Depends(get_session)
):
    """
    Entlädt externe Spule von einem Drucker.
    Setzt status="Lager" und entfernt printer_id Verknüpfung.
    """
    # Finde aktive externe Spule für diesen Drucker
    spool = session.exec(
        select(Spool)
        .where(Spool.printer_id == printer_id)
        .where(Spool.status == "Aktiv")
        .where(Spool.location == "external")
    ).first()

    if not spool:
        # Kein Fehler, wenn keine Spule geladen ist
        return {"success": True, "message": "Keine externe Spule geladen"}

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

    return {"success": True, "spool_id": spool.id}
