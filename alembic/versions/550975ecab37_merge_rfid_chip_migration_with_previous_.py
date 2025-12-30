"""merge rfid chip migration with previous heads

Revision ID: 550975ecab37
Revises: 20251230_add_rfid_chip_id_to_spool, 2c0e7b2f0b71
Create Date: 2025-12-30 11:38:32.685596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '550975ecab37'
down_revision: Union[str, Sequence[str], None] = ('20251230_add_rfid_chip_id_to_spool', '2c0e7b2f0b71')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
