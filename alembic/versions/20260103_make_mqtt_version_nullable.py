"""Make mqtt_version nullable for auto detection.

Revision ID: 20260103_make_mqtt_version_nullable
Revises: 20260102_add_bambu_material_fields
Create Date: 2026-01-03 12:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260103_make_mqtt_version_nullable"
down_revision: Union[str, Sequence[str], None] = "20260102_add_bambu_material_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("printer") as batch_op:
        batch_op.alter_column(
            "mqtt_version",
            existing_type=sa.String(length=8),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(sa.text("UPDATE printer SET mqtt_version = '311' WHERE mqtt_version IS NULL"))
    with op.batch_alter_table("printer") as batch_op:
        batch_op.alter_column(
            "mqtt_version",
            existing_type=sa.String(length=8),
            nullable=False,
        )
