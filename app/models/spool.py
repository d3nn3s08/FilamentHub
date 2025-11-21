from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4


class SpoolBase(SQLModel):
    material_id: str = Field(foreign_key="material.id")
    weight_full: float = 1000  # g, Filament ohne Leerspule
    weight_empty: float = 250  # g, nur Leerspule
    weight_remaining: Optional[float] = None

    label: Optional[str] = None  # Nutzerdefinierter Name
    manufacturer_spool_id: Optional[str] = None  # optional RFID/Chip
    ams_slot: Optional[int] = None

    is_open: bool = True
    is_empty: bool = False


class Spool(SpoolBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class SpoolCreate(SpoolBase):
    pass


class SpoolRead(SpoolBase):
    id: str
