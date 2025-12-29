from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4


class MaterialBase(SQLModel):
    name: str
    brand: Optional[str] = None
    density: float = 1.24  # g/cm³, Standard PLA
    diameter: float = 1.75  # mm
    notes: Optional[str] = None
    external_id: Optional[str] = None  # Für Cloud/AMS
    printer_slot: Optional[int] = None  # Für spätere Slot-Zuordnung
    created_at: Optional[str] = None  # ISO-Timestamp
    updated_at: Optional[str] = None  # ISO-Timestamp


class Material(MaterialBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)



# Pydantic-Schemas
from pydantic import BaseModel, Field, ConfigDict, field_validator

class MaterialCreateSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str
    brand: str | None = Field(None, alias="manufacturer")
    density: float = Field(1.24, gt=0)
    diameter: float = Field(1.75, ge=1.5, le=3.0)
    notes: str | None = None
    external_id: str | None = None
    printer_slot: int | str | None = None
    material_type: str | None = Field(None, alias="type")

    @field_validator("name")
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name darf nicht leer sein")
        return v.strip()

    @field_validator("printer_slot")
    def normalize_printer_slot(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        digits = "".join(filter(str.isdigit, str(v)))
        return int(digits) if digits else None

class MaterialUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str | None = None
    brand: str | None = Field(None, alias="manufacturer")
    density: float | None = Field(None, gt=0)
    diameter: float | None = Field(None, ge=1.5, le=3.0)
    notes: str | None = None
    external_id: str | None = None
    printer_slot: int | str | None = None
    material_type: str | None = Field(None, alias="type")

class MaterialReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    brand: str | None = None
    density: float
    diameter: float
    notes: str | None = None
    external_id: str | None = None
    printer_slot: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
