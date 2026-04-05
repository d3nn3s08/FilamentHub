"""create ams_unit and ams_tray tables + backfill spools

Revision ID: 20251230_create_ams_unit_and_tray
Revises: 20251230_add_rfid_chip_id_to_spool
Create Date: 2025-12-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251230_create_ams_unit_and_tray"
down_revision = "20251230_add_rfid_chip_id_to_spool"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    tbls = [r[0] for r in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' ")).fetchall()]

    if "amsunit" not in tbls:
        op.create_table(
            "amsunit",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("cloud_serial", sa.String(), nullable=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("trays_count", sa.Integer(), nullable=True),
            sa.Column("last_seen", sa.String(), nullable=True),
            sa.Column("metadata", sa.Text(), nullable=True),
        )

    if "amstray" not in tbls:
        op.create_table(
            "amstray",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("ams_unit_id", sa.String(), nullable=True),
            sa.Column("tray_index", sa.Integer(), nullable=True),
            sa.Column("tray_uuid", sa.String(), nullable=True),
            sa.Column("remaining_weight", sa.Float(), nullable=True),
            sa.Column("material_type", sa.String(), nullable=True),
            sa.Column("last_seen", sa.String(), nullable=True),
            sa.Column("metadata", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["ams_unit_id"], ["amsunit.id"], name="fk_amstray_ams_unit_id_amsunit"),
        )

    # Backfill inconsistent spools: assigned=true but ams_id IS NULL -> reset
    try:
        conn.execute(sa.text(
            """
            UPDATE spool
            SET assigned = 0,
                ams_id = NULL,
                ams_slot = NULL,
                ams_source = NULL
            WHERE assigned = 1
              AND (ams_id IS NULL OR ams_id = '')
            """
        ))
    except Exception:
        # best-effort backfill; avoid failing migration on edge cases
        pass


def downgrade():
    conn = op.get_bind()
    tbls = [r[0] for r in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' ")).fetchall()]
    if "amstray" in tbls:
        op.drop_table("amstray")
    if "amsunit" in tbls:
        op.drop_table("amsunit")
