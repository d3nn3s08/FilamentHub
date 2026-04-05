import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class KlipperFileAdapter:
    """
    Klipper Adapter auf Basis von exportierten Moonraker JSON-Dateien.
    Dient als Offline-/Mock-Quelle.
    """

    def __init__(
        self,
        printer_info_path: str,
        objects_list_path: str,
        objects_query_path: str,
    ):
        self.printer_info_path = Path(printer_info_path)
        self.objects_list_path = Path(objects_list_path)
        self.objects_query_path = Path(objects_query_path)

    # -------------------------------------------------
    # Loader
    # -------------------------------------------------

    def _load_json(self, path: Path) -> dict:
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Klipper file load failed: %s (%s)", path, e)
            return {}

    # -------------------------------------------------
    # Moonraker-ähnliche APIs
    # -------------------------------------------------

    def get_printer_info(self) -> dict:
        return self._load_json(self.printer_info_path).get("result", {})

    def get_printer_objects_list(self) -> list[str]:
        data = self._load_json(self.objects_list_path)
        return data.get("result", {}).get("objects", [])

    def get_printer_objects_query(self) -> dict:
        return self._load_json(self.objects_query_path).get("result", {}).get("status", {})

    # -------------------------------------------------
    # Normalisierung → PrinterData
    # -------------------------------------------------

    def to_printer_data(self) -> dict:
        status = self.get_printer_objects_query()

        print_stats = status.get("print_stats", {})
        v_sd = status.get("virtual_sdcard", {})
        extruder = status.get("extruder", {})
        bed = status.get("heater_bed", {})
        pause = status.get("pause_resume", {})

        return {
            "state": print_stats.get("state", "unknown"),
            "file": print_stats.get("filename"),
            "progress": v_sd.get("progress"),
            "elapsed": print_stats.get("print_duration"),
            "paused": pause.get("is_paused", False),
            "temperatures": {
                "hotend": extruder.get("temperature"),
                "bed": bed.get("temperature"),
            },
            "source": "klipper",
            "mode": "file",
        }
