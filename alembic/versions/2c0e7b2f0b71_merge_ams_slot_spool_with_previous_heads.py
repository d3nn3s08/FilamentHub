"""merge ams slot spool with previous heads

Revision ID: 2c0e7b2f0b71
Revises: 20251230_add_ams_slot_to_spool, d86176e7e88b
Create Date: 2025-12-30 09:30:52.243773

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c0e7b2f0b71'
down_revision: Union[str, Sequence[str], None] = ('20251230_add_ams_slot_to_spool', 'd86176e7e88b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
