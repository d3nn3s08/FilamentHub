"""Add print_source to job table

Revision ID: 20260103_add_print_source
Revises: 20260103_make_mqtt_version_nullable
Create Date: 2026-01-03 14:29:50.000000

Fügt print_source Feld hinzu für Unterscheidung zwischen AMS und externem Druck
"""
from alembic import op
import sqlalchemy as sa

revision = "20260103_add_print_source"
down_revision = "20260103_make_mqtt_version_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade-Migration:
    - Fügt print_source Feld zur job Tabelle hinzu
    - Mögliche Werte: "ams", "external", "unknown" (default)
    """
    print(">> Fuege print_source Feld hinzu...")

    # Prüfe ob Spalte bereits existiert (Idempotenz)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("job")]

    if "print_source" not in columns:
        op.add_column(
            "job",
            sa.Column("print_source", sa.String(), nullable=True),
        )

        # Setze Default für existierende Rows
        op.execute("UPDATE job SET print_source = 'unknown' WHERE print_source IS NULL")

        print("[OK] print_source Feld hinzugefuegt")
    else:
        print("[SKIP] print_source Feld existiert bereits")

    print("[OK] Migration erfolgreich abgeschlossen!")
    print("  >> Job-Tabelle hat jetzt print_source Feld (ams/external/unknown)")


def downgrade() -> None:
    """
    Downgrade-Migration:
    - Entfernt print_source Feld
    """
    print(">> Entferne print_source Feld...")

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("job")]

    if "print_source" in columns:
        op.drop_column("job", "print_source")
        print("[OK] print_source Feld entfernt")
    else:
        print("[SKIP] print_source Feld existiert nicht")

    print("[OK] Downgrade erfolgreich abgeschlossen!")
