"""Add series to printer"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260103_add_printer_series"
down_revision: Union[str, Sequence[str], None] = "a693d8045b41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "printer",
        sa.Column("series", sa.String(length=16), nullable=False, server_default="UNKNOWN"),
    )
    with op.batch_alter_table("printer") as batch_op:
        batch_op.alter_column("series", server_default=None)


def downgrade() -> None:
    op.drop_column("printer", "series")
