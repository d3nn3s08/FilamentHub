from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4


class SpoolBase(SQLModel):
    material_id: str = Field(foreign_key="material.id")
    vendor_id: Optional[str] = None  # optional
    weight_full: float = 1000  # g, Filament ohne Leerspule
    weight_empty: float = 250  # g, nur Leerspule
    weight_current: Optional[float] = None  # aktuelles Gewicht
    status: Optional[str] = None  # z.B. "voll", "angebrochen", "leer"
    location: Optional[str] = None  # Lagerort
    label: Optional[str] = None  # Nutzerdefinierter Name
    external_id: Optional[str] = None  # Für Cloud/AMS
    printer_id: Optional[str] = Field(default=None, foreign_key="printer.id")
    printer_slot: Optional[int] = None  # Historisch
    ams_slot: Optional[int] = None  # AMS-Slot (0-3)
    tag_uid: Optional[str] = None  # RFID/Tag UID aus AMS
    tray_uuid: Optional[str] = None  # AMS tray_uuid
    tray_color: Optional[str] = None  # Hex
    tray_type: Optional[str] = None  # Material-Typ (PLA, ABS, ...)
    remain_percent: Optional[float] = None  # Rest laut AMS (%)
    last_seen: Optional[str] = None  # ISO-Timestamp der letzten Meldung
    created_at: Optional[str] = None  # ISO-Timestamp
    updated_at: Optional[str] = None  # ISO-Timestamp


class Spool(SpoolBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)



# Pydantic-Schemas
from pydantic import BaseModel, Field, ConfigDict, field_validator

class SpoolCreateSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    material_id: str
    vendor_id: str | None = Field(None, alias="manufacturer")
    weight: float | None = Field(None, gt=0)
    weight_full: float = Field(1000, gt=0)
    weight_empty: float = Field(250, gt=0)
    weight_current: float | None = Field(None, gt=0)
    status: str | None = None
    location: str | None = None
    label: str | None = None
    external_id: str | None = None
    printer_slot: int | str | None = None
    ams_slot: int | str | None = None
    printer_id: str | None = None
    tag_uid: str | None = None
    tray_uuid: str | None = None
    tray_color: str | None = None
    tray_type: str | None = None
    remain_percent: float | None = None
    last_seen: str | None = None
    color: str | None = None  # aktuell nicht persistiert

    @field_validator("material_id")
    def material_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("material_id darf nicht leer sein")
        return v.strip()

    @field_validator("printer_slot")
    def normalize_printer_slot(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        digits = "".join(filter(str.isdigit, str(v)))
        return int(digits) if digits else None

    @field_validator("ams_slot")
    def normalize_ams_slot(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        digits = "".join(filter(str.isdigit, str(v)))
        return int(digits) if digits else None

class SpoolUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    material_id: str | None = None
    vendor_id: str | None = Field(None, alias="manufacturer")
    weight: float | None = Field(None, gt=0)
    weight_full: float | None = Field(None, gt=0)
    weight_empty: float | None = Field(None, gt=0)
    weight_current: float | None = Field(None, gt=0)
    status: str | None = None
    location: str | None = None
    label: str | None = None
    external_id: str | None = None
    printer_slot: int | str | None = None
    ams_slot: int | str | None = None
    printer_id: str | None = None
    tag_uid: str | None = None
    tray_uuid: str | None = None
    tray_color: str | None = None
    tray_type: str | None = None
    remain_percent: float | None = None
    last_seen: str | None = None
    color: str | None = None

    @field_validator("material_id")
    def material_id_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("material_id darf nicht leer sein")
        return v.strip()

    @field_validator("printer_slot")
    def normalize_printer_slot_update(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        digits = "".join(filter(str.isdigit, str(v)))
        return int(digits) if digits else None

    @field_validator("ams_slot")
    def normalize_ams_slot_update(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        digits = "".join(filter(str.isdigit, str(v)))
        return int(digits) if digits else None

class SpoolReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    material_id: str
    vendor_id: str | None = Field(None, serialization_alias="manufacturer")
    weight_full: float
    weight_empty: float
    weight_current: float | None = Field(None, serialization_alias="weight")
    status: str | None = None
    location: str | None = None
    label: str | None = None
    external_id: str | None = None
    printer_slot: int | None = None
    ams_slot: int | None = None
    printer_id: str | None = None
    tag_uid: str | None = None
    tray_uuid: str | None = None
    tray_color: str | None = None
    tray_type: str | None = None
    remain_percent: float | None = None
    last_seen: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
