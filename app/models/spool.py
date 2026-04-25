from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import SQLModel, Field as SQLField


class SpoolBase(SQLModel):
    material_id: str = SQLField(foreign_key="material.id")
    vendor_id: Optional[str] = None

    # Spulen-Nummern-System (NEU - Teil der Spezifikation v4)
    spool_number: Optional[int] = None  # Unique, user-friendly number (#1, #2, #3...)
    name: Optional[str] = None          # Denormalized from material.name
    vendor: Optional[str] = None        # Denormalized from material.brand
    color: Optional[str] = None         # Spulen-spezifische Farbe

    weight_full: float = 750
    weight_empty: float = 20
    weight_current: Optional[float] = None
    price: Optional[float] = None  # Kaufpreis der vollen Spule in Euro
    status: Optional[str] = None
    location: Optional[str] = None
    label: Optional[str] = None
    external_id: Optional[str] = None
    printer_id: Optional[str] = SQLField(default=None, foreign_key="printer.id")
    printer_slot: Optional[int] = None
    ams_slot: Optional[int] = None
    ams_id: Optional[str] = None
    ams_source: Optional[str] = None
    assigned: bool = False
    is_active: bool = True
    tag_uid: Optional[str] = None
    rfid_chip_id: Optional[str] = None
    tray_uuid: Optional[str] = None
    tray_color: Optional[str] = None
    tray_type: Optional[str] = None
    remain_percent: Optional[float] = None
    last_seen: Optional[str] = None
    first_seen: Optional[str] = None
    used_count: int = 0
    last_slot: Optional[int] = None
    is_open: bool = True
    is_empty: bool = False
    manufacturer_spool_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Weight History & AMS Tracking (Weight Management System)
    last_seen_in_ams_type: Optional[str] = None  # 'AMS_LITE' oder 'AMS_FULL'
    last_seen_timestamp: Optional[str] = None
    cloud_weight: Optional[float] = None
    cloud_last_sync: Optional[str] = None
    weight_source: Optional[str] = "filamenthub_manual"
    last_manual_update: Optional[str] = None
    last_number: Optional[int] = None  # Archiv: Nummer bevor sie freigegeben wurde
    emptied_at: Optional[str] = None

    # Bambu Cloud Integration
    cloud_tray_uuid: Optional[str] = None  # UUID aus Bambu Cloud für Mapping
    last_verified_at: Optional[str] = None  # Zeitpunkt der letzten Cloud-Verifizierung
    cloud_sync_status: Optional[str] = None  # 'synced', 'pending', 'conflict', 'error'


class Spool(SpoolBase, table=True):
    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True)


class SpoolCreateSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    material_id: str
    vendor_id: str | None = Field(None, alias="manufacturer")
    weight: float | None = Field(None, gt=0)
    weight_full: float = Field(750, gt=0)
    weight_empty: float = Field(20, gt=0)
    weight_current: float | None = Field(None, gt=0)
    price: float | None = Field(None, ge=0)  # Kaufpreis in Euro
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
    rfid_chip_id: str | None = None
    remain_percent: float | None = None
    # Neuer Canonical-Ausgabewerte (Backend-berechnet)
    remaining_weight_g: float | None = None
    total_weight_g: float | None = None
    remaining_percent: float | None = None
    last_seen: str | None = None
    color: str | None = None  # JETZT persistiert (Teil des Nummern-Systems)
    name: str | None = None  # NEU: Kopie von material.name
    vendor: str | None = None  # NEU: Kopie von material.brand
    spool_number: int | None = None  # NEU: User-friendly Nummer
    first_seen: str | None = None
    used_count: int = 0
    last_slot: int | None = None
    is_open: bool = True
    is_empty: bool = False
    manufacturer_spool_id: str | None = None
    # Weight History & AMS Tracking
    last_seen_in_ams_type: str | None = None
    cloud_weight: float | None = None
    weight_source: str | None = None
    last_number: int | None = None
    # Bambu Cloud Integration
    cloud_tray_uuid: str | None = None
    last_verified_at: str | None = None
    cloud_sync_status: str | None = None

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
    price: float | None = Field(None, ge=0)  # Kaufpreis in Euro
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
    rfid_chip_id: str | None = None
    last_seen: str | None = None
    color: str | None = None
    spool_number: int | None = None
    first_seen: str | None = None
    used_count: int | None = None
    last_slot: int | None = None
    is_open: bool | None = None
    is_empty: bool | None = None
    manufacturer_spool_id: str | None = None
    # Weight History & AMS Tracking
    last_seen_in_ams_type: str | None = None
    cloud_weight: float | None = None
    weight_source: str | None = None
    last_manual_update: str | None = None
    last_number: int | None = None
    emptied_at: str | None = None
    # Bambu Cloud Integration
    cloud_tray_uuid: str | None = None
    last_verified_at: str | None = None
    cloud_sync_status: str | None = None

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

    # Spulen-Nummern-System (NEU)
    spool_number: int | None = None
    name: str | None = None
    vendor: str | None = None
    color: str | None = None

    weight_full: float
    weight_empty: float
    weight_current: float | None = Field(None, serialization_alias="weight")
    price: float | None = None  # Kaufpreis in Euro
    status: str | None = None
    location: str | None = None
    label: str | None = None
    external_id: str | None = None
    printer_slot: int | None = None
    ams_slot: int | None = None
    printer_id: str | None = None
    printer_name: str | None = None  # Drucker-Name für UI-Anzeige
    tag_uid: str | None = None
    tray_uuid: str | None = None
    tray_color: str | None = None
    tray_type: str | None = None
    remain_percent: float | None = None
    remaining_weight_g: float | None = None
    total_weight_g: float | None = None
    remaining_percent: float | None = None
    last_seen: str | None = None
    first_seen: str | None = None
    used_count: int = 0
    last_slot: int | None = None
    is_open: bool = True
    is_empty: bool = False
    manufacturer_spool_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    fill_state: str | None = None
    # Weight History & AMS Tracking
    last_seen_in_ams_type: str | None = None
    last_seen_timestamp: str | None = None
    cloud_weight: float | None = None
    cloud_last_sync: str | None = None
    weight_source: str | None = None
    last_manual_update: str | None = None
    last_number: int | None = None
    emptied_at: str | None = None
    # Bambu Cloud Integration
    cloud_tray_uuid: str | None = None
    last_verified_at: str | None = None
    cloud_sync_status: str | None = None
    is_locked: bool = False
    lock_reason: str | None = None
    active_job_id: str | None = None
    active_job_name: str | None = None
