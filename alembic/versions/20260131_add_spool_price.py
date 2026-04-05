"""Add price field to spool table

Revision ID: 20260131_add_spool_price
Revises: 20260129_add_bambu_cloud_integration
Create Date: 2026-01-31 20:00:00.000000

Fügt das Preis-Feld zur Spool-Tabelle hinzu für Wertberechnung.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260131_add_spool_price"
down_revision = "20260129_add_bambu_cloud_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Fügt price Spalte zur Spool-Tabelle hinzu."""
    print(">> Füge price Spalte zur Spool-Tabelle hinzu...")

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('spool')]

    if 'price' not in existing_columns:
        op.add_column('spool', sa.Column('price', sa.Float(), nullable=True))
        print("    >> Spalte price hinzugefügt")
    else:
        print("    >> Spalte price existiert bereits, überspringe")

    print("[OK] Migration erfolgreich!")


def downgrade() -> None:
    """Entfernt price Spalte von der Spool-Tabelle."""
    print(">> Entferne price Spalte von Spool-Tabelle...")

    try:
        op.drop_column('spool', 'price')
        print("    >> Spalte price entfernt")
    except Exception:
        print("    >> Spalte price existiert nicht, überspringe")

    print("[OK] Downgrade erfolgreich!")
