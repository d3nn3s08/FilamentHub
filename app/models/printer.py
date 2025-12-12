from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4


class PrinterBase(SQLModel):
    name: str
    printer_type: str  # "bambu", "klipper", "manual"
    ip_address: Optional[str] = None
    port: Optional[int] = None
    model: str = Field(default="X1C", max_length=32)  # z.B. X1C, A1MINI, P1S, H2D
    mqtt_version: str = Field(default="311", max_length=8)  # MQTT Protocol Version

    cloud_serial: Optional[str] = None  # Bambu Cloud Seriennummer
    api_key: Optional[str] = None  # z.B. Moonraker Token
    active: bool = True  # wird beim Start berücksichtigt
    auto_connect: bool = False  # Automatische MQTT-Verbindung


class Printer(PrinterBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class PrinterCreate(PrinterBase):
    pass


class PrinterRead(PrinterBase):
    id: str
    online: bool = False
    active: bool = True
    image_url: Optional[str] = None  # Nur Ausgabe, kein DB-Feld
