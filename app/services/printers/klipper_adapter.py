import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)


class KlipperAdapter:
    """
    Adapter für Klipper / Moonraker
    Aufgabe:
    - Moonraker abfragen
    - Relevante Objects holen
    - In internes PrinterData-Format mappen
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # -------------------------------------------------
    # Low-Level HTTP
    # -------------------------------------------------

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            r = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("Klipper GET failed: %s %s", url, e)
            return {}

    # -------------------------------------------------
    # Moonraker Endpoints
    # -------------------------------------------------

    def get_printer_info(self) -> dict:
        return self._get("/printer/info")

    def get_printer_objects(self, objects: list[str]) -> dict:
        """
        objects z.B.:
        ["print_stats", "virtual_sdcard", "extruder", "heater_bed", "pause_resume"]
        """
        params = {"objects": ",".join(objects)}
        return self._get("/printer/objects/query", params=params)

    # -------------------------------------------------
    # High-Level API
    # -------------------------------------------------

    def fetch_status(self) -> dict:
        """
        Zentrale Methode für FilamentHub.
        Liefert normalisierte Rohdaten.
        """
        data = self.get_printer_objects(
            [
                "print_stats",
                "virtual_sdcard",
                "extruder",
                "heater_bed",
                "pause_resume",
            ]
        )

        result = data.get("result", {})
        status = result.get("status", {})

        return {
            "print_stats": status.get("print_stats", {}),
            "virtual_sdcard": status.get("virtual_sdcard", {}),
            "extruder": status.get("extruder", {}),
            "heater_bed": status.get("heater_bed", {}),
            "pause_resume": status.get("pause_resume", {}),
        }

    # -------------------------------------------------
    # Mapping → PrinterData (noch bewusst simpel)
    # -------------------------------------------------

    def to_printer_data(self) -> dict:
        raw = self.fetch_status()

        print_stats = raw["print_stats"]
        v_sd = raw["virtual_sdcard"]

        state = print_stats.get("state", "unknown")

        return {
            "state": state,
            "file": print_stats.get("filename"),
            "progress": v_sd.get("progress"),
            "elapsed": print_stats.get("print_duration"),
            "paused": raw["pause_resume"].get("is_paused", False),
            "temperatures": {
                "hotend": raw["extruder"].get("temperature"),
                "bed": raw["heater_bed"].get("temperature"),
            },
            "source": "klipper",
        }
