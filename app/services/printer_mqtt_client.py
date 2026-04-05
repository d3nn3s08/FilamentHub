"""Re-export wrapper for the runtime PrinterMQTTClient.

This keeps `app.services.printer_mqtt_client` as the stable import path while
reusing the existing implementation in `services.printer_mqtt_client`.
"""

from services.printer_mqtt_client import PrinterMQTTClient

__all__ = ["PrinterMQTTClient"]
