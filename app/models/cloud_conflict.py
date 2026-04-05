"""
CloudConflict Model - Protokolliert Konflikte zwischen lokalen und Cloud-Daten
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, ConfigDict


class CloudConflictBase(SQLModel):
    """Basis-Felder für Cloud-Konflikte"""

    # Referenzen
    spool_id: Optional[str] = Field(default=None, foreign_key="spool.id")
    printer_id: Optional[str] = Field(default=None, foreign_key="printer.id")

    # Konflikt-Details
    conflict_type: str  # 'weight', 'color', 'material', 'location', 'missing_local', 'missing_cloud'
    severity: str = "medium"  # 'low', 'medium', 'high', 'critical'

    # Werte
    local_value: Optional[str] = None  # Lokaler Wert (als JSON-String)
    cloud_value: Optional[str] = None  # Cloud-Wert (als JSON-String)
    difference_percent: Optional[float] = None  # Prozentuale Abweichung (bei Gewicht)

    # Status
    status: str = "pending"  # 'pending', 'resolved', 'ignored', 'auto_resolved'
    resolution: Optional[str] = None  # 'kept_local', 'accepted_cloud', 'merged', 'ignored'
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None  # 'user', 'auto', 'system'

    # Kontext
    detected_at: str  # Wann wurde der Konflikt erkannt
    sync_session_id: Optional[str] = None  # Zu welchem Sync gehört der Konflikt
    description: Optional[str] = None  # Menschenlesbare Beschreibung

    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CloudConflict(CloudConflictBase, table=True):
    """Cloud-Konflikt Tabelle"""
    __tablename__ = "cloud_conflicts"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class CloudConflictCreate(BaseModel):
    """Schema zum Erstellen eines Konflikts"""
    model_config = ConfigDict(extra="ignore")

    spool_id: Optional[str] = None
    printer_id: Optional[str] = None
    conflict_type: str
    severity: str = "medium"
    local_value: Optional[str] = None
    cloud_value: Optional[str] = None
    difference_percent: Optional[float] = None
    detected_at: str
    sync_session_id: Optional[str] = None
    description: Optional[str] = None


class CloudConflictRead(BaseModel):
    """Schema für API-Ausgabe"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    spool_id: Optional[str] = None
    printer_id: Optional[str] = None
    conflict_type: str
    severity: str
    local_value: Optional[str] = None
    cloud_value: Optional[str] = None
    difference_percent: Optional[float] = None
    status: str
    resolution: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    detected_at: str
    sync_session_id: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Zusätzliche Infos für UI
    spool_name: Optional[str] = None
    spool_number: Optional[int] = None
    printer_name: Optional[str] = None


class CloudConflictResolve(BaseModel):
    """Schema zum Auflösen eines Konflikts"""
    resolution: str  # 'keep_local', 'accept_cloud', 'merge', 'ignore'
    merge_value: Optional[str] = None  # Bei 'merge': der zusammengeführte Wert
