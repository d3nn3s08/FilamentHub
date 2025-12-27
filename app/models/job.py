from sqlmodel import SQLModel, Field
from typing import Optional, List, ClassVar
from uuid import uuid4
from datetime import datetime


class JobBase(SQLModel):
    printer_id: str = Field(foreign_key="printer.id")
    spool_id: Optional[str] = Field(default=None, foreign_key="spool.id")

    name: str
    filament_used_mm: float = 0
    filament_used_g: float = 0

    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    # Status: running, completed, failed, cancelled, aborted
    status: str = Field(default="running")

    # Spulen-Snapshot-System (NEU - Teil der Spezifikation v4)
    # Speichert Spulen-Daten zum Zeitpunkt des Job-Starts
    spool_number: Optional[int] = None
    spool_name: Optional[str] = None
    spool_vendor: Optional[str] = None
    spool_color: Optional[str] = None
    spool_created_at: Optional[str] = None


class Job(JobBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class JobCreate(JobBase):
    pass


class JobRead(JobBase):
    id: str


class JobSpoolUsageBase(SQLModel):
    job_id: str = Field(foreign_key="job.id")
    spool_id: Optional[str] = Field(default=None, foreign_key="spool.id")
    slot: Optional[int] = None
    used_mm: float = 0
    used_g: float = 0
    order_index: Optional[int] = None


class JobSpoolUsage(JobSpoolUsageBase, table=True):
    __tablename__: ClassVar[str] = "job_spool_usage"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class JobSpoolUsageCreate(JobSpoolUsageBase):
    pass


class JobSpoolUsageRead(JobSpoolUsageBase):
    id: str
