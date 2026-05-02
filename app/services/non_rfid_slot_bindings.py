from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.non_rfid_slot_binding import NonRfidSlotBinding
from app.services.ams_identity import normalize_feeder_key


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _ensure_table(session: Session) -> None:
    session.exec(text("""
        CREATE TABLE IF NOT EXISTS non_rfid_slot_binding (
            id TEXT PRIMARY KEY,
            printer_id TEXT NOT NULL,
            feeder_key TEXT NOT NULL,
            slot_index INTEGER NOT NULL,
            spool_id TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        )
    """))
    session.exec(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_non_rfid_slot_binding_slot
        ON non_rfid_slot_binding(printer_id, feeder_key, slot_index)
    """))
    session.exec(text("""
        CREATE INDEX IF NOT EXISTS ix_non_rfid_slot_binding_spool
        ON non_rfid_slot_binding(spool_id)
    """))


def get_non_rfid_binding(
    session: Session,
    *,
    printer_id: Optional[str],
    feeder_key: Optional[str],
    slot_index: Optional[int],
) -> Optional[NonRfidSlotBinding]:
    _ensure_table(session)
    if not printer_id or feeder_key is None or slot_index is None:
        return None
    normalized_key = normalize_feeder_key(None, feeder_key)
    stmt = select(NonRfidSlotBinding).where(
        NonRfidSlotBinding.printer_id == printer_id,
        NonRfidSlotBinding.feeder_key == normalized_key,
        NonRfidSlotBinding.slot_index == int(slot_index),
    )
    binding = session.exec(stmt).first()
    if binding:
        return binding

    candidates = session.exec(
        select(NonRfidSlotBinding).where(
            NonRfidSlotBinding.printer_id == printer_id,
            NonRfidSlotBinding.slot_index == int(slot_index),
        )
    ).all()
    for candidate in candidates:
        if normalize_feeder_key(None, candidate.feeder_key) == normalized_key:
            return candidate
    return None


def upsert_non_rfid_binding(
    session: Session,
    *,
    printer_id: str,
    feeder_key: str,
    slot_index: int,
    spool_id: str,
) -> NonRfidSlotBinding:
    _ensure_table(session)
    normalized_key = normalize_feeder_key(None, feeder_key)
    binding = get_non_rfid_binding(
        session,
        printer_id=printer_id,
        feeder_key=normalized_key,
        slot_index=slot_index,
    )
    now = _now_iso()
    if binding is None:
        binding = NonRfidSlotBinding(
            printer_id=printer_id,
            feeder_key=normalized_key,
            slot_index=int(slot_index),
            spool_id=spool_id,
            created_at=now,
            updated_at=now,
        )
    else:
        binding.feeder_key = normalized_key
        binding.spool_id = spool_id
        binding.updated_at = now
    session.add(binding)
    duplicates = session.exec(
        select(NonRfidSlotBinding).where(
            NonRfidSlotBinding.printer_id == printer_id,
            NonRfidSlotBinding.slot_index == int(slot_index),
        )
    ).all()
    for duplicate in duplicates:
        if duplicate.id == binding.id:
            continue
        if normalize_feeder_key(None, duplicate.feeder_key) == normalized_key:
            session.delete(duplicate)
    return binding


def clear_non_rfid_binding_for_slot(
    session: Session,
    *,
    printer_id: Optional[str],
    feeder_key: Optional[str],
    slot_index: Optional[int],
) -> None:
    _ensure_table(session)
    normalized_key = normalize_feeder_key(None, feeder_key)
    if not printer_id or normalized_key is None or slot_index is None:
        return
    duplicates = session.exec(
        select(NonRfidSlotBinding).where(
            NonRfidSlotBinding.printer_id == printer_id,
            NonRfidSlotBinding.slot_index == int(slot_index),
        )
    )
    for binding in duplicates:
        if normalize_feeder_key(None, binding.feeder_key) == normalized_key:
            session.delete(binding)


def clear_non_rfid_bindings_for_spool(session: Session, spool_id: Optional[str]) -> None:
    _ensure_table(session)
    if not spool_id:
        return
    stmt = select(NonRfidSlotBinding).where(NonRfidSlotBinding.spool_id == spool_id)
    for binding in session.exec(stmt).all():
        session.delete(binding)
