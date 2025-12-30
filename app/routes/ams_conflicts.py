from fastapi import APIRouter, Body, HTTPException
from sqlmodel import Session, select
from sqlalchemy import or_
from app.database import get_session
from app.models.ams_conflict import AmsConflict
from app.models.spool import Spool
from services.ams_assignment_service import remove_spool_from_ams, assign_spool_rfid

router = APIRouter(prefix="/api/ams/conflict", tags=["ams"])


@router.post("/confirm")
def confirm_conflict(body: dict = Body(...)):
    ams_id = body.get("ams_id")
    slot = body.get("slot")
    manual_spool_id = body.get("manual_spool_id")
    rfid_spool_id = body.get("rfid_spool_id")

    if not (ams_id and slot is not None and manual_spool_id and rfid_spool_id):
        raise HTTPException(status_code=400, detail="Missing required fields")

    session = next(get_session())
    try:
        # Remove manual spool assignment
        remove_spool_from_ams(manual_spool_id, session=session)
        # Assign RFID spool
        assign_spool_rfid(rfid_spool_id, ams_id, slot, session=session)

        # mark any existing open conflict for this slot as confirmed
        # tolerant matching for ams_id formats
        # build candidate ams_id variants (original, str, prefixed, digits)
        try:
            raw = str(ams_id)
            digits = "".join(ch for ch in raw if ch.isdigit())
            candidates = {raw, str(ams_id), f"AMS{ams_id}", digits or None}
            candidates = [c for c in candidates if c]
            or_clause = None
            from sqlalchemy import or_ as _or
            clauses = [_or(AmsConflict.ams_id == c) for c in candidates]
            conflict = session.exec(
                select(AmsConflict).where(
                    AmsConflict.slot == slot,
                    AmsConflict.status == "open",
                    _or(*[AmsConflict.ams_id == c for c in candidates])
                )
            ).first()
        except Exception:
            conflict = session.exec(
                select(AmsConflict).where(AmsConflict.ams_id == ams_id, AmsConflict.slot == slot, AmsConflict.status == "open")
            ).first()
        if conflict:
            conflict.status = "confirmed"
            session.add(conflict)
            session.commit()

        return {"status": "ok"}
    finally:
        session.close()


@router.post("/cancel")
def cancel_conflict(body: dict = Body(...)):
    ams_id = body.get("ams_id")
    slot = body.get("slot")
    if not (ams_id and slot is not None):
        raise HTTPException(status_code=400, detail="Missing required fields")

    session = next(get_session())
    try:
        try:
            raw = str(ams_id)
            digits = "".join(ch for ch in raw if ch.isdigit())
            candidates = {raw, str(ams_id), f"AMS{ams_id}", digits or None}
            candidates = [c for c in candidates if c]
            from sqlalchemy import or_ as _or
            conflict = session.exec(
                select(AmsConflict).where(
                    AmsConflict.slot == slot,
                    AmsConflict.status == "open",
                    _or(*[AmsConflict.ams_id == c for c in candidates])
                )
            ).first()
        except Exception:
            conflict = session.exec(
                select(AmsConflict).where(AmsConflict.ams_id == ams_id, AmsConflict.slot == slot, AmsConflict.status == "open")
            ).first()
        if conflict:
            conflict.status = "cancelled"
            session.add(conflict)
            session.commit()
        return {"status": "ok"}
    finally:
        session.close()


@router.get("/open")
def get_open_conflicts():
    """Return list of open AMS conflicts."""
    session = next(get_session())
    try:
        conflicts = session.exec(select(AmsConflict).where(AmsConflict.status == "open")).all()
        result = []
        for c in conflicts:
            item = {
                "id": c.id,
                "ams_id": c.ams_id,
                "slot": c.slot,
                "manual_spool_id": c.manual_spool_id,
                "rfid_payload": c.rfid_payload,
                "status": c.status,
                "rfid_spool_id": None,
            }
            # Try to resolve RFID to an existing spool id (best-effort)
            try:
                import json as _json
                payload = _json.loads(c.rfid_payload) if c.rfid_payload else {}
                tray_uuid = payload.get("tray_uuid") or payload.get("tray_uuid")
                if tray_uuid:
                    from app.models.spool import Spool
                    existing = session.exec(select(Spool).where((Spool.rfid_chip_id == tray_uuid) | (Spool.tray_uuid == tray_uuid))).first()
                    if existing:
                        item["rfid_spool_id"] = existing.id
            except Exception:
                pass
            result.append(item)
        return result
    finally:
        session.close()
