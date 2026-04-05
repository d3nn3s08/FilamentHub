"""Add eta_seconds to job table

Revision ID: 20251228_add_eta_seconds_to_job
Revises: b6901f165641
Create Date: 2025-12-28 23:10:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20251228_add_eta_seconds_to_job"
down_revision = "b6901f165641"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add eta_seconds column to job table."""
    op.add_column(
        "job",
        sa.Column("eta_seconds", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove eta_seconds column from job table."""
    op.drop_column("job", "eta_seconds")
