from typing import Any, Dict, Optional
from datetime import datetime, timezone

from app.services.printer_data import PrinterData


class UniversalMapper:
    """
    Universeller Mapper für verschiedene Druckerplattformen.

    Unterstützt:
    - BambuLab (X1C/X1E/P1/A1/A1 Mini, H2D-ähnliche Payloads)
    - Klipper (Moonraker-Statusstruktur)
    - Fallback auf "alles in extra"
    """

    def __init__(self, model: Optional[str] = None) -> None:
        # Optionaler Modell-Hint aus DB oder Config
        self.model_hint = (model or "").upper().strip() or None

    # ------------------------------------------------------------------ #
    # Public Entry
    # ------------------------------------------------------------------ #
    def map(self, data: Dict[str, Any]) -> PrinterData:
        pd = PrinterData()

        # Modell bestimmen: Hint > Auto-Detection > UNKNOWN
        detected = self._detect_model(data)
        pd.model = self.model_hint or detected or "UNKNOWN"

        # Timestamp setzen, falls PrinterData das Feld hat
        try:
            pd.timestamp = datetime.now(timezone.utc).isoformat()
        except AttributeError:
            # falls älteres PrinterData ohne timestamp
            pass

        model = (pd.model or "").upper()

        # Routing nach Modell / Struktur
        if model in {"X1C", "X1E", "P1", "P1P", "P1S", "A1", "A1MINI"}:
            self._map_bambu(data, pd)
        elif model == "H2D":
            self._map_bambu_h2d(data, pd)
        elif model == "KLIPPER":
            self._map_klipper(data, pd)
        else:
            # wenn Modell unklar ist, versuche Struktur-basiert
            if self._looks_like_bambu(data):
                self._map_bambu(data, pd)
            elif self._looks_like_klipper(data):
                self._map_klipper(data, pd)
            else:
                self._map_generic(data, pd)

        return pd

    # ------------------------------------------------------------------ #
    # Modell-Erkennung
    # ------------------------------------------------------------------ #
    def _detect_model(self, data: Dict[str, Any]) -> Optional[str]:
        # 1) Bambu-spezifische Zeichen
        if "gcode_state" in data or "mc_percent" in data or "lights_report" in data:
            return "X1C"
        if "mc_print" in data or "ams" in data or "vt_tray" in data:
            return "X1C"
        if "temperature" in data and "cooling_fan" in data and "material_system" in data:
            return "H2D"

        # 2) Klipper/Moonraker Strukturen
        if self._looks_like_klipper(data):
            return "KLIPPER"

        return None

    def _looks_like_bambu(self, data: Dict[str, Any]) -> bool:
        keys = set(data.keys())
        bambu_markers = {
            "gcode_state", "mc_percent", "mc_remaining_time",
            "print", "ams", "lights_report", "nozzle_temper", "bed_temper"
        }
        return bool(keys & bambu_markers)

    def _looks_like_klipper(self, data: Dict[str, Any]) -> bool:
        # Moonraker: top-level "status": {...}
        if "status" in data:
            return True
        # manchmal direkt status-Felder
        status_keys = {"print_stats", "heater_bed", "extruder", "display_status"}
        if isinstance(data.get("status"), dict):
            return True
        if any(k in data for k in status_keys):
            return True
        return False

    # ------------------------------------------------------------------ #
    # Bambu – Hauptmapper (X1C, P1, A1, A1 Mini)
    # ------------------------------------------------------------------ #
    def _map_bambu(self, data: Dict[str, Any], out: PrinterData) -> None:
        """
        Flexibler Bambu-Mapper:
        - unterstützt sowohl neue X1C-ähnliche Payloads (device/extruder/bed/ctc, lights_report,...)
        - als auch ältere mc_print/print/heater/cooling Strukturen.
        """

        # ---------------- STATE ----------------
        state = (
            data.get("gcode_state") or
            self._translate_mc_stage(data.get("mc_print_stage")) or
            data.get("state")
        )
        out.state = state

        # ---------------- PROGRESS ----------------
        mc_percent = data.get("mc_percent")
        percent = data.get("percent")
        pr_progress = None

        pr = data.get("print") or {}

        if isinstance(pr, dict):
            pr_progress = pr.get("progress")

        out.progress = self._safe_float(
            mc_percent if mc_percent is not None
            else percent if percent is not None
            else pr_progress if pr_progress is not None
            else 0.0
        )

        # ---------------- TEMPERATURE ----------------
        # Variante 1: neue X1C-Struktur über device.*
        nozzle = (
            data.get("nozzle_temper")
            or self._deep_get(data, ["device", "extruder", "info", 0, "temp"])
        )
        bed = (
            data.get("bed_temper")
            or self._deep_get(data, ["device", "bed", "info", "temp"])
        )
        chamber = self._deep_get(data, ["device", "ctc", "info", "temp"])

        # Fallback Variante 2: ältere heater-Struktur
        heater = data.get("heater") or {}
        if nozzle is None:
            nozzle = heater.get("nozzle_temper") or heater.get("nozzle_temp")
        if bed is None:
            bed = heater.get("bed_temper") or heater.get("bed_temp")
        if chamber is None:
            chamber = heater.get("chamber_temper") or heater.get("chamber_temp")

        out.temperature["nozzle"] = self._safe_float(nozzle)
        out.temperature["bed"] = self._safe_float(bed)
        out.temperature["chamber"] = self._safe_float(chamber)

        # ---------------- LAYER ----------------
        current_layer = (
            data.get("layer_num")
            or self._deep_get(pr, ["layer_num"])
            or self._deep_get(data, ["print", "3D", "layer_num"])
            or 0
        )
        total_layer = (
            data.get("total_layer_num")
            or pr.get("total_layer")
            or self._deep_get(data, ["print", "3D", "total_layer_num"])
        )

        out.layer["current"] = self._safe_int(current_layer)
        out.layer["total"] = self._safe_int(total_layer)

        if out.layer["current"] and out.layer["total"] and out.layer["current"] > out.layer["total"]:
            out.layer["current"] = out.layer["total"]

        # ---------------- FANS ----------------
        cooling = data.get("cooling") or {}
        out.fan["part_cooling"] = (
            data.get("cooling_fan_speed")
            or data.get("heatbreak_fan_speed")
            or cooling.get("fan_1_speed")
        )
        out.fan["aux"] = cooling.get("fan_2_speed") or data.get("big_fan1_speed")
        out.fan["chamber"] = cooling.get("fan_3_speed") or data.get("big_fan2_speed")

        # ---------------- LIGHTS ----------------
        lights = data.get("lights_report") or data.get("light") or []
        if isinstance(lights, list):
            for l in lights:
                if l.get("node") == "chamber_light":
                    out.light["state"] = l.get("mode")
        elif isinstance(lights, dict):
            # ältere Struktur: {"light_state": ..., "light_strength": ...}
            out.light["state"] = lights.get("light_state") or lights.get("on")
            out.light["brightness"] = lights.get("light_strength") or lights.get("strength")

        # ---------------- AMS ----------------
        # komplette AMS-Struktur unter print.ams / ams / fil / vt_tray
        ams = (
            self._deep_get(data, ["print", "ams"])
            or data.get("ams")
            or data.get("filament")
            or data.get("material_system")  # H2D-ähnlich
            or data.get("vt_tray")
            or data.get("vir_slot")
        )
        out.ams = ams

        # ---------------- JOB ----------------
        out.job["file"] = (
            data.get("gcode_file")
            or data.get("file")
            or pr.get("file")
            or ""
        )
        out.job["time_remaining"] = (
            data.get("mc_remaining_time")
            or data.get("remain_time")
            or pr.get("time_remaining")
        )
        # hier nur "irgendwas" für elapsed, Bambu liefert das nicht immer sauber
        out.job["time_elapsed"] = self._deep_get(data, ["job", "cur_stage", "state"])

        # ---------------- SPEED MODE ----------------
        out.speed_mode = (
            data.get("print_speed_mode")
            or pr.get("speed_level")
            or data.get("spd_lvl")
        )

        # ---------------- ERROR ----------------
        out.error = (
            data.get("err")
            or data.get("mc_err")
            or pr.get("error_code")
        )

        # ---------------- EXTRA ----------------
        known = {
            "gcode_state", "mc_print_stage", "state",
            "mc_percent", "percent", "print",
            "device", "heater", "cooling",
            "lights_report", "light",
            "ams", "filament", "material_system",
            "vt_tray", "vir_slot",
            "gcode_file", "file", "remain_time",
            "mc_remaining_time", "job",
            "layer_num", "total_layer_num",
            "big_fan1_speed", "big_fan2_speed",
            "heatbreak_fan_speed", "cooling_fan_speed",
            "nozzle_temper", "bed_temper",
            "spd_lvl", "mc_err", "err",
        }
        for k, v in data.items():
            if k not in known:
                out.extra[k] = v

    # ------------------------------------------------------------------ #
    # Bambu H2D – stärker API-orientierte Struktur
    # ------------------------------------------------------------------ #
    def _map_bambu_h2d(self, data: Dict[str, Any], out: PrinterData) -> None:
        # eher generische H2D-Variante, falls du später H2D direkt nutzt
        temp = data.get("temperature", {})
        out.temperature["nozzle"] = self._safe_float(temp.get("nozzle"))
        out.temperature["bed"] = self._safe_float(temp.get("bed"))
        out.temperature["chamber"] = self._safe_float(temp.get("chamber"))

        fan = data.get("cooling_fan", {})
        out.fan["part_cooling"] = fan.get("toolhead_fan")
        out.fan["chamber"] = fan.get("chamber_fan")

        job = data.get("job", {})
        out.job["file"] = job.get("name")
        out.job["time_elapsed"] = job.get("elapsed")
        out.job["time_remaining"] = job.get("remaining")

        out.state = job.get("state")
        out.progress = self._safe_float(job.get("progress"))

        out.ams = data.get("material_system")
        out.error = data.get("error")

        # rest als extra
        known = {"temperature", "cooling_fan", "job", "material_system", "error"}
        for k, v in data.items():
            if k not in known:
                out.extra[k] = v

    # ------------------------------------------------------------------ #
    # Klipper / Moonraker
    # ------------------------------------------------------------------ #
    def _map_klipper(self, data: Dict[str, Any], out: PrinterData) -> None:
        """
        Erwartet Moonraker-ähnliche Strukturen:
        {
          "status": {
             "print_stats": {...},
             "heater_bed": {...},
             "extruder": {...},
             "fan": {...},
             "display_status": {...},
             ...
          }
        }
        oder direkt "print_stats", "heater_bed" etc. auf Top-Level.
        """
        status = data.get("status") or data

        print_stats = status.get("print_stats", {})
        heater_bed = status.get("heater_bed", {})
        extruder = status.get("extruder", {})
        fan = status.get("fan") or status.get("part_fan") or {}
        display_status = status.get("display_status", {})

        # STATE
        out.state = print_stats.get("state")

        # PROGRESS (Moonraker liefert meist 0..1)
        prog = print_stats.get("progress")
        if prog is not None:
            # wir speichern hier 0..100
            out.progress = float(prog) * 100.0 if prog <= 1 else float(prog)
        else:
            out.progress = None

        # TEMPERATURE
        out.temperature["nozzle"] = self._safe_float(extruder.get("temperature"))
        out.temperature["bed"] = self._safe_float(heater_bed.get("temperature"))
        # chamber eher selten, aber manchmal über "temperature_sensor chamber"
        chamber = None
        temp_sensors = status.get("temperature_sensor") or {}
        if isinstance(temp_sensors, dict):
            chamber_sensor = temp_sensors.get("chamber") or temp_sensors.get("Chamber")
            if isinstance(chamber_sensor, dict):
                chamber = chamber_sensor.get("temperature")
        out.temperature["chamber"] = self._safe_float(chamber)

        # FAN
        # fan.speed in 0..1
        fan_speed = fan.get("speed")
        if fan_speed is not None:
            try:
                out.fan["part_cooling"] = float(fan_speed) * 100.0
            except Exception:
                out.fan["part_cooling"] = None

        # LAYER (falls Klipper-Plugin das liefert)
        cur_layer = display_status.get("layer")
        total_layer = display_status.get("total_layer")
        out.layer["current"] = self._safe_int(cur_layer)
        out.layer["total"] = self._safe_int(total_layer)
        if out.layer["current"] and out.layer["total"] and out.layer["current"] > out.layer["total"]:
            out.layer["current"] = out.layer["total"]

        # JOB
        out.job["file"] = print_stats.get("filename")
        out.job["time_elapsed"] = print_stats.get("print_duration") or print_stats.get("total_duration")
        out.job["time_remaining"] = print_stats.get("time_remaining") or display_status.get("estimated_time_remaining")

        # ERROR – z.B. durch "state": "error" oder andere Felder
        if out.state and str(out.state).lower() == "error":
            out.error = "print_error"
        else:
            out.error = None

        # REST ALS EXTRA
        known_top = {"status"}
        for k, v in data.items():
            if k not in known_top:
                out.extra[k] = v

        # auch Teile von status in extra mitnehmen, die wir nicht explizit mappen
        known_status = {"print_stats", "heater_bed", "extruder", "fan", "part_fan", "display_status", "temperature_sensor"}
        for k, v in status.items():
            if k not in known_status:
                out.extra[f"status.{k}"] = v

    # ------------------------------------------------------------------ #
    # Fallback – alles in extra
    # ------------------------------------------------------------------ #
    def _map_generic(self, data: Dict[str, Any], out: PrinterData) -> None:
        out.extra = dict(data)

    # ------------------------------------------------------------------ #
    # HELPER
    # ------------------------------------------------------------------ #
    def _translate_mc_stage(self, stage: Any) -> Optional[str]:
        mapping = {
            "0": None,
            "1": "IDLE",
            "2": "HEATING",
            "3": "PRINTING",
            "4": "PAUSED",
            "5": "FINISHED",
        }
        if stage is None:
            return None
        return mapping.get(str(stage).strip(), None)

    def _safe_int(self, val: Any) -> Optional[int]:
        try:
            if val is None:
                return None
            return int(val)
        except Exception:
            return None

    def _safe_float(self, val: Any) -> Optional[float]:
        try:
            if val is None:
                return None
            return float(val)
        except Exception:
            return None

    def _deep_get(self, data: Any, path: list, default=None):
        """
        Tief verschachtelte Werte sicher holen:
        path = ["device", "extruder", "info", 0, "temp"]
        """
        cur = data
        try:
            for p in path:
                if isinstance(p, int):
                    cur = cur[p]
                else:
                    cur = cur[p]
            return cur
        except Exception:
            return default
