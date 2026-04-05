"""add bambu material fields

Revision ID: 20260102_add_bambu_material_fields
Revises: d86176e7e88b
Create Date: 2026-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260102_add_bambu_material_fields"
down_revision: Union[str, Sequence[str], None] = "d86176e7e88b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("material") as batch_op:
        batch_op.add_column(sa.Column("is_bambu", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("spool_weight_full", sa.Float(), nullable=True))

    # Backfill Bambu Lab materials only
    op.execute(
        sa.text(
            "UPDATE material SET is_bambu = 1 WHERE brand = :brand"
        ).bindparams(brand="Bambu Lab")
    )
    op.execute(
        sa.text(
            "UPDATE material SET spool_weight_full = :full "
            "WHERE is_bambu = 1 AND spool_weight_full IS NULL"
        ).bindparams(full=1000.0)
    )
    op.execute(
        sa.text(
            "UPDATE material SET spool_weight_empty = :empty "
            "WHERE is_bambu = 1 AND spool_weight_empty IS NULL"
        ).bindparams(empty=209.0)
    )


def downgrade() -> None:
    with op.batch_alter_table("material") as batch_op:
        batch_op.drop_column("spool_weight_full")
        batch_op.drop_column("is_bambu")
