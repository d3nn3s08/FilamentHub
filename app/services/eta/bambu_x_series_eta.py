"""
ETA für Bambu X-Serie (X1, X1C).

Grund: Bambu-eigene ETA ist bei X-Serie zuverlässig und präzise.
Strategie: Verwende Bambu-ETA direkt.
"""

from typing import Optional


def estimate_eta_x_series(
    bambu_remaining_time: Optional[int],
) -> Optional[int]:
    """
    ETA für X-Serie (direkt von Bambu).

    Args:
        bambu_remaining_time: Von Bambu gemeldete Restzeit (Sekunden)

    Returns:
        Bambu-ETA in Sekunden, oder None
    """
    # Validierung
    if bambu_remaining_time is None or bambu_remaining_time <= 0:
        return None

    return bambu_remaining_time
