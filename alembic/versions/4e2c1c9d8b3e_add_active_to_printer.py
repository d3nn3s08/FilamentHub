"""add active flag to printer

Revision ID: 4e2c1c9d8b3e
Revises: 11f74386f230
Create Date: 2025-11-27 19:58:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "4e2c1c9d8b3e"
down_revision: Union[str, Sequence[str], None] = "11f74386f230"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "printer",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("printer", "active")
