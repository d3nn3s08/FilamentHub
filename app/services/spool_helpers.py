"""
============================================================
EXTERNAL SPOOL TRAY HELPERS

Zentrale Logik für druckermodellabhängige externe Spulen.

TRAY-ID REGELN:
  A-Serie (A1 / A1 mini):
    Externe Spule = Tray 254

  X1 / P-Serie:
    Externe Spule = Tray 255

VERWENDUNG:
  - Verwende IMMER diese Helpers statt hardcoded 254/255
  - get_external_tray_id(printer) → int (254 oder 255)
  - is_external_tray(printer, tray_id) → bool
============================================================
"""

from typing import Optional
from app.models.printer import Printer


def get_external_tray_id(printer: Optional[Printer]) -> int:
    """
    Gibt die Tray-ID für externe Spulen basierend auf Drucker-Serie zurück.

    A-Serie (A1 / A1 mini): 254
    X1 / P-Serie:          255

    Args:
        printer: Printer-Objekt (oder None für Fallback)

    Returns:
        254 (A-Serie) oder 255 (X1/P-Serie)
    """
    if printer is None:
        return 255  # Fallback: X1 Default

    series = str(getattr(printer, "series", "UNKNOWN") or "UNKNOWN").upper()

    if series == "A":
        return 254

    return 255


def is_external_tray(printer: Optional[Printer], tray_id: Optional[int]) -> bool:
    """
    Prüft, ob eine Tray-ID eine externe Spule darstellt.

    Berücksichtigt druckerspezifische Unterschiede:
    - A1 / A1 mini: Tray 254
    - X1 / P-Serie: Tray 255

    Args:
        printer: Printer-Objekt
        tray_id: Tray-ID zum Prüfen

    Returns:
        True wenn externe Spule, sonst False
    """
    if tray_id is None or printer is None:
        return False

    expected_tray = get_external_tray_id(printer)
    return int(tray_id) == expected_tray
