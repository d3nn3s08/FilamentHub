from run import klipper_logger, error_logger
import requests


class KlipperService:
    """
    Service für Klipper-Drucker. Modular, robust,
    später kompatibel mit Moonraker / KlipperStatus.
    """

    def __init__(self, host: str = None):
        self.host = host
        klipper_logger.info("KlipperService initialisiert.")

    def is_configured(self) -> bool:
        configured = bool(self.host)
        klipper_logger.debug(f"Konfiguration geprüft: {configured}")
        return configured

    def get_status(self) -> dict | None:
        if not self.is_configured():
            klipper_logger.warning("KlipperService nicht konfiguriert.")
            return None

        try:
            url = f"http://{self.host}/printer/info"
            klipper_logger.info(f"Abfrage: {url}")

            # Platzhalter – Moonraker API später echte Daten
            response = requests.get(url, timeout=3)

            if response.status_code != 200:
                klipper_logger.warning(f"Klipper Error: {response.status_code}")
                return None

            data = response.json()
            klipper_logger.debug(f"KlipperStatus: {data}")
            return data

        except Exception as e:
            error_logger.exception(f"Klipper API Fehler: {e}")
            return None

    def send_gcode(self, gcode: str) -> bool:
        try:
            klipper_logger.info(f"Sende GCODE: {gcode}")
            # später -> POST an Moonraker API
            return True
        except Exception as e:
            error_logger.exception(f"GCODE Fehler: {e}")
            return False
