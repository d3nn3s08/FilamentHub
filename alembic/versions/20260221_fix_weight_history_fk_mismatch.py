"""Compatibility placeholder for locally stamped revision.

Revision ID: 20260221_fix_weight_history_fk_mismatch
Revises: 20260205_add_job_weight_tracking
Create Date: 2026-02-21
"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision = "20260221_fix_weight_history_fk_mismatch"
down_revision = "20260205_add_job_weight_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
