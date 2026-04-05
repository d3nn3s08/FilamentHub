"""Add power and maintenance to printer

Revision ID: 20251219_000001_add_power_and_maintenance_to_printer
Revises: 20251206_182015_add_printer_model_and_mqtt_version
Create Date: 2025-12-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251219_000001_add_power_and_maintenance_to_printer"
down_revision: Union[str, Sequence[str], None] = "20251206_182015_add_printer_model_and_mqtt_version"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("printer", sa.Column("power_consumption_kw", sa.Float(), nullable=True))
    op.add_column("printer", sa.Column("maintenance_cost_yearly", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("printer", "maintenance_cost_yearly")
    op.drop_column("printer", "power_consumption_kw")
