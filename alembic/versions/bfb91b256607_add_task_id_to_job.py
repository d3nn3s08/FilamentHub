"""add_task_id_to_job

Revision ID: bfb91b256607
Revises: 20260103_add_printer_series
Create Date: 2026-01-12 22:30:52.578053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfb91b256607'
down_revision: Union[str, Sequence[str], None] = '20260103_add_printer_series'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add task_id column to job table."""
    # Check if column already exists (idempotent)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('job')]

    if 'task_id' not in columns:
        op.add_column('job', sa.Column('task_id', sa.String(), nullable=True))
        print("[MIGRATION] Added task_id column to job table")
    else:
        print("[MIGRATION] task_id column already exists, skipping")


def downgrade() -> None:
    """Downgrade schema: Remove task_id column from job table."""
    # Check if column exists before dropping
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('job')]

    if 'task_id' in columns:
        op.drop_column('job', 'task_id')
        print("[MIGRATION] Removed task_id column from job table")
    else:
        print("[MIGRATION] task_id column does not exist, skipping")
