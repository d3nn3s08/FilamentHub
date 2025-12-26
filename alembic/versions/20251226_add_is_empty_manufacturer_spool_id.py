"""Add is_empty and manufacturer_spool_id to spool

Revision ID: 20251226_add_is_empty_manufacturer_spool_id
Revises: 20251222_add_job_status
Create Date: 2025-12-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20251226_add_is_empty_manufacturer_spool_id"
down_revision = "20251222_add_job_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_empty column with default False
    op.add_column(
        "spool",
        sa.Column("is_empty", sa.Boolean(), nullable=False, server_default="0"),
    )

    # Add manufacturer_spool_id column
    op.add_column(
        "spool",
        sa.Column("manufacturer_spool_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("spool", "manufacturer_spool_id")
    op.drop_column("spool", "is_empty")
