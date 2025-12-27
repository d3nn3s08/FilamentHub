"""
Service für Spulen-Nummern-Verwaltung

Implementiert das Spulen-Nummern-System gemäß Spezifikation v4:
- Automatische Nummernvergabe mit Recycling
- Denormalisierung von Material-Daten
- Snapshot-Erstellung für Job-Historie
"""
from typing import Optional
from sqlmodel import Session, select, func
from datetime import datetime

from app.models.spool import Spool
from app.models.material import Material


def get_next_spool_number(session: Session) -> int:
    """
    Findet die niedrigste freie Spulen-Nummer (Recycling-System)

    Beispiel:
    - Spulen #1, #2, #4 existieren
    - #3 wurde gelöscht
    - Ergebnis: 3 (recycelt die gelöschte Nummer)

    Args:
        session: SQLModel Session

    Returns:
        int: Nächste freie Spulen-Nummer
    """
    # Hole alle verwendeten Nummern
    stmt = select(Spool.spool_number).where(Spool.spool_number.is_not(None))
    used_numbers = set(num for num in session.exec(stmt).all() if num is not None)

    # Finde erste Lücke (Recycling)
    for i in range(1, 10000):
        if i not in used_numbers:
            return i

    # Fallback: MAX + 1 (sollte nie erreicht werden)
    max_num = session.exec(
        select(func.max(Spool.spool_number))
    ).one_or_none()
    return (max_num or 0) + 1


def assign_spool_number(spool: Spool, session: Session) -> int:
    """
    Weist einer Spule eine Nummer zu und denormalisiert Material-Daten

    Diese Funktion:
    1. Findet die niedrigste freie Nummer
    2. Kopiert name, vendor aus material-Tabelle
    3. Extrahiert Farbe aus tray_color (falls Bambu-Spule)

    Args:
        spool: Spool-Objekt (wird modifiziert)
        session: SQLModel Session

    Returns:
        int: Zugewiesene Spulen-Nummer
    """
    # 1. Nummer zuweisen
    spool.spool_number = get_next_spool_number(session)

    # 2. Material-Daten kopieren (denormalisieren für schnelle Suche)
    if spool.material_id:
        material = session.get(Material, spool.material_id)
        if material:
            spool.name = material.name
            spool.vendor = material.brand

    # 3. Farbe extrahieren oder setzen
    if not spool.color and spool.tray_color:
        # Bambu-Spule: Extrahiere Farbe aus Hex-Code
        spool.color = extract_color_from_hex(spool.tray_color)
    elif not spool.color:
        # Fallback: unknown
        spool.color = "unknown"

    return spool.spool_number


def extract_color_from_hex(hex_color: str) -> str:
    """
    Konvertiert Bambu Hex-Farbe (z.B. "000000FF") zu lesbarem Namen

    Vereinfachte Farb-Erkennung basierend auf RGB-Werten.

    Args:
        hex_color: Hex-String (z.B. "FF0000FF" für rot)

    Returns:
        str: Farb-Name (black, white, red, green, blue, yellow, mixed, unknown)

    Beispiele:
        "000000FF" → "black"
        "FFFFFFFF" → "white"
        "FF0000FF" → "red"
        "00FF00FF" → "green"
    """
    if not hex_color or len(hex_color) < 6:
        return "unknown"

    # Erste 6 Zeichen = RGB (letzte 2 = Alpha-Channel)
    rgb_hex = hex_color[:6]

    try:
        # Konvertiere zu RGB-Werten (0-255)
        r = int(rgb_hex[0:2], 16)
        g = int(rgb_hex[2:4], 16)
        b = int(rgb_hex[4:6], 16)

        # Einfache Farb-Erkennung
        if r < 50 and g < 50 and b < 50:
            return "black"
        elif r > 200 and g > 200 and b > 200:
            return "white"
        elif r > 150 and g < 100 and b < 100:
            return "red"
        elif r < 100 and g > 150 and b < 100:
            return "green"
        elif r < 100 and g < 100 and b > 150:
            return "blue"
        elif r > 150 and g > 150 and b < 100:
            return "yellow"
        elif r > 150 and g < 100 and b > 150:
            return "purple"
        elif r > 150 and g > 100 and b < 100:
            return "orange"
        else:
            return "mixed"
    except (ValueError, IndexError):
        return "unknown"


def create_job_snapshot(spool: Spool) -> dict:
    """
    Erstellt Snapshot-Daten für Job-Historie

    Dieser Snapshot wird in der job-Tabelle gespeichert und bewahrt
    die Spulen-Daten zum Zeitpunkt des Job-Starts auf.

    Auch wenn die Spule später gelöscht oder die Nummer recycelt wird,
    bleibt die Historie korrekt.

    Args:
        spool: Spool-Objekt

    Returns:
        dict: Snapshot-Daten für job-Tabelle

    Beispiel:
        {
            "spool_number": 3,
            "spool_name": "PLA Basic",
            "spool_vendor": "Bambu Lab",
            "spool_color": "black",
            "spool_created_at": "2024-11-01T10:00:00"
        }
    """
    return {
        "spool_number": spool.spool_number,
        "spool_name": spool.name,
        "spool_vendor": spool.vendor,
        "spool_color": spool.color,
        "spool_created_at": spool.created_at,
    }


def update_spool_denormalized_fields(spool: Spool, session: Session) -> None:
    """
    Aktualisiert denormalisierte Felder einer Spule

    Nützlich wenn sich Material-Daten ändern und Spule aktualisiert werden soll.

    Args:
        spool: Spool-Objekt (wird modifiziert)
        session: SQLModel Session
    """
    if spool.material_id:
        material = session.get(Material, spool.material_id)
        if material:
            spool.name = material.name
            spool.vendor = material.brand
