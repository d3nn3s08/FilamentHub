"""add task_name and gcode_file to job

Revision ID: 20260124_task_name
Revises: bfb91b256607
Create Date: 2026-01-24 15:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260124_task_name'
down_revision = 'bfb91b256607'
branch_labels = None
depends_on = None


def upgrade():
    # Add task_name column (nullable for now, will be filled from name)
    op.add_column('job', sa.Column('task_name', sa.String(), nullable=True))

    # Add gcode_file column (nullable, will be extracted from task_name)
    op.add_column('job', sa.Column('gcode_file', sa.String(), nullable=True))

    # Migrate existing data: task_name = name
    op.execute("UPDATE job SET task_name = name WHERE task_name IS NULL")

    # Extract gcode_file from task_name (simple approach: use task_name as-is)
    # More sophisticated extraction can be done in application code
    op.execute("UPDATE job SET gcode_file = task_name WHERE gcode_file IS NULL")


def downgrade():
    # Remove columns
    op.drop_column('job', 'gcode_file')
    op.drop_column('job', 'task_name')
