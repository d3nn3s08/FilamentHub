"""
Weight History Model

Tracks all weight changes for spools with full audit trail.
Linked to spools via tray_uuid (permanent ID) instead of spool_number (recyclable).
"""
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field as SQLField


class WeightHistoryBase(SQLModel):
    """Base model for weight history entries"""

    # Spulen-Referenz (UUID statt ID!)
    # Soft-Reference: kein Foreign-Key-Constraint, da spool.tray_uuid kein UNIQUE-Feld ist
    # und SQLite mit PRAGMA foreign_keys=ON sonst "foreign key mismatch" wirft.
    spool_uuid: str = SQLField(index=True)
    spool_number: Optional[int] = None  # Snapshot der Nummer zum Zeitpunkt

    # Gewichts-Änderung
    old_weight: float
    new_weight: float

    # Metadaten
    source: str  # 'filamenthub_manual', 'bambu_cloud', 'ams_rfid', 'print_consumed'
    change_reason: str  # 'manual_update', 'conflict_resolution_user_choice', 'print_job_completed', etc.
    ams_type: Optional[str] = None  # 'AMS_LITE' oder 'AMS_FULL'

    # User & Zeit
    user: str  # Username oder 'System'
    timestamp: datetime = SQLField(default_factory=datetime.utcnow)

    # Details
    details: Optional[str] = None


class WeightHistory(WeightHistoryBase, table=True):
    """Weight history table"""

    __tablename__ = "weight_history"

    id: Optional[int] = SQLField(default=None, primary_key=True)


class WeightHistoryRead(SQLModel):
    """Schema for reading weight history"""

    id: int
    spool_uuid: str
    spool_number: Optional[int]
    old_weight: float
    new_weight: float
    source: str
    change_reason: str
    ams_type: Optional[str]
    user: str
    timestamp: datetime
    details: Optional[str]

    class Config:
        from_attributes = True


class WeightHistoryCreate(SQLModel):
    """Schema for creating weight history entries"""

    spool_uuid: str
    spool_number: Optional[int] = None
    old_weight: float
    new_weight: float
    source: str
    change_reason: str
    ams_type: Optional[str] = None
    user: str
    details: Optional[str] = None
