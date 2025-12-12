"""Add job_spool_usage table for multi-spool tracking

Revision ID: 20231205_add_job_spool_usage
Revises: a662aa086a07
Create Date: 2025-12-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20231205_add_job_spool_usage"
down_revision = "a662aa086a07"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_spool_usage",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.String(), sa.ForeignKey("job.id"), nullable=False),
        sa.Column("spool_id", sa.String(), sa.ForeignKey("spool.id"), nullable=True),
        sa.Column("slot", sa.Integer(), nullable=True),
        sa.Column("used_mm", sa.Float(), nullable=False, server_default="0"),
        sa.Column("used_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer(), nullable=True),
    )
    # remove defaults after creation
    with op.batch_alter_table("job_spool_usage") as batch_op:
        batch_op.alter_column("used_mm", server_default=None)
        batch_op.alter_column("used_g", server_default=None)


def downgrade():
    op.drop_table("job_spool_usage")
