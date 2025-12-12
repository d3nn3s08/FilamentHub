"""Add spool usage tracking fields

Revision ID: 20231202_add_spool_usage_fields
Revises: 
Create Date: 2025-12-02 22:00:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20231202_add_spool_usage_fields"
down_revision = "20231202_ams_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("spool", sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("spool", sa.Column("last_slot", sa.Integer(), nullable=True))
    # remove server_default after backfill
    with op.batch_alter_table("spool") as batch_op:
        batch_op.alter_column("used_count", server_default=None)


def downgrade():
    with op.batch_alter_table("spool") as batch_op:
        batch_op.drop_column("first_seen")
        batch_op.drop_column("used_count")
        batch_op.drop_column("last_slot")
