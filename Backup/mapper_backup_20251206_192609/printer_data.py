from typing import Any, Dict, Optional
from datetime import datetime


class PrinterData:
    """Einheitliches Ausgabeformat für alle Bambu Lab Drucker."""

    def __init__(self) -> None:
        self.model: Optional[str] = None
        self.state: Optional[str] = None
        self.progress: Optional[float] = None
        self.sub_state: Optional[str] = None

        self.temperature: Dict[str, Optional[float]] = {
            "nozzle": None,
            "bed": None,
            "chamber": None,
        }

        self.fan: Dict[str, Optional[float]] = {
            "part_cooling": None,
            "aux": None,
            "chamber": None,
        }

        self.layer: Dict[str, Optional[int]] = {
            "current": None,
            "total": None,
        }

        self.speed_mode: Optional[str] = None

        self.light: Dict[str, Optional[Any]] = {
            "state": None,
            "brightness": None,
        }

        self.ams: Optional[Any] = None

        self.job: Dict[str, Optional[Any]] = {
            "file": None,
            "time_elapsed": None,
            "time_remaining": None,
        }

        self.error: Optional[Any] = None
        self.extra: Dict[str, Any] = {}
        self.timestamp: str = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialisierbare Repräsentation für WebSocket/API (ohne geteilte Referenzen)."""
        return {
            "model": self.model,
            "state": self.state,
            "progress": self.progress,
            "sub_state": self.sub_state,
            "temperature": dict(self.temperature),
            "fan": dict(self.fan),
            "layer": dict(self.layer),
            "speed_mode": self.speed_mode,
            "light": dict(self.light),
            "ams": self.ams,
            "job": dict(self.job),
            "error": self.error,
            "extra": dict(self.extra),
            "timestamp": self.timestamp,
        }
