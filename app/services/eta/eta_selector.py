"""
Zentrale ETA-Auswahl basierend auf Drucker-Modell.
"""

from datetime import datetime
from typing import Optional

from .bambu_a_series_eta import estimate_remaining_time_from_layers
from .bambu_p_series_eta import estimate_eta_p_series
from .bambu_x_series_eta import estimate_eta_x_series


# Modell-Mapping
A_SERIES_MODELS = {"A1", "A1MINI", "A1 MINI"}
P_SERIES_MODELS = {"P1P", "P1S"}
X_SERIES_MODELS = {"X1", "X1C", "X1E"}


def calculate_eta(
    printer_model: Optional[str],
    started_at: Optional[datetime],
    layer_num: Optional[int],
    total_layer_num: Optional[int],
    bambu_remaining_time: Optional[int],
) -> Optional[int]:
    """
    Zentrale ETA-Berechnung basierend auf Drucker-Modell.

    Args:
        printer_model: Modell-Name (z.B. "X1C", "P1S", "A1")
        started_at: Job-Start-Zeit
        layer_num: Aktueller Layer
        total_layer_num: Gesamt-Layer
        bambu_remaining_time: Von Bambu gemeldete Restzeit (Sekunden)

    Returns:
        ETA in Sekunden, oder None wenn nicht berechenbar
    """
    # Kein Modell → keine spezifische ETA
    if not printer_model:
        return None

    # Normalisiere Modell-Name
    model_upper = printer_model.upper().strip()

    # A-Serie: Layer-basierte ETA
    if model_upper in A_SERIES_MODELS:
        return estimate_remaining_time_from_layers(
            started_at=started_at,
            layer_num=layer_num,
            total_layer_num=total_layer_num,
        )

    # P-Serie: Hybrid-ETA
    if model_upper in P_SERIES_MODELS:
        layer_eta = estimate_remaining_time_from_layers(
            started_at=started_at,
            layer_num=layer_num,
            total_layer_num=total_layer_num,
        )
        return estimate_eta_p_series(
            bambu_remaining_time=bambu_remaining_time,
            layer_eta=layer_eta,
        )

    # X-Serie: Bambu-ETA direkt
    if model_upper in X_SERIES_MODELS:
        return estimate_eta_x_series(bambu_remaining_time)

    # Unbekanntes Modell → keine ETA
    return None
