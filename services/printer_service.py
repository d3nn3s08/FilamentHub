from typing import Dict, Optional, Any, cast, Union
from datetime import datetime

from app.services.printer_data import PrinterData


class PrinterService:
    """Zentraler In-Memory-Speicher für Druckerdaten (PrinterData).

    Keyed by cloud_serial (string). No automatic registration by client_id.
    """

    def __init__(self) -> None:
        # keys: cloud_serial -> { name, model, printer_id, data, last_update, capabilities }
        # Use Any for inner dict values; cast when returning typed PrinterData
        self.printers: Dict[str, Dict[str, Any]] = {}

    def register_printer(self, key: str, name: str, model: str, printer_id: str, source: str = "unknown") -> None:
        if not key:
            print(f"[PrinterService] register_printer called without cloud_serial; source={source}")
            return
        self.printers[key] = {
            "name": name,
            "model": model,
            "printer_id": printer_id,
            "data": None,
            "last_update": None,
            "capabilities": {},
            "registered_via": source,
            "connected": False,
            "last_seen": None,
        }

    def update_printer(self, key: str, data: PrinterData) -> None:
        if not key:
            print(f"[PrinterService] update_printer called without cloud_serial; skipping update")
            return
        if key not in self.printers:
            # Do not auto-register by client_id anymore
            print(f"[PrinterService] Unbekannter cloud_serial '{key}', update ignored (no auto-register)")
            return
        self.printers[key]["data"] = data
        self.printers[key]["last_update"] = datetime.utcnow().isoformat()

    def get(self, key: str) -> Optional[PrinterData]:
        entry = self.printers.get(key)
        if not entry:
            return None
        return cast(Optional[PrinterData], entry.get("data"))

    def get_all(self) -> Dict[str, Optional[PrinterData]]:
        return {k: cast(Optional[PrinterData], v.get("data")) for k, v in self.printers.items()}

    def update_capabilities(self, key: str, caps: Dict[str, bool]) -> None:
        if key in self.printers:
            self.printers[key]["capabilities"] = caps

    def set_connected(self, key: str, connected: bool, last_seen: Optional[str] = None) -> None:
        if not key:
            return
        if key not in self.printers:
            # do not auto-register here
            print(f"[PrinterService] set_connected called for unknown cloud_serial '{key}', ignored")
            return
        self.printers[key]["connected"] = bool(connected)
        if last_seen:
            self.printers[key]["last_seen"] = last_seen
            # Also mirror last_update for backward compatibility
            self.printers[key]["last_update"] = last_seen

    def get_status(self, key: str, timeout_seconds: int = 15) -> Dict[str, Optional[Union[bool, str]]]:
        entry = self.printers.get(key)
        if not entry:
            return {"connected": False, "last_seen": None}
        last_seen = entry.get("last_seen")
        connected = bool(entry.get("connected", False))
        # timeout logic: if last_seen older than threshold, treat as disconnected
        if last_seen:
            try:
                from datetime import datetime, timezone

                last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                delta = (now - last_dt).total_seconds()
                if delta > float(timeout_seconds):
                    connected = False
            except Exception:
                # if parsing fails, keep stored connected flag
                pass

        return {"connected": connected, "last_seen": last_seen}
