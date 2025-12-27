"""Add spool number system and job snapshots

Revision ID: 20251227_add_spool_number_system
Revises: 20251226_add_is_empty_manufacturer_spool_id
Create Date: 2025-12-27 12:00:00.000000

Dieses System implementiert:
1. Spulen-Nummern (#1, #2, #3...) mit Recycling
2. Denormalisierte Felder für schnelle Suche (name, vendor, color)
3. Job-Snapshots für korrekte Historie
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "20251227_add_spool_number_system"
down_revision = "20251226_add_is_empty_manufacturer_spool_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade-Migration:
    - Fügt Spulen-Nummern-System hinzu
    - Fügt denormalisierte Felder für Suche hinzu
    - Fügt Job-Snapshot-Felder hinzu
    - Migriert bestehende Daten
    """

    # ========================================
    # TEIL 1: SPOOL TABLE
    # ========================================

    print("→ Füge Spulen-Nummern-System hinzu...")

    # 1. Add spool_number (unique, nullable initially for migration)
    op.add_column(
        "spool",
        sa.Column("spool_number", sa.Integer(), nullable=True),
    )

    # 2. Add denormalized fields for fast search (ohne JOINs)
    op.add_column(
        "spool",
        sa.Column("name", sa.String(100), nullable=True),
    )
    op.add_column(
        "spool",
        sa.Column("vendor", sa.String(100), nullable=True),
    )
    op.add_column(
        "spool",
        sa.Column("color", sa.String(50), nullable=True),
    )

    print("→ Erstelle Indizes für Performance...")

    # 3. Create indexes for performance
    op.create_index("idx_spool_number", "spool", ["spool_number"], unique=False)
    op.create_index("idx_spool_name", "spool", ["name"], unique=False)
    op.create_index("idx_spool_search", "spool", ["name", "vendor", "color"], unique=False)
    op.create_index("idx_spool_printer_slot", "spool", ["printer_id", "ams_slot"], unique=False)

    # ========================================
    # TEIL 2: JOB TABLE (Snapshots)
    # ========================================

    print("→ Füge Job-Snapshot-Felder hinzu...")

    # 4. Add snapshot fields to job table
    op.add_column(
        "job",
        sa.Column("spool_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "job",
        sa.Column("spool_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "job",
        sa.Column("spool_vendor", sa.String(100), nullable=True),
    )
    op.add_column(
        "job",
        sa.Column("spool_color", sa.String(50), nullable=True),
    )
    op.add_column(
        "job",
        sa.Column("spool_created_at", sa.String(), nullable=True),
    )

    # 5. Create index for job spool_number
    op.create_index("idx_job_spool_number", "job", ["spool_number"], unique=False)

    # ========================================
    # TEIL 3: DATA MIGRATION
    # ========================================

    print("→ Migriere bestehende Daten...")

    connection = op.get_bind()

    # 6. Populate spool_number for existing spools (sequential, by created_at)
    print("  → Vergebe Spulen-Nummern...")
    connection.execute(text("""
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at NULLS LAST, id) as num
            FROM spool
        )
        UPDATE spool
        SET spool_number = (SELECT num FROM numbered WHERE numbered.id = spool.id)
    """))

    # 7. Populate name, vendor from material table
    print("  → Kopiere Material-Daten (name, vendor)...")
    connection.execute(text("""
        UPDATE spool
        SET
            name = (SELECT name FROM material WHERE material.id = spool.material_id),
            vendor = (SELECT brand FROM material WHERE material.id = spool.material_id)
        WHERE spool.material_id IS NOT NULL
    """))

    # 8. Populate color from tray_color (simplified: use first 6 chars as hex)
    print("  → Extrahiere Farben aus tray_color...")
    connection.execute(text("""
        UPDATE spool
        SET color = CASE
            WHEN tray_color IS NOT NULL AND length(tray_color) >= 6 THEN substr(tray_color, 1, 6)
            ELSE 'unknown'
        END
        WHERE color IS NULL
    """))

    # 9. Populate job snapshots for existing jobs
    print("  → Erstelle Job-Snapshots für bestehende Jobs...")
    connection.execute(text("""
        UPDATE job
        SET
            spool_number = (SELECT spool_number FROM spool WHERE spool.id = job.spool_id),
            spool_name = (SELECT name FROM spool WHERE spool.id = job.spool_id),
            spool_vendor = (SELECT vendor FROM spool WHERE spool.id = job.spool_id),
            spool_color = (SELECT color FROM spool WHERE spool.id = job.spool_id),
            spool_created_at = (SELECT created_at FROM spool WHERE spool.id = job.spool_id)
        WHERE job.spool_id IS NOT NULL
          AND job.spool_number IS NULL
    """))

    # 10. Add UNIQUE constraint on spool_number (now that all have values)
    print("→ Setze UNIQUE constraint auf spool_number...")
    op.create_unique_constraint("uq_spool_number", "spool", ["spool_number"])

    print("✓ Migration erfolgreich abgeschlossen!")
    print("  → Spulen haben jetzt Nummern (#1, #2, #3...)")
    print("  → Jobs haben Snapshots für korrekte Historie")
    print("  → Schnelle Suche ohne JOINs aktiviert")


def downgrade() -> None:
    """
    Downgrade-Migration:
    - Entfernt alle Änderungen dieser Migration
    """

    print("→ Entferne Spulen-Nummern-System...")

    # Drop unique constraint
    op.drop_constraint("uq_spool_number", "spool", type_="unique")

    # Drop indexes
    op.drop_index("idx_job_spool_number", "job")
    op.drop_index("idx_spool_printer_slot", "spool")
    op.drop_index("idx_spool_search", "spool")
    op.drop_index("idx_spool_name", "spool")
    op.drop_index("idx_spool_number", "spool")

    # Drop job columns
    op.drop_column("job", "spool_created_at")
    op.drop_column("job", "spool_color")
    op.drop_column("job", "spool_vendor")
    op.drop_column("job", "spool_name")
    op.drop_column("job", "spool_number")

    # Drop spool columns
    op.drop_column("spool", "color")
    op.drop_column("spool", "vendor")
    op.drop_column("spool", "name")
    op.drop_column("spool", "spool_number")

    print("✓ Downgrade erfolgreich abgeschlossen!")
