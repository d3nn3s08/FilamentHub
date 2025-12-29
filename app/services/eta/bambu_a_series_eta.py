"""
Layer-basierte ETA für Bambu A-Serie (A1, A1 Mini).

Grund: Bambu-eigene ETA ist bei A-Serie unzuverlässig.
Strategie: Berechne ETA basierend auf durchschnittlicher Layer-Zeit.
"""

from datetime import datetime
from typing import Optional


def estimate_remaining_time_from_layers(
    started_at: datetime,
    layer_num: int,
    total_layer_num: int,
    now: Optional[datetime] = None,
    min_layers_for_eta: int = 5,
) -> Optional[int]:
    """
    Layer-basierte ETA-Berechnung.

    Args:
        started_at: Wann der Job gestartet wurde
        layer_num: Aktueller Layer
        total_layer_num: Gesamt-Layer
        now: Aktueller Zeitpunkt (für Tests)
        min_layers_for_eta: Minimum Layers bevor ETA berechnet wird

    Returns:
        Verbleibende Sekunden (int) oder None wenn ETA nicht sinnvoll
    """
    # Validierung: Pflichtfelder
    if not started_at:
        return None
    if layer_num is None or total_layer_num is None:
        return None

    # Zu früh für sinnvolle ETA
    if layer_num < min_layers_for_eta:
        return None

    # Job ist fertig oder über 100%
    if total_layer_num <= layer_num:
        return 0

    # Berechne verstrichene Zeit
    current_time = now if now else datetime.utcnow()
    elapsed = (current_time - started_at).total_seconds()

    # Verhindere Division durch 0
    if layer_num <= 0:
        return None

    # Berechne durchschnittliche Zeit pro Layer
    avg_time_per_layer = elapsed / layer_num

    # Berechne verbleibende Layer
    remaining_layers = total_layer_num - layer_num

    # Berechne ETA
    eta_seconds = avg_time_per_layer * remaining_layers

    # Sicherheit: Niemals negativ
    return max(0, int(eta_seconds))
