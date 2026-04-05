"""add spool_weight_empty to material

Revision ID: 9ee84e1c222f
Revises: 20251230_merge_heads_550975ecab37
Create Date: 2026-01-01 14:29:55.463601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ee84e1c222f'
down_revision: Union[str, Sequence[str], None] = '20251230_merge_heads_550975ecab37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add spool_weight_empty column to material table
    op.add_column('material', sa.Column('spool_weight_empty', sa.Float(), nullable=True))

    # Set default values for known manufacturers
    # Based on: https://grischabock.ch/forum/thread/2091-filament-spulen-leergewicht/
    op.execute("""
        UPDATE material
        SET spool_weight_empty = 209.0
        WHERE brand = 'Bambu Lab'
    """)

    op.execute("""
        UPDATE material
        SET spool_weight_empty = 190.0
        WHERE brand = 'Sunlu'
    """)

    op.execute("""
        UPDATE material
        SET spool_weight_empty = 256.0
        WHERE brand = 'eSun'
    """)

    op.execute("""
        UPDATE material
        SET spool_weight_empty = 220.0
        WHERE brand IN ('Polymaker', 'Prusa')
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('material', 'spool_weight_empty')
