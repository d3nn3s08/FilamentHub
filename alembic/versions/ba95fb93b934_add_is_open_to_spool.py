"""add_is_open_to_spool

Revision ID: ba95fb93b934
Revises: 20251227_add_spool_number_system
Create Date: 2025-12-27 18:21:32.452987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba95fb93b934'
down_revision: Union[str, Sequence[str], None] = '20251227_add_spool_number_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_open column to spool table."""
    op.add_column('spool', sa.Column('is_open', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Remove is_open column from spool table."""
    op.drop_column('spool', 'is_open')
