"""Add Bambu Cloud Integration tables and columns

Revision ID: 20260129_add_bambu_cloud_integration
Revises: 1dda5a552fbf
Create Date: 2026-01-29 13:00:00.000000

Dieses System implementiert:
1. BambuCloudConfig Tabelle (Singleton für Cloud-Konfiguration)
2. CloudConflicts Tabelle (Konflikt-Protokollierung)
3. Neue Felder in Spool für Cloud-Tracking
4. Neue Felder in Printer für Cloud-Sync
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "20260129_add_bambu_cloud_integration"
down_revision = "1dda5a552fbf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade-Migration:
    - Erstellt BambuCloudConfig Tabelle
    - Erstellt CloudConflicts Tabelle
    - Erweitert Spool-Tabelle um Cloud-Sync Felder
    - Erweitert Printer-Tabelle um Cloud-Sync Felder
    """

    print(">> Fuege Bambu Cloud Integration hinzu...")

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    # ========================================
    # TEIL 1: BAMBU_CLOUD_CONFIG TABLE
    # ========================================

    print("  >> Erstelle bambu_cloud_config Tabelle...")

    if "bambu_cloud_config" not in existing_tables:
        op.create_table(
            "bambu_cloud_config",
            # Primary Key
            sa.Column("id", sa.String(36), primary_key=True),

            # Authentifizierung (verschluesselt)
            sa.Column("access_token_encrypted", sa.Text(), nullable=True),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(), nullable=True),

            # Account Info
            sa.Column("bambu_user_id", sa.String(100), nullable=True),
            sa.Column("bambu_username", sa.String(255), nullable=True),
            sa.Column("region", sa.String(10), nullable=False, server_default="eu"),

            # Sync-Einstellungen
            sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("auto_sync_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("sync_on_print_start", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("sync_on_print_end", sa.Boolean(), nullable=False, server_default="1"),

            # Konflikt-Behandlung
            sa.Column("conflict_resolution_mode", sa.String(20), nullable=False, server_default="ask"),
            sa.Column("auto_accept_cloud_weight", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("weight_tolerance_percent", sa.Float(), nullable=False, server_default="5.0"),

            # Status
            sa.Column("last_sync_at", sa.DateTime(), nullable=True),
            sa.Column("last_sync_status", sa.String(20), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("connection_status", sa.String(20), nullable=False, server_default="disconnected"),

            # Timestamps
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        print("    >> bambu_cloud_config Tabelle erstellt")
    else:
        print("    >> Tabelle bambu_cloud_config existiert bereits, ueberspringe")

    # ========================================
    # TEIL 2: CLOUD_CONFLICTS TABLE
    # ========================================

    print("  >> Erstelle cloud_conflicts Tabelle...")

    if "cloud_conflicts" not in existing_tables:
        op.create_table(
            "cloud_conflicts",
            # Primary Key
            sa.Column("id", sa.String(36), primary_key=True),

            # Referenzen
            sa.Column("spool_id", sa.String(36), nullable=True),
            sa.Column("printer_id", sa.String(36), nullable=True),

            # Konflikt-Details
            sa.Column("conflict_type", sa.String(50), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),

            # Werte
            sa.Column("local_value", sa.Text(), nullable=True),
            sa.Column("cloud_value", sa.Text(), nullable=True),
            sa.Column("difference_percent", sa.Float(), nullable=True),

            # Status
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("resolution", sa.String(50), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by", sa.String(50), nullable=True),

            # Kontext
            sa.Column("detected_at", sa.DateTime(), nullable=False),
            sa.Column("sync_session_id", sa.String(36), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),

            # Timestamps
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), nullable=True),

            # Foreign Keys
            sa.ForeignKeyConstraint(
                ["spool_id"],
                ["spool.id"],
                name="fk_cloud_conflicts_spool_id",
                ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["printer_id"],
                ["printer.id"],
                name="fk_cloud_conflicts_printer_id",
                ondelete="SET NULL"
            ),
        )
        print("    >> cloud_conflicts Tabelle erstellt")
    else:
        print("    >> Tabelle cloud_conflicts existiert bereits, ueberspringe")

    # ========================================
    # TEIL 3: SPOOL TABLE - Neue Spalten
    # ========================================

    print("  >> Erweitere Spool-Tabelle...")

    existing_spool_columns = [col['name'] for col in inspector.get_columns('spool')]

    new_spool_columns = [
        ("cloud_tray_uuid", sa.Column("cloud_tray_uuid", sa.String(100), nullable=True)),
        ("last_verified_at", sa.Column("last_verified_at", sa.DateTime(), nullable=True)),
        ("cloud_sync_status", sa.Column("cloud_sync_status", sa.String(20), nullable=True)),
    ]

    for col_name, col_def in new_spool_columns:
        if col_name not in existing_spool_columns:
            op.add_column("spool", col_def)
            print(f"    >> Spalte {col_name} hinzugefuegt")
        else:
            print(f"    >> Spalte {col_name} existiert bereits, ueberspringe")

    # ========================================
    # TEIL 4: PRINTER TABLE - Neue Spalten
    # ========================================

    print("  >> Erweitere Printer-Tabelle...")

    existing_printer_columns = [col['name'] for col in inspector.get_columns('printer')]

    new_printer_columns = [
        ("bambu_device_id", sa.Column("bambu_device_id", sa.String(100), nullable=True)),
        ("cloud_sync_enabled", sa.Column("cloud_sync_enabled", sa.Boolean(), nullable=False, server_default="0")),
        ("last_cloud_sync", sa.Column("last_cloud_sync", sa.DateTime(), nullable=True)),
    ]

    for col_name, col_def in new_printer_columns:
        if col_name not in existing_printer_columns:
            op.add_column("printer", col_def)
            print(f"    >> Spalte {col_name} hinzugefuegt")
        else:
            print(f"    >> Spalte {col_name} existiert bereits, ueberspringe")

    # ========================================
    # TEIL 5: INDIZES
    # ========================================

    print("  >> Erstelle Indizes...")

    indices = [
        ("idx_cloud_conflicts_status", "cloud_conflicts", ["status"]),
        ("idx_cloud_conflicts_spool_id", "cloud_conflicts", ["spool_id"]),
        ("idx_cloud_conflicts_detected_at", "cloud_conflicts", ["detected_at"]),
        ("idx_spool_cloud_sync_status", "spool", ["cloud_sync_status"]),
        ("idx_spool_cloud_tray_uuid", "spool", ["cloud_tray_uuid"]),
        ("idx_printer_bambu_device_id", "printer", ["bambu_device_id"]),
    ]

    for idx_name, table, columns in indices:
        try:
            op.create_index(idx_name, table, columns)
            print(f"    >> Index {idx_name} erstellt")
        except Exception:
            print(f"    >> Index {idx_name} existiert bereits, ueberspringe")

    print("[OK] Bambu Cloud Integration Migration erfolgreich!")
    print("  [OK] BambuCloudConfig Tabelle erstellt")
    print("  [OK] CloudConflicts Tabelle erstellt")
    print("  [OK] Spool Cloud-Felder hinzugefuegt")
    print("  [OK] Printer Cloud-Felder hinzugefuegt")


def downgrade() -> None:
    """
    Downgrade-Migration:
    - Entfernt alle Aenderungen dieser Migration
    """

    print(">> Entferne Bambu Cloud Integration...")

    # Drop Indizes
    try:
        op.drop_index("idx_printer_bambu_device_id", "printer")
    except Exception:
        pass
    try:
        op.drop_index("idx_spool_cloud_tray_uuid", "spool")
    except Exception:
        pass
    try:
        op.drop_index("idx_spool_cloud_sync_status", "spool")
    except Exception:
        pass
    try:
        op.drop_index("idx_cloud_conflicts_detected_at", "cloud_conflicts")
    except Exception:
        pass
    try:
        op.drop_index("idx_cloud_conflicts_spool_id", "cloud_conflicts")
    except Exception:
        pass
    try:
        op.drop_index("idx_cloud_conflicts_status", "cloud_conflicts")
    except Exception:
        pass

    # Drop Printer-Spalten
    try:
        op.drop_column("printer", "last_cloud_sync")
    except Exception:
        pass
    try:
        op.drop_column("printer", "cloud_sync_enabled")
    except Exception:
        pass
    try:
        op.drop_column("printer", "bambu_device_id")
    except Exception:
        pass

    # Drop Spool-Spalten
    try:
        op.drop_column("spool", "cloud_sync_status")
    except Exception:
        pass
    try:
        op.drop_column("spool", "last_verified_at")
    except Exception:
        pass
    try:
        op.drop_column("spool", "cloud_tray_uuid")
    except Exception:
        pass

    # Drop Tabellen
    op.drop_table("cloud_conflicts")
    op.drop_table("bambu_cloud_config")

    print("[OK] Downgrade erfolgreich abgeschlossen!")
