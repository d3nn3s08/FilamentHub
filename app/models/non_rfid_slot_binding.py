from typing import Optional
from uuid import uuid4

from sqlmodel import SQLModel, Field as SQLField


class NonRfidSlotBinding(SQLModel, table=True):
    __tablename__ = "non_rfid_slot_binding"
    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True)
    printer_id: str
    feeder_key: str
    slot_index: int
    spool_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
