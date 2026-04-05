"""Add display_name field to job table

Revision ID: 20260131_add_job_display_name
Revises: 20260131_add_spool_price
Create Date: 2026-01-31 23:00:00.000000

Fügt das display_name Feld zur Job-Tabelle hinzu.
- name: Original-Name aus MQTT (für Matching, wird nicht überschrieben)
- display_name: Anzeigename (User kann frei ändern)
"""
from alembic import op
import sqlalchemy as sa

revision = "20260131_add_job_display_name"
down_revision = "20260131_add_spool_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Fügt display_name Spalte zur Job-Tabelle hinzu."""
    print(">> Füge display_name Spalte zur Job-Tabelle hinzu...")

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('job')]

    if 'display_name' not in existing_columns:
        op.add_column('job', sa.Column('display_name', sa.String(), nullable=True))
        print("    >> Spalte display_name hinzugefügt")
    else:
        print("    >> Spalte display_name existiert bereits, überspringe")

    print("[OK] Migration erfolgreich!")


def downgrade() -> None:
    """Entfernt display_name Spalte von der Job-Tabelle."""
    print(">> Entferne display_name Spalte von Job-Tabelle...")

    try:
        op.drop_column('job', 'display_name')
        print("    >> Spalte display_name entfernt")
    except Exception:
        print("    >> Spalte display_name existiert nicht, überspringe")

    print("[OK] Downgrade erfolgreich!")
