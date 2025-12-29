from printer_data import PrinterData

class UniversalMapper:
    """Universal Mapper für ALLE BambuLab Drucker."""

    def __init__(self, model: str):
        self.model = model.upper()

    def map(self, data: dict) -> PrinterData:
        out = PrinterData()

        # ======= STATUS =======
        if mc := data.get("mc_print"):
            out.state = mc.get("stage")
            out.progress = mc.get("progress")
            out.sub_state = mc.get("sub_stage")

            out.layer["current"] = mc.get("layer_num")
            out.layer["total"] = mc.get("total_layers")

            out.job["file"] = mc.get("file_name")
            out.job["time_elapsed"] = mc.get("time_elapsed")
            out.job["time_remaining"] = mc.get("time_remaining")

            out.error = mc.get("error_code")
            out.speed_mode = mc.get("print_speed_mode")

        elif pr := data.get("print"):
            out.state = pr.get("gcode_state")
            out.progress = pr.get("progress")

            out.layer["current"] = pr.get("layer_num")
            out.layer["total"] = pr.get("total_layer")

            out.job["file"] = pr.get("file")
            out.job["time_elapsed"] = pr.get("time_elapsed")
            out.job["time_remaining"] = pr.get("time_remaining")

            out.error = pr.get("error_code")
            out.speed_mode = pr.get("speed_level")

        # ======= TEMPERATURE =======
        if heater := data.get("heater"):
            out.temperature["nozzle"] = heater.get("nozzle_temper") or heater.get("nozzle_temp")
            out.temperature["bed"] = heater.get("bed_temper") or heater.get("bed_temp")
            out.temperature["chamber"] = heater.get("chamber_temper") or heater.get("chamber_temp")

        if temp := data.get("temperature"):  # H2D
            out.temperature["nozzle"] = temp.get("nozzle")
            out.temperature["bed"] = temp.get("bed")
            out.temperature["chamber"] = temp.get("chamber")

        # ======= FANS =======
        if cooling := data.get("cooling"):
            out.fan["part_cooling"] = cooling.get("fan_1_speed") or cooling.get("fan_speed")
            out.fan["aux"] = cooling.get("fan_2_speed")
            out.fan["chamber"] = cooling.get("fan_3_speed")

        if fan := data.get("fan"):
            out.fan["part_cooling"] = fan.get("speed")

        if f := data.get("cooling_fan"):  # H2D
            out.fan["part_cooling"] = f.get("toolhead_fan")
            out.fan["chamber"] = f.get("chamber_fan")

        # ======= LIGHT =======
        if light := data.get("light"):
            out.light["state"] = light.get("light_state") or light.get("on")
            out.light["brightness"] = light.get("light_strength") or light.get("strength")

        # ======= AMS =======
        if ams := data.get("ams"):
            out.ams = ams
        if fil := data.get("filament"):
            out.ams = fil
        if matsys := data.get("material_system"):  # H2D
            out.ams = matsys

        # ======= ERROR =======
        if err := data.get("error"):
            out.error = err

        # ======= JOB (H2D) =======
        if job := data.get("job"):
            out.job["file"] = job.get("name")
            out.job["time_elapsed"] = job.get("elapsed")
            out.job["time_remaining"] = job.get("remaining")

        # ======= EXTRA FELDER =======
        known = {
            "mc_print", "print", "heater", "cooling", "fan",
            "light", "ams", "filament", "temperature",
            "material_system", "job", "error"
        }

        for k, v in data.items():
            if k not in known:
                out.extra[k] = v

        return out
