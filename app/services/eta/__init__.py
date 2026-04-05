"""
ETA (Estimated Time Remaining) Modul für BambuLab Drucker.

WICHTIG:
- ETA ist REINE ANZEIGE-INFORMATION
- Hat KEINE Auswirkung auf Job-Logik
- Kann None sein (dann UI zeigt "—")
- Darf niemals negativ sein
"""

from .eta_selector import calculate_eta

__all__ = ["calculate_eta"]
