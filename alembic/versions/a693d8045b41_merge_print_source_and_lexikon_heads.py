"""merge print_source and lexikon heads

Revision ID: a693d8045b41
Revises: 20260103_add_print_source, 3297bc236676
Create Date: 2026-01-03 14:31:13.097487

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a693d8045b41'
down_revision: Union[str, Sequence[str], None] = ('20260103_add_print_source', '3297bc236676')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
