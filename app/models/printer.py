from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4


class PrinterBase(SQLModel):
    name: str
    printer_type: str  # "bambu", "klipper", "manual"
    ip_address: Optional[str] = None
    port: Optional[int] = None

    cloud_serial: Optional[str] = None  # Bambu Cloud Seriennummer
    api_key: Optional[str] = None  # z.B. Moonraker Token


class Printer(PrinterBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class PrinterCreate(PrinterBase):
    pass


class PrinterRead(PrinterBase):
    id: str
