"""merge ams metadata and eta seconds heads

Revision ID: d86176e7e88b
Revises: 20251229_add_ams_metadata_and_conflict, 20251228_add_eta_seconds_to_job
Create Date: 2025-12-29 23:29:48.080885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd86176e7e88b'
down_revision: Union[str, Sequence[str], None] = ('20251229_add_ams_metadata_and_conflict', '20251228_add_eta_seconds_to_job')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
