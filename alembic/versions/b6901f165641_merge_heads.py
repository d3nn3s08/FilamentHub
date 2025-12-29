"""merge heads

Revision ID: b6901f165641
Revises: ba95fb93b934, 20251228_add_filament_start_mm
Create Date: 2025-12-28 21:50:09.045225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6901f165641'
down_revision: Union[str, Sequence[str], None] = ('ba95fb93b934', '20251228_add_filament_start_mm')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
