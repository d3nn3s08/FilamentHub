"""Remove material color column

Revision ID: 20251220_remove_material_color
Revises: 20251219_000001_add_power_and_maintenance_to_printer
Create Date: 2025-12-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20251220_remove_material_color"
down_revision = "20251219_000001_add_power_and_maintenance_to_printer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("material", "color")


def downgrade() -> None:
    op.add_column(
        "material",
        sa.Column("color", sa.String(), nullable=True),
    )
