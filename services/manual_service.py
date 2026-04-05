import logging

app_logger = logging.getLogger("services")


class ManualService:
    """
    Reines manuelles Eingabemodul.
    Nützlich, wenn:
    - kein LAN-Modus
    - keine API
    - keine Automatisierung

    Hier kann der Benutzer Daten selbst eintragen.
    """

    def __init__(self):
        app_logger.info("ManualService initialisiert.")

    def set_filament_usage(self, grams: float) -> bool:
        try:
            app_logger.info(f"Manuelle Filamentmenge gesetzt: {grams} g")
            # Später Speicherung in Datenbank
            return True
        except Exception:
            app_logger.exception("Fehler beim Setzen")
            return False

    def set_printer_status(self, status: str) -> bool:
        try:
            app_logger.info(f"Manueller Status: {status}")
            return True
        except Exception:
            app_logger.exception("Fehler beim manuellen Status")
            return False
