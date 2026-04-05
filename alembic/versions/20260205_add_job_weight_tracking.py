"""Add start_weight and end_weight to job table for weight tracking

Revision ID: 20260205_add_job_weight_tracking
Revises: 20260131_add_job_display_name
Create Date: 2026-02-05 12:00:00.000000

Fuegt start_weight und end_weight Felder zur Job-Tabelle hinzu.
- start_weight: Spulen-Gewicht bei Job-Start (Snapshot)
- end_weight: Spulen-Gewicht bei Job-Ende (Snapshot)
- Verbrauch = start_weight - end_weight
"""
from alembic import op
import sqlalchemy as sa

revision = "20260205_add_job_weight_tracking"
down_revision = "20260131_add_job_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Fuegt start_weight und end_weight Spalten zur Job-Tabelle hinzu."""
    print(">> Fuege Gewichts-Tracking-Spalten zur Job-Tabelle hinzu...")

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('job')]

    if 'start_weight' not in existing_columns:
        op.add_column('job', sa.Column('start_weight', sa.Float(), nullable=True))
        print("    >> Spalte start_weight hinzugefuegt")
    else:
        print("    >> Spalte start_weight existiert bereits, ueberspringe")

    if 'end_weight' not in existing_columns:
        op.add_column('job', sa.Column('end_weight', sa.Float(), nullable=True))
        print("    >> Spalte end_weight hinzugefuegt")
    else:
        print("    >> Spalte end_weight existiert bereits, ueberspringe")

    print("[OK] Migration erfolgreich!")


def downgrade() -> None:
    """Entfernt start_weight und end_weight Spalten von der Job-Tabelle."""
    print(">> Entferne Gewichts-Tracking-Spalten von Job-Tabelle...")

    try:
        op.drop_column('job', 'end_weight')
        print("    >> Spalte end_weight entfernt")
    except Exception:
        print("    >> Spalte end_weight existiert nicht, ueberspringe")

    try:
        op.drop_column('job', 'start_weight')
        print("    >> Spalte start_weight entfernt")
    except Exception:
        print("    >> Spalte start_weight existiert nicht, ueberspringe")

    print("[OK] Downgrade erfolgreich!")
