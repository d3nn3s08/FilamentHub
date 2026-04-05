"""Add weight history system and AMS type tracking

Revision ID: 20260117_add_weight_history_system
Revises: bfb91b256607
Create Date: 2025-01-17 15:00:00.000000

Dieses System implementiert:
1. Weight History Tracking (Audit-Trail für Gewichtsänderungen)
2. AMS Type Unterscheidung (AMS Lite vs AMS Full)
3. Cloud-Sync Tracking (Bambu Cloud vs FilamentHub DB)
4. Archiv-System für recycelte Spulen-Nummern
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "20260117_add_weight_history_system"
down_revision = "bfb91b256607"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade-Migration:
    - Fügt Weight History Tabelle hinzu
    - Erweitert Spool-Tabelle um AMS-Tracking und Cloud-Sync
    - Erstellt Indizes für Performance
    """

    print(">> Fuege Weight History System hinzu...")

    # Check if columns already exist (skip if they do)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('spool')]

    # ========================================
    # TEIL 1: SPOOL TABLE - Neue Spalten
    # ========================================

    print("  >> Erweitere Spool-Tabelle...")

    # AMS-Tracking (nur wenn nicht existiert)
    if "last_seen_in_ams_type" not in existing_columns:
        op.add_column(
            "spool",
            sa.Column("last_seen_in_ams_type", sa.String(20), nullable=True),
        )
    else:
        print("    >> Spalte last_seen_in_ams_type existiert bereits, ueberspringe")

    if "last_seen_timestamp" not in existing_columns:
        op.add_column(
            "spool",
            sa.Column("last_seen_timestamp", sa.DateTime(), nullable=True),
        )
    else:
        print("    >> Spalte last_seen_timestamp existiert bereits, ueberspringe")

    # Cloud-Sync Tracking (skip if exists)
    for col_name, col_def in [
        ("cloud_weight", sa.Column("cloud_weight", sa.Float(), nullable=True)),
        ("cloud_last_sync", sa.Column("cloud_last_sync", sa.DateTime(), nullable=True)),
        ("weight_source", sa.Column("weight_source", sa.String(50), nullable=True, server_default="filamenthub_manual")),
        ("last_manual_update", sa.Column("last_manual_update", sa.DateTime(), nullable=True)),
        ("last_number", sa.Column("last_number", sa.Integer(), nullable=True)),
        ("emptied_at", sa.Column("emptied_at", sa.DateTime(), nullable=True)),
    ]:
        if col_name not in existing_columns:
            op.add_column("spool", col_def)
        else:
            print(f"    >> Spalte {col_name} existiert bereits, ueberspringe")

    # ========================================
    # TEIL 2: WEIGHT_HISTORY TABLE
    # ========================================

    print("  >> Erstelle weight_history Tabelle...")

    # Check if table exists
    existing_tables = inspector.get_table_names()

    if "weight_history" not in existing_tables:
        op.create_table(
        "weight_history",
        # Primary Key
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # Spulen-Referenz (UUID statt ID!)
        sa.Column("spool_uuid", sa.String(36), nullable=False),
        sa.Column("spool_number", sa.Integer(), nullable=True),  # Snapshot

        # Gewichts-Änderung
        sa.Column("old_weight", sa.Float(), nullable=False),
        sa.Column("new_weight", sa.Float(), nullable=False),

        # Metadaten
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("change_reason", sa.String(100), nullable=False),
        sa.Column("ams_type", sa.String(20), nullable=True),

        # User & Zeit
        sa.Column("user", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),

        # Details
        sa.Column("details", sa.String(500), nullable=True),

        # Foreign Key zu Spule (tray_uuid!)
        sa.ForeignKeyConstraint(
            ["spool_uuid"],
            ["spool.tray_uuid"],
            name="fk_weight_history_spool_uuid",
            ondelete="SET NULL"
        ),
        )
    else:
        print("    >> Tabelle weight_history existiert bereits, ueberspringe")

    # ========================================
    # TEIL 3: INDIZES für Performance
    # ========================================

    print("  >> Erstelle Indizes...")

    # Skip if indices already exist
    for idx_name, table, columns in [
        ("idx_spool_last_seen_ams_type", "spool", ["last_seen_in_ams_type"]),
        ("idx_spool_is_active_last_number", "spool", ["is_active", "last_number"]),
        ("idx_spool_tray_uuid", "spool", ["tray_uuid"]),
        ("idx_weight_history_spool_uuid", "weight_history", ["spool_uuid"]),
        ("idx_weight_history_timestamp", "weight_history", ["timestamp"]),
        ("idx_weight_history_source", "weight_history", ["source"]),
        ("idx_weight_history_spool_timestamp", "weight_history", ["spool_uuid", "timestamp"]),
    ]:
        try:
            op.create_index(idx_name, table, columns)
        except Exception:
            print(f"    >> Index {idx_name} existiert bereits, ueberspringe")

    # ========================================
    # TEIL 4: VIEWS (Optional, für einfache Queries)
    # ========================================

    print("  >> Erstelle Helper-Views...")

    # View: Aktive Spulen mit letzter History
    connection = op.get_bind()
    connection.execute(text("""
        CREATE VIEW IF NOT EXISTS v_active_spools_with_last_change AS
        SELECT
            s.*,
            h.timestamp as last_change_timestamp,
            h.source as last_change_source,
            h.change_reason as last_change_reason
        FROM spool s
        LEFT JOIN (
            SELECT spool_uuid, MAX(timestamp) as max_timestamp
            FROM weight_history
            GROUP BY spool_uuid
        ) h_max ON s.tray_uuid = h_max.spool_uuid
        LEFT JOIN weight_history h ON h.spool_uuid = s.tray_uuid AND h.timestamp = h_max.max_timestamp
        WHERE s.is_active = 1
    """))

    # View: Archivierte Spulen nach Nummer
    connection.execute(text("""
        CREATE VIEW IF NOT EXISTS v_archived_spools_by_number AS
        SELECT
            s.tray_uuid,
            s.last_number,
            s.color,
            s.vendor,
            s.emptied_at,
            COUNT(h.id) as total_changes
        FROM spool s
        LEFT JOIN weight_history h ON h.spool_uuid = s.tray_uuid
        WHERE s.is_active = 0 AND s.last_number IS NOT NULL
        GROUP BY s.tray_uuid, s.last_number, s.color, s.vendor, s.emptied_at
        ORDER BY s.last_number, s.emptied_at DESC
    """))

    print("[OK] Migration erfolgreich abgeschlossen!")
    print("  [OK] Weight History Tabelle erstellt")
    print("  [OK] AMS-Type Tracking aktiviert")
    print("  [OK] Cloud-Sync Tracking aktiviert")
    print("  [OK] Archiv-System fuer Nummern-Recycling bereit")


