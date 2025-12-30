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
    # Add columns to spool table
    with op.batch_alter_table("spool") as batch_op:
        batch_op.add_column(sa.Column("ams_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("ams_source", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("assigned", sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text('1')))

    # Create ams_conflict table
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
    op.drop_table("ams_conflict")
    with op.batch_alter_table("spool") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("assigned")
        batch_op.drop_column("ams_source")
        batch_op.drop_column("ams_id")
