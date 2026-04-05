from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4


class PrinterBase(SQLModel):
    name: str
    printer_type: str  # "bambu", "klipper", "manual"
    ip_address: Optional[str] = None
    port: Optional[int] = None
    model: str = Field(default="X1C", max_length=32)  # z.B. X1C, A1MINI, P1S, H2D
    series: str = Field(default="UNKNOWN", max_length=16)  # A, X, P, H, UNKNOWN, klipper
    mqtt_version: Optional[str] = Field(default=None, max_length=8)  # MQTT Protocol Version

    power_consumption_kw: Optional[float] = Field(default=None)  # Durchschnittliche Leistungsaufnahme
    maintenance_cost_yearly: Optional[float] = Field(default=None)  # Wartungskosten pro Jahr

    cloud_serial: Optional[str] = None  # Bambu Cloud Seriennummer
    api_key: Optional[str] = None  # z.B. Moonraker Token
    active: bool = True  # wird beim Start berücksichtigt
    auto_connect: bool = False  # Automatische MQTT-Verbindung

    # Bambu Cloud Integration
    bambu_device_id: Optional[str] = None  # Device ID aus Bambu Cloud
    cloud_sync_enabled: bool = False  # Cloud-Sync für diesen Drucker aktiviert
    last_cloud_sync: Optional[str] = None  # Zeitpunkt des letzten Cloud-Syncs

    # Happy Hare MMU Integration (Klipper)
    has_mmu: bool = False                  # Hat dieser Drucker eine MMU (Happy Hare)?
    mmu_type: Optional[str] = None         # z.B. "ERCF", "Tradrack", "BoxTurtle"
    mmu_gate_count: Optional[int] = None   # Anzahl Gates (wird automatisch aus HH erkannt)


class Printer(PrinterBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class PrinterCreate(PrinterBase):
    pass


class PrinterRead(PrinterBase):
    id: str
    online: bool = False
    active: bool = True
    image_url: Optional[str] = None  # Nur Ausgabe, kein DB-Feld
    # Bambu Cloud Integration (inherited from PrinterBase)
    bambu_device_id: Optional[str] = None
    cloud_sync_enabled: bool = False
    last_cloud_sync: Optional[str] = None
    # Happy Hare MMU (inherited from PrinterBase)
    has_mmu: bool = False
    mmu_type: Optional[str] = None
    mmu_gate_count: Optional[int] = None
