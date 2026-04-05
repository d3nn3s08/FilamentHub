from typing import Optional
from uuid import uuid4
from sqlmodel import SQLModel, Field


class AmsConflict(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    printer_id: Optional[str] = None
    ams_id: Optional[str] = None
    slot: Optional[int] = None
    manual_spool_id: Optional[str] = Field(default=None, foreign_key="spool.id")
    rfid_payload: Optional[str] = None
    status: str = "open"
    created_at: Optional[str] = None
