"""
Hybrid-ETA für Bambu P-Serie (P1P, P1S).

Grund: Bambu-ETA ist brauchbar, aber nicht immer stabil.
Strategie: Verwende max(Bambu-ETA, Layer-ETA) für konservative Schätzung.
"""

from typing import Optional


def estimate_eta_p_series(
    bambu_remaining_time: Optional[int],
    layer_eta: Optional[int],
) -> Optional[int]:
    """
    Hybrid-ETA für P-Serie.

    Args:
        bambu_remaining_time: Von Bambu gemeldete Restzeit (Sekunden)
        layer_eta: Layer-basierte ETA (Sekunden)

    Returns:
        Konservativere (größere) ETA in Sekunden, oder None
    """
    # Bereinige negative/0-Werte
    bambu_valid = bambu_remaining_time if (bambu_remaining_time and bambu_remaining_time > 0) else None
    layer_valid = layer_eta if (layer_eta and layer_eta > 0) else None

    # Beide None → keine ETA
    if bambu_valid is None and layer_valid is None:
        return None

    # Nur eine vorhanden
    if bambu_valid is None:
        return layer_valid
    if layer_valid is None:
        return bambu_valid

    # Beide vorhanden: Nimm die konservativere (größere)
    return max(bambu_valid, layer_valid)
