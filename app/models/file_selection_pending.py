"""
File Selection Pending - Model für ausstehende File-Auswahl-Entscheidungen

Wenn Title-Matching Score < 60% ist, wird eine File-Selection-Request erstellt
und der User muss die richtige Datei auswählen.
"""
from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime


class FileSelectionPending(SQLModel, table=True):
    """
    Ausstehende File-Auswahl-Entscheidung

    Wird erstellt wenn:
    - FTP G-Code Download fehlschlägt (Filename-Match)
    - Title-Matching Score < 60%
    - User muss manuell richtige Datei auswählen
    """
    __tablename__ = "file_selection_pending"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Job Info
    job_id: str = Field(index=True)  # Job für den die Datei gesucht wird
    job_name: str  # Job-Name aus MQTT
    printer_ip: str  # Drucker IP für FTP
    api_key: str  # FTPS Access Code

    # Matching Info
    target_filename: str  # Gesuchter Dateiname aus MQTT
    best_match_filename: Optional[str] = None  # Beste Match wenn Score < 60%
    best_match_score: Optional[int] = None  # Score 0-100
    best_match_title: Optional[str] = None  # Title der besten Match

    # Kandidaten (JSON Array)
    candidates_json: str = "{}"  # JSON: [{"filename": "...", "title": "...", "score": 85}, ...]

    # Status
    status: str = "pending"  # pending | resolved | cancelled
    resolved_filename: Optional[str] = None  # User-Auswahl
    resolved_at: Optional[datetime] = None
    resolved_weight_g: Optional[float] = None  # Extrahiertes Gewicht

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
