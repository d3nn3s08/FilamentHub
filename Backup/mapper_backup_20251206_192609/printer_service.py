from typing import Dict, Optional
from datetime import datetime

from app.services.printer_data import PrinterData


class PrinterService:
    """Zentraler In-Memory-Speicher für Druckerdaten (PrinterData)."""

    def __init__(self) -> None:
        self.printers: Dict[str, Dict[str, object]] = {}

    def register(self, name: str, model: str, ip: Optional[str], mqtt_version: Optional[str]) -> None:
        self.printers[name] = {
            "model": model,
            "ip": ip,
            "mqtt_version": mqtt_version,
            "data": None,
            "last_update": None,
        }

    def update_printer(self, name: str, data: PrinterData) -> None:
        if name not in self.printers:
            print(f"[PrinterService] Unbekannter Drucker '{name}', wird dynamisch registriert.")
            self.printers[name] = {
                "model": getattr(data, "model", None) or "UNKNOWN",
                "ip": None,
                "mqtt_version": None,
                "data": None,
                "last_update": None,
            }
        self.printers[name]["data"] = data
        self.printers[name]["last_update"] = datetime.utcnow().isoformat()

    def get(self, name: str) -> Optional[PrinterData]:
        entry = self.printers.get(name)
        return entry["data"] if entry else None

    def get_all(self) -> Dict[str, Optional[PrinterData]]:
        return {n: d.get("data") for n, d in self.printers.items()}
