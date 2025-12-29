"""Add filament_start_mm to job table

Revision ID: 20251228_add_filament_start_mm
Revises: 20251227_add_spool_number_system
Create Date: 2025-12-28 12:00:00.000000

Fügt filament_start_mm Feld hinzu für sauberes Filament-Tracking ab layer_num >= 1
"""
from alembic import op
import sqlalchemy as sa

revision = "20251228_add_filament_start_mm"
down_revision = "20251227_add_spool_number_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade-Migration:
    - Fügt filament_start_mm Feld zur job Tabelle hinzu
    """
    print(">> Fuege filament_start_mm Feld hinzu...")

    op.add_column(
        "job",
        sa.Column("filament_start_mm", sa.Float(), nullable=True),
    )

    print("[OK] Migration erfolgreich abgeschlossen!")
    print("  >> Job-Tabelle hat jetzt filament_start_mm Feld")


def downgrade() -> None:
    """
    Downgrade-Migration:
    - Entfernt filament_start_mm Feld
    """
    print(">> Entferne filament_start_mm Feld...")

    op.drop_column("job", "filament_start_mm")

    print("[OK] Downgrade erfolgreich abgeschlossen!")

