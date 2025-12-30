"""add ams_slot to spool table

Revision ID: 20251230_add_ams_slot_to_spool
Revises: 20251229_add_ams_metadata_and_conflict
Create Date: 2025-12-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251230_add_ams_slot_to_spool"
down_revision = "20251229_add_ams_metadata_and_conflict"
branch_labels = None
depends_on = None


def upgrade():
    # Add ams_slot column (nullable integer)
    with op.batch_alter_table("spool") as batch_op:
        batch_op.add_column(sa.Column("ams_slot", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("spool") as batch_op:
        batch_op.drop_column("ams_slot")
