from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, ClassVar
from uuid import uuid4
from datetime import datetime


class JobBase(SQLModel):
    printer_id: str = Field(foreign_key="printer.id")
    spool_id: Optional[str] = Field(default=None, foreign_key="spool.id")

    name: str  # Original-Name aus MQTT (für Matching, wird nicht überschrieben)
    display_name: Optional[str] = None  # Anzeigename (User kann frei ändern)
    filament_used_mm: float = 0
    filament_used_g: float = 0

    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    # Status: running, completed, failed, cancelled, aborted
    status: str = Field(default="running")

    # Print Source: "ams" (AMS slot used), "external" (vir_slot/external spool), "unknown"
    print_source: Optional[str] = Field(default="unknown")

    # Bambu Cloud Task ID (für Cloud API Integration)
    # Wird aus MQTT-Payload extrahiert: print.task_id
    # Verwendet für: Cloud-Weight-Fetch, Admin-Backfill, Audit-Trail
    task_id: Optional[str] = None

    # Task Name & GCode File (für zukünftige Claude/AI-Integration)
    # task_name: Menschenlesbarer Name des Druckauftrags (aus MQTT: subtask_name oder gcode_file)
    # gcode_file: Dateiname der GCode-Datei (für FTP-Download und Gewichtsextraktion)
    task_name: Optional[str] = None
    gcode_file: Optional[str] = None

    # Spulen-Snapshot-System (NEU - Teil der Spezifikation v4)
    # Speichert Spulen-Daten zum Zeitpunkt des Job-Starts
    spool_number: Optional[int] = None
    spool_name: Optional[str] = None
    spool_vendor: Optional[str] = None
    spool_color: Optional[str] = None
    spool_created_at: Optional[str] = None
    # Optionales, berechnetes Feld für UI: ETA in Sekunden (oder None)
    eta_seconds: Optional[int] = None

    # Filament-Tracking: Startwert beim ersten Auftreten von layer_num >= 1
    filament_start_mm: Optional[float] = None

    # Gewichts-Tracking: Snapshots fuer Verbrauchsberechnung (start - end = consumption)
    start_weight: Optional[float] = None  # Spulen-Gewicht bei Job-Start (g)
    end_weight: Optional[float] = None    # Spulen-Gewicht bei Job-Ende (g)


class Job(JobBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    # Relationship: Many-to-Many mit Spools via JobSpoolUsage
    spool_usages: List["JobSpoolUsage"] = Relationship(back_populates="job")


class JobCreate(JobBase):
    pass


class JobRead(JobBase):
    id: str
    # Optional client-side field for display only (not persisted)
    progress: Optional[float] = None
    is_a_series: Optional[bool] = None

    # Dynamisches Feld: Spulen-Array aus JobSpoolUsage
    # Wird von API geladen (nicht in DB gespeichert)
    spools: Optional[List["JobSpoolUsageRead"]] = None


class JobSpoolUsageBase(SQLModel):
    job_id: str = Field(foreign_key="job.id")
    spool_id: Optional[str] = Field(default=None, foreign_key="spool.id")
    slot: Optional[int] = None
    used_mm: float = 0
    used_g: float = 0
    order_index: Optional[int] = None


class JobSpoolUsage(JobSpoolUsageBase, table=True):
    __tablename__ = "job_spool_usage"  # type: ignore[reportAssignmentType]
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    # Relationship: Zurück zum Job
    job: Optional["Job"] = Relationship(back_populates="spool_usages")


class JobSpoolUsageCreate(JobSpoolUsageBase):
    pass


class JobSpoolUsageRead(JobSpoolUsageBase):
    id: str
