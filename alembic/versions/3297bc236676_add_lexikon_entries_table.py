"""add_lexikon_entries_table

Revision ID: 3297bc236676
Revises: 9ee84e1c222f
Create Date: 2026-01-01 17:32:19.937962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3297bc236676'
down_revision: Union[str, Sequence[str], None] = '9ee84e1c222f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'lexikon_entries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('icon', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('keywords', sa.String(), nullable=True),
        sa.Column('property_1_label', sa.String(), nullable=True),
        sa.Column('property_1_value', sa.String(), nullable=True),
        sa.Column('property_2_label', sa.String(), nullable=True),
        sa.Column('property_2_value', sa.String(), nullable=True),
        sa.Column('property_3_label', sa.String(), nullable=True),
        sa.Column('property_3_value', sa.String(), nullable=True),
        sa.Column('property_4_label', sa.String(), nullable=True),
        sa.Column('property_4_value', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('lexikon_entries')
