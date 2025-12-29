class PrinterData:
    """Einheitliches Ausgabeformat für ALLE Bambu Lab Drucker."""

    def __init__(self):
        self.state = None
        self.progress = None
        self.sub_state = None

        self.temperature = {
            "nozzle": None,
            "bed": None,
            "chamber": None
        }

        self.fan = {
            "part_cooling": None,
            "aux": None,
            "chamber": None
        }

        self.layer = {
            "current": None,
            "total": None
        }

        self.speed_mode = None

        self.light = {
            "state": None,
            "brightness": None
        }

        self.ams = None

        self.job = {
            "file": None,
            "time_elapsed": None,
            "time_remaining": None
        }

        self.error = None
        self.extra = {}  # Alle unbekannten Felder