def downgrade() -> None:
    """
    Downgrade-Migration:
    - Entfernt alle Änderungen dieser Migration
    """

    print(">> Entferne Weight History System...")

    # Drop Views
    connection = op.get_bind()
    connection.execute(text("DROP VIEW IF EXISTS v_archived_spools_by_number"))
    connection.execute(text("DROP VIEW IF EXISTS v_active_spools_with_last_change"))

    # Drop Indizes
    op.drop_index("idx_weight_history_spool_timestamp", "weight_history")
    op.drop_index("idx_weight_history_source", "weight_history")
    op.drop_index("idx_weight_history_timestamp", "weight_history")
    op.drop_index("idx_weight_history_spool_uuid", "weight_history")

    op.drop_index("idx_spool_tray_uuid", "spool")
    op.drop_index("idx_spool_is_active_last_number", "spool")
    op.drop_index("idx_spool_last_seen_ams_type", "spool")

    # Drop Tabelle
    op.drop_table("weight_history")

    # Drop Spalten
    op.drop_column("spool", "emptied_at")
    op.drop_column("spool", "last_number")
    op.drop_column("spool", "last_manual_update")
    op.drop_column("spool", "weight_source")
    op.drop_column("spool", "cloud_last_sync")
    op.drop_column("spool", "cloud_weight")
    op.drop_column("spool", "last_seen_timestamp")
    op.drop_column("spool", "last_seen_in_ams_type")

    print("[OK] Downgrade erfolgreich abgeschlossen!")
