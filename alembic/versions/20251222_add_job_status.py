"""add job status field

Revision ID: 20251222_add_job_status
Revises: 20251220_remove_material_color
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251222_add_job_status'
down_revision = '20251220_remove_material_color'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add status column to job table with default value 'running'
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(), nullable=False, server_default='running'))

    # Set status for existing jobs based on finished_at
    # If finished_at is set, assume completed; otherwise running
    op.execute("""
        UPDATE job
        SET status = CASE
            WHEN finished_at IS NOT NULL THEN 'completed'
            ELSE 'running'
        END
    """)


def downgrade() -> None:
    # Remove status column
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_column('status')
