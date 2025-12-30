"""Service to manage AMS assignments for spools.

Functions:
- assign_spool_manual(spool_id, ams_id, slot)
- assign_spool_rfid(spool_id, ams_id, slot)
- remove_spool_from_ams(spool_id)

These functions are additive and intentionally avoid changing unrelated logic.
"""
from typing import Optional
from sqlmodel import Session, select
from app.models.spool import Spool
from app.database import get_session


def _get_session(provided_session: Optional[Session] = None) -> Session:
    if provided_session is not None:
        return provided_session
    return next(get_session())


def assign_spool_manual(spool_id: str, ams_id: str, slot: int, session=None) -> None:
    """Assign a spool to an AMS slot as a manual assignment.

    Removes any existing spool in the target slot (ams_id + slot) by clearing
    its ams fields and assigned flag, then assigns the given spool.
    """
    session = _get_session(session)

    # Clear existing spool in that slot
    existing = session.exec(
        select(Spool).where(Spool.ams_id == ams_id, Spool.ams_slot == slot, Spool.is_active == True)
    ).first()
    if existing and existing.id != spool_id:
        existing.ams_id = None
        existing.ams_slot = None
        existing.ams_source = None
        existing.assigned = False
        session.add(existing)

    # Assign new spool
    spool = session.get(Spool, spool_id)
    if spool:
        spool.ams_id = ams_id
        spool.ams_slot = slot
        spool.ams_source = "manual"
        spool.assigned = True
        spool.is_active = True
        session.add(spool)

    session.commit()


def assign_spool_rfid(spool_id: str, ams_id: str, slot: int, session=None) -> None:
    """Assign a spool to an AMS slot detected by RFID.

    Removes any existing RFID spool in the target slot, then assigns this RFID spool.
    """
    session = _get_session(session)

    existing = session.exec(
        select(Spool).where(Spool.ams_id == ams_id, Spool.ams_slot == slot, Spool.is_active == True)
    ).first()
    if existing and existing.id != spool_id:
        # If existing is RFID or manual, we remove its AMS info to make room
        existing.ams_id = None
        existing.ams_slot = None
        existing.ams_source = None
        existing.assigned = False
        session.add(existing)

    spool = session.get(Spool, spool_id)
    if spool:
        spool.ams_id = ams_id
        spool.ams_slot = slot
        spool.ams_source = "rfid"
        spool.assigned = True
        spool.is_active = True
        session.add(spool)

    session.commit()


def remove_spool_from_ams(spool_id: str, session=None) -> None:
    """Remove AMS assignment from a spool (clear fields and flags)."""
    session = _get_session(session)
    spool = session.get(Spool, spool_id)
    if not spool:
        return
    spool.ams_id = None
    spool.ams_slot = None
    spool.ams_source = None
    spool.assigned = False
    session.add(spool)
    session.commit()
