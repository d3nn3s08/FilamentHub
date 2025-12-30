"""add ams metadata to spool and create ams_conflict table

Revision ID: 20251229_add_ams_metadata_and_conflict
Revises: 20251228_add_filament_start_mm
Create Date: 2025-12-29
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251229_add_ams_metadata_and_conflict"
down_revision = "20251228_add_filament_start_mm"
branch_labels = None
depends_on = None


def upgrade():
    # Add columns to spool table if they don't already exist
    conn = op.get_bind()
    existing_cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info('spool')")).fetchall()]
    to_add = []
    if "ams_id" not in existing_cols:
        to_add.append(sa.Column("ams_id", sa.String(), nullable=True))
    if "ams_source" not in existing_cols:
        to_add.append(sa.Column("ams_source", sa.String(), nullable=True))
    if "assigned" not in existing_cols:
        to_add.append(sa.Column("assigned", sa.Boolean(), nullable=False, server_default=sa.text('0')))
    if "is_active" not in existing_cols:
        to_add.append(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text('1')))

    if to_add:
        with op.batch_alter_table("spool") as batch_op:
            for col in to_add:
                batch_op.add_column(col)

    # Create ams_conflict table if it doesn't exist
    tbls = [r[0] for r in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
    if "ams_conflict" not in tbls:
        op.create_table(
            "ams_conflict",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("printer_id", sa.String(), nullable=True),
            sa.Column("ams_id", sa.String(), nullable=True),
            sa.Column("slot", sa.Integer(), nullable=True),
            sa.Column("manual_spool_id", sa.String(), nullable=True),
            sa.Column("rfid_payload", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("created_at", sa.String(), nullable=True),
            sa.ForeignKeyConstraint(["manual_spool_id"], ["spool.id"], name="fk_ams_conflict_manual_spool_id_spool"),
        )


def downgrade():
    conn = op.get_bind()
    tbls = [r[0] for r in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
    if "ams_conflict" in tbls:
        op.drop_table("ams_conflict")

    existing_cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info('spool')")).fetchall()]
    with op.batch_alter_table("spool") as batch_op:
        if "is_active" in existing_cols:
            batch_op.drop_column("is_active")
        if "assigned" in existing_cols:
            batch_op.drop_column("assigned")
        if "ams_source" in existing_cols:
            batch_op.drop_column("ams_source")
        if "ams_id" in existing_cols:
            batch_op.drop_column("ams_id")
