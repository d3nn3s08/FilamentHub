"""
Alembic migration: Add settings and userflag tables
"""
from typing import Sequence, Union
# revision identifiers, used by Alembic.
revision: str = '20251204_01_add_settings_and_userflag'
down_revision: Union[str, Sequence[str], None] = '20231205_add_job_spool_usage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'setting',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', sa.String(), nullable=True),
    )
    op.create_table(
        'userflag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('flag', sa.String(), nullable=False),
        sa.Column('value', sa.Boolean(), nullable=False, default=False),
    )

def downgrade():
    op.drop_table('userflag')
    op.drop_table('setting')
