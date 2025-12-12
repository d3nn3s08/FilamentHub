from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.printer_data import PrinterData


class UniversalMapper:
    """
    Universeller Mapper für verschiedene Druckerplattformen.

    Unterstützt:
    - BambuLab (X1C/X1E/P1/P1P/P1S/A1/A1MINI, H2D-ähnliche Payloads)
    - Klipper / Moonraker
    - Fallback auf generische Strukturen
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self.model_hint = (model or "").upper().strip() or None

    # ------------------------------------------------------------------ #
    # Public Entry
    # ------------------------------------------------------------------ #
    def map(self, data: Dict[str, Any]) -> PrinterData:
        pd = PrinterData()
        try:
            detected = self._detect_model(data)
            pd.model = self.model_hint or detected or "UNKNOWN"
            pd.timestamp = datetime.now(timezone.utc).isoformat()

            model = (pd.model or "").upper()
            if model in {"X1C", "X1E", "P1", "P1P", "P1S", "A1", "A1MINI"}:
                self._map_bambu(data, pd)
            elif model == "H2D":
                self._map_bambu_h2d(data, pd)
            elif model == "KLIPPER":
                self._map_klipper(data, pd)
            else:
                if self._looks_like_bambu(data):
                    self._map_bambu(data, pd)
                elif self._looks_like_klipper(data):
                    self._map_klipper(data, pd)
                else:
                    self._map_generic(data, pd)
        except Exception:
            # Niemals Exceptions werfen – best effort
            pass
        return pd

    # ------------------------------------------------------------------ #
    # Modell-Erkennung
    # ------------------------------------------------------------------ #
    def _detect_model(self, data: Dict[str, Any]) -> Optional[str]:
        if "gcode_state" in data or "mc_percent" in data or "lights_report" in data:
            return "X1C"
        if "mc_print" in data or "ams" in data or "vt_tray" in data:
            return "X1C"
        if "temperature" in data and "cooling_fan" in data and "material_system" in data:
            return "H2D"
        if self._looks_like_klipper(data):
            return "KLIPPER"
        return None

    def _looks_like_bambu(self, data: Dict[str, Any]) -> bool:
        keys = set(data.keys())
        markers = {
            "gcode_state",
            "mc_percent",
            "mc_remaining_time",
            "print",
            "ams",
            "lights_report",
            "nozzle_temper",
            "bed_temper",
        }
        return bool(keys & markers)

    def _looks_like_klipper(self, data: Dict[str, Any]) -> bool:
        if isinstance(data.get("status"), dict):
            return True
        status_keys = {"print_stats", "heater_bed", "extruder", "display_status"}
        if any(k in data for k in status_keys):
            return True
        return False

    # ------------------------------------------------------------------ #
    # Bambu – Hauptmapper (X1C, P1, A1, A1 Mini)
    # ------------------------------------------------------------------ #
    def _map_bambu(self, data: Dict[str, Any], out: PrinterData) -> None:
        # STATE
        pr = data.get("print") or data.get("print_status") or {}
        state = (
            data.get("gcode_state")
            or self._translate_mc_stage(data.get("mc_print_stage"))
            or pr.get("gcode_state")
            or pr.get("state")
            or data.get("state")
        )
        out.state = state

        # PROGRESS
        progress_candidates = [
            data.get("mc_percent"),
            data.get("percent"),
            pr.get("progress") if isinstance(pr, dict) else None,
            pr.get("percent") if isinstance(pr, dict) else None,
            pr.get("mc_percent") if isinstance(pr, dict) else None,
            pr.get("gcode_file_prepare_percent") if isinstance(pr, dict) else None,
            data.get("gcode_file_prepare_percent"),
        ]
        out.progress = self._first_defined_float(progress_candidates)

        # TEMPERATURE
        nozzle = (
            data.get("nozzle_temper")
            or data.get("nozzle_temp")
            or data.get("extruder_temp")
            or self._deep_get(data, ["extruder", "temp"])
            or self._deep_get(data, ["device", "extruder", "info", 0, "temp"])
            or self._deep_get(data, ["temperature", "nozzle"])
        )
        bed = (
            data.get("bed_temper")
            or self._deep_get(data, ["device", "bed", "info", "temp"])
        )
        chamber = self._deep_get(data, ["device", "ctc", "info", "temp"])

        heater = data.get("heater") or {}
        if nozzle is None:
            nozzle = heater.get("nozzle_temper") or heater.get("nozzle_temp")
        if bed is None:
            bed = heater.get("bed_temper") or heater.get("bed_temp")
        if chamber is None:
            chamber = heater.get("chamber_temper") or heater.get("chamber_temp")

        temp_block = data.get("temperature") or {}
        nozzle = nozzle if nozzle is not None else temp_block.get("nozzle")
        bed = bed if bed is not None else temp_block.get("bed")
        chamber = chamber if chamber is not None else temp_block.get("chamber")

        self._set(out.temperature, "nozzle", self._safe_float(nozzle))
        self._set(out.temperature, "bed", self._safe_float(bed))
        self._set(out.temperature, "chamber", self._safe_float(chamber))

        # LAYER
        current_layer = (
            data.get("layer_num")
            or self._deep_get(pr, ["layer_num"])
            or self._deep_get(data, ["print", "3D", "layer_num"])
        )
        total_layer = (
            data.get("total_layer_num")
            or (pr.get("total_layer") if isinstance(pr, dict) else None)
            or self._deep_get(data, ["print", "3D", "total_layer_num"])
        )
        self._set(out.layer, "current", self._safe_int(current_layer))
        self._set(out.layer, "total", self._safe_int(total_layer))
        if (
            out.layer["current"] is not None
            and out.layer["total"] is not None
            and out.layer["current"] > out.layer["total"]
        ):
            out.layer["current"] = out.layer["total"]

        # FANS
        cooling = data.get("cooling") or {}
        cooling_fan = data.get("cooling_fan") or {}
        self._set(
            out.fan,
            "part_cooling",
            self._first_defined_float(
                [
                    data.get("cooling_fan_speed"),
                    data.get("heatbreak_fan_speed"),
                    cooling.get("fan_1_speed"),
                    cooling_fan.get("toolhead_fan"),
                    data.get("fan_speed"),
                ]
            ),
        )
        self._set(
            out.fan,
            "aux",
            self._first_defined_float(
                [
                    cooling.get("fan_2_speed"),
                    cooling_fan.get("heatbreak_fan"),
                    data.get("heatbreak_fan_speed"),
                ]
            ),
        )
        self._set(
            out.fan,
            "chamber",
            self._first_defined_float(
                [
                    cooling.get("fan_3_speed"),
                    cooling_fan.get("chamber_fan"),
                    data.get("big_fan1_speed"),
                    data.get("big_fan2_speed"),
                ]
            ),
        )

        # LIGHTS
        lights = data.get("lights_report") or data.get("light") or []
        if isinstance(lights, list):
            for l in lights:
                if l.get("node") == "chamber_light":
                    self._set(out.light, "state", l.get("mode"))
                if l.get("strength") is not None:
                    self._set(out.light, "brightness", self._safe_float(l.get("strength")))
        elif isinstance(lights, dict):
            self._set(out.light, "state", lights.get("light_state") or lights.get("on"))
            self._set(out.light, "brightness", self._safe_float(lights.get("light_strength") or lights.get("strength")))

        # AMS
        ams_val = (
            self._deep_get(data, ["print", "ams"])
            or data.get("ams")
            or data.get("filament")
            or data.get("material_system")
            or data.get("vt_tray")
            or data.get("vir_slot")
        )
        out.ams = ams_val

        # JOB
        job_block = data.get("job") or pr.get("job") if isinstance(pr, dict) else {}
        self._set(out.job, "file", data.get("gcode_file") or data.get("file") or pr.get("file") if isinstance(pr, dict) else None)
        self._set(out.job, "time_remaining", self._first_defined_float([
            data.get("mc_remaining_time"),
            data.get("remain_time"),
            pr.get("time_remaining") if isinstance(pr, dict) else None,
            job_block.get("remaining") if isinstance(job_block, dict) else None,
        ]))
        self._set(out.job, "time_elapsed", self._first_defined_float([
            job_block.get("elapsed") if isinstance(job_block, dict) else None,
            pr.get("time_elapsed") if isinstance(pr, dict) else None,
        ]))

        # SPEED MODE
        self._set_attr(out, "speed_mode", data.get("print_speed_mode") or pr.get("speed_level") if isinstance(pr, dict) else None)

        # ERROR
        self._set_attr(out, "error", data.get("err") or data.get("mc_err") or (pr.get("error_code") if isinstance(pr, dict) else None))

        # EXTRA
        known = {
            "gcode_state",
            "mc_print_stage",
            "state",
            "mc_percent",
            "percent",
            "print",
            "print_status",
            "device",
            "heater",
            "cooling",
            "cooling_fan",
            "lights_report",
            "light",
            "ams",
            "filament",
            "material_system",
            "vt_tray",
            "vir_slot",
            "gcode_file",
            "file",
            "remain_time",
            "mc_remaining_time",
            "job",
            "layer_num",
            "total_layer_num",
            "big_fan1_speed",
            "big_fan2_speed",
            "heatbreak_fan_speed",
            "cooling_fan_speed",
            "nozzle_temper",
            "bed_temper",
            "spd_lvl",
            "mc_err",
            "err",
            "temperature",
        }
        for k, v in data.items():
            if k not in known:
                out.extra[k] = v

    # ------------------------------------------------------------------ #
    # Bambu H2D
    # ------------------------------------------------------------------ #
    def _map_bambu_h2d(self, data: Dict[str, Any], out: PrinterData) -> None:
        temp = data.get("temperature", {}) if isinstance(data, dict) else {}
        self._set(out.temperature, "nozzle", self._safe_float(temp.get("nozzle")))
        self._set(out.temperature, "bed", self._safe_float(temp.get("bed")))
        self._set(out.temperature, "chamber", self._safe_float(temp.get("chamber")))

        fan = data.get("cooling_fan", {}) if isinstance(data, dict) else {}
        self._set(out.fan, "part_cooling", self._safe_float(fan.get("toolhead_fan")))
        self._set(out.fan, "chamber", self._safe_float(fan.get("chamber_fan")))

        job = data.get("job", {}) if isinstance(data, dict) else {}
        self._set(out.job, "file", job.get("name"))
        self._set(out.job, "time_elapsed", job.get("elapsed"))
        self._set(out.job, "time_remaining", job.get("remaining"))

        out.state = data.get("state") or job.get("state")
        out.progress = self._safe_float(job.get("progress") if isinstance(job, dict) else None)

        out.ams = data.get("material_system")
        out.error = data.get("error")

        known = {"temperature", "cooling_fan", "job", "material_system", "error", "state", "progress"}
        for k, v in data.items():
            if k not in known:
                out.extra[k] = v

    # ------------------------------------------------------------------ #
    # Klipper / Moonraker
    # ------------------------------------------------------------------ #
    def _map_klipper(self, data: Dict[str, Any], out: PrinterData) -> None:
        status = data.get("status") or data

        print_stats = status.get("print_stats", {})
        heater_bed = status.get("heater_bed", {})
        extruder = status.get("extruder", {})
        fan = status.get("fan") or status.get("part_fan") or {}
        display_status = status.get("display_status", {})

        out.state = print_stats.get("state")
        prog = print_stats.get("progress")
        if prog is not None:
            out.progress = float(prog) * 100.0 if prog <= 1 else float(prog)

        self._set(out.temperature, "nozzle", self._safe_float(extruder.get("temperature")))
        self._set(out.temperature, "bed", self._safe_float(heater_bed.get("temperature")))
        chamber = None
        temp_sensors = status.get("temperature_sensor") or {}
        if isinstance(temp_sensors, dict):
            chamber_sensor = temp_sensors.get("chamber") or temp_sensors.get("Chamber")
            if isinstance(chamber_sensor, dict):
                chamber = chamber_sensor.get("temperature")
        self._set(out.temperature, "chamber", self._safe_float(chamber))

        fan_speed = fan.get("speed")
        if fan_speed is not None:
            try:
                out.fan["part_cooling"] = float(fan_speed) * 100.0 if float(fan_speed) <= 1 else float(fan_speed)
            except Exception:
                out.fan["part_cooling"] = None

        cur_layer = display_status.get("layer")
        total_layer = display_status.get("total_layer")
        self._set(out.layer, "current", self._safe_int(cur_layer))
        self._set(out.layer, "total", self._safe_int(total_layer))
        if (
            out.layer["current"] is not None
            and out.layer["total"] is not None
            and out.layer["current"] > out.layer["total"]
        ):
            out.layer["current"] = out.layer["total"]

        out.job["file"] = print_stats.get("filename")
        out.job["time_elapsed"] = print_stats.get("print_duration") or print_stats.get("total_duration")
        out.job["time_remaining"] = print_stats.get("time_remaining") or display_status.get("estimated_time_remaining")

        if out.state and str(out.state).lower() == "error":
            out.error = "print_error"

        known_top = {"status"}
        for k, v in data.items():
            if k not in known_top:
                out.extra[k] = v

        known_status = {
            "print_stats",
            "heater_bed",
            "extruder",
            "fan",
            "part_fan",
            "display_status",
            "temperature_sensor",
        }
        for k, v in status.items():
            if k not in known_status:
                out.extra[f"status.{k}"] = v

    # ------------------------------------------------------------------ #
    # Fallback – alles in extra
    # ------------------------------------------------------------------ #
    def _map_generic(self, data: Dict[str, Any], out: PrinterData) -> None:
        try:
            out.extra = dict(data)
        except Exception:
            out.extra = {}

    # ------------------------------------------------------------------ #
    # Helper
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
        cur = data
        try:
            for p in path:
                if isinstance(cur, list) and isinstance(p, int):
                    cur = cur[p]
                elif isinstance(cur, dict):
                    cur = cur[p]
                else:
                    return default
            return cur
        except Exception:
            return default

    def _first_defined_float(self, values) -> Optional[float]:
        for v in values:
            f = self._safe_float(v)
            if f is not None:
                return f
        return None

    def _set(self, target: Dict[str, Any], key: str, value: Any) -> None:
        if value is not None:
            target[key] = value

    def _set_attr(self, obj: Any, attr: str, value: Any) -> None:
        if value is not None:
            setattr(obj, attr, value)
