"""
BambuCloudConfig Model - Speichert Bambu Cloud Konfiguration
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, ConfigDict


class BambuCloudConfigBase(SQLModel):
    """Basis-Felder für Bambu Cloud Konfiguration"""

    # Authentifizierung (Token wird verschlüsselt gespeichert)
    access_token_encrypted: Optional[str] = None  # Verschlüsselter Access Token
    refresh_token_encrypted: Optional[str] = None  # Verschlüsselter Refresh Token
    token_expires_at: Optional[str] = None  # Ablaufzeitpunkt des Tokens

    # Account Info
    bambu_user_id: Optional[str] = None  # Bambu Cloud User ID
    bambu_username: Optional[str] = None  # Benutzername (Email)
    region: str = "eu"  # Region: eu, us, cn

    # Sync-Einstellungen
    sync_enabled: bool = False  # Ist Cloud-Sync aktiviert?
    sync_paused: bool = False  # Pause-Modus: Credentials bleiben, Sync pausiert
    dry_run_mode: bool = False  # Test-Modus: Keine DB-Änderungen, nur Logging
    auto_sync_interval_minutes: int = 30  # Auto-Sync Intervall
    sync_on_print_start: bool = True  # Sync bei Druckstart
    sync_on_print_end: bool = True  # Sync bei Druckende

    # Konflikt-Behandlung
    conflict_resolution_mode: str = "ask"  # 'ask', 'prefer_local', 'prefer_cloud'
    auto_accept_cloud_weight: bool = False  # Cloud-Gewicht automatisch übernehmen
    weight_tolerance_percent: float = 5.0  # Toleranz für Gewichtsabweichungen

    # Status
    last_sync_at: Optional[str] = None  # Letzter Sync-Zeitpunkt
    last_sync_status: Optional[str] = None  # 'success', 'error', 'partial'
    last_error_message: Optional[str] = None  # Letzte Fehlermeldung
    connection_status: str = "disconnected"  # 'connected', 'disconnected', 'error'

    # Cloud MQTT Settings
    cloud_mqtt_enabled: bool = False  # Cloud MQTT statt lokalem MQTT verwenden
    cloud_mqtt_connected: bool = False  # Aktueller Verbindungsstatus
    cloud_mqtt_last_message: Optional[str] = None  # Letzter Empfang

    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BambuCloudConfig(BambuCloudConfigBase, table=True):
    """Bambu Cloud Konfiguration - Singleton (nur ein Eintrag)"""
    __tablename__ = "bambu_cloud_config"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class BambuCloudConfigCreate(BaseModel):
    """Schema zum Erstellen/Aktualisieren der Konfiguration"""
    model_config = ConfigDict(extra="ignore")

    # Token wird im Klartext empfangen und vom Service verschlüsselt
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

    bambu_username: Optional[str] = None
    region: str = "eu"

    sync_enabled: bool = False
    sync_paused: bool = False
    dry_run_mode: bool = False
    auto_sync_interval_minutes: int = 30
    sync_on_print_start: bool = True
    sync_on_print_end: bool = True

    conflict_resolution_mode: str = "ask"
    auto_accept_cloud_weight: bool = False
    weight_tolerance_percent: float = 5.0

    cloud_mqtt_enabled: bool = False


class BambuCloudConfigRead(BaseModel):
    """Schema für API-Ausgabe (ohne sensible Daten)"""
    model_config = ConfigDict(from_attributes=True)

    id: str

    # Account Info (ohne Token!)
    bambu_user_id: Optional[str] = None
    bambu_username: Optional[str] = None
    region: str = "eu"
    has_token: bool = False  # Nur ob Token vorhanden, nicht der Token selbst
    token_expires_at: Optional[str] = None

    # Sync-Einstellungen
    sync_enabled: bool = False
    sync_paused: bool = False
    dry_run_mode: bool = False
    auto_sync_interval_minutes: int = 30
    sync_on_print_start: bool = True
    sync_on_print_end: bool = True

    # Konflikt-Behandlung
    conflict_resolution_mode: str = "ask"
    auto_accept_cloud_weight: bool = False
    weight_tolerance_percent: float = 5.0

    # Status
    last_sync_at: Optional[str] = None
    last_sync_status: Optional[str] = None
    last_error_message: Optional[str] = None
    connection_status: str = "disconnected"

    # Cloud MQTT
    cloud_mqtt_enabled: bool = False
    cloud_mqtt_connected: bool = False
    cloud_mqtt_last_message: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BambuCloudSyncStatus(BaseModel):
    """Status des Cloud-Syncs"""
    is_syncing: bool = False
    is_connected: bool = False
    is_paused: bool = False
    is_dry_run: bool = False
    has_config: bool = False
    last_sync: Optional[str] = None
    last_sync_at: Optional[str] = None
    last_sync_status: Optional[str] = None
    synced_printers: int = 0
    synced_spools_count: int = 0
    pending_conflicts: int = 0
    conflicts_count: int = 0
    errors: list[str] = []
    # Fehlerdetails für UI-Anzeige
    connection_status: Optional[str] = None       # "connected", "error", "disconnected", None
    last_error_message: Optional[str] = None      # z.B. "Token-Fehler: Ungültiger Token..."
    # Token-Ablaufzeit für UI-Warnungen (ISO-String UTC)
    token_expires_at: Optional[str] = None
