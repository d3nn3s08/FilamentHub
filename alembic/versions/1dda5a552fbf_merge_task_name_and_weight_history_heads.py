"""merge task_name and weight_history heads

Revision ID: 1dda5a552fbf
Revises: 20260117_add_weight_history_system, 20260124_task_name
Create Date: 2026-01-24 15:02:10.385416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1dda5a552fbf'
down_revision: Union[str, Sequence[str], None] = ('20260117_add_weight_history_system', '20260124_task_name')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
