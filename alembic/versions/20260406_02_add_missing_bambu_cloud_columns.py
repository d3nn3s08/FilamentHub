"""add_missing_bambu_cloud_columns

Adds dry_run_mode, cloud_mqtt_enabled, cloud_mqtt_connected, cloud_mqtt_last_message
to bambu_cloud_config table.

Revision ID: 20260406_02_add_missing_bambu_cloud_columns
Revises: 20260406_add_sync_paused_to_bambu_cloud_config
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260406_02_add_missing_bambu_cloud_columns'
down_revision: Union[str, Sequence[str], None] = '20260406_add_sync_paused_to_bambu_cloud_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [col['name'] for col in inspector.get_columns('bambu_cloud_config')]

    missing = [
        ('dry_run_mode',            sa.Column('dry_run_mode',            sa.Boolean(), nullable=False, server_default='0')),
        ('cloud_mqtt_enabled',      sa.Column('cloud_mqtt_enabled',      sa.Boolean(), nullable=False, server_default='0')),
        ('cloud_mqtt_connected',    sa.Column('cloud_mqtt_connected',    sa.Boolean(), nullable=False, server_default='0')),
        ('cloud_mqtt_last_message', sa.Column('cloud_mqtt_last_message', sa.String(),  nullable=True)),
    ]

    for col_name, col_def in missing:
        if col_name not in existing_cols:
            op.add_column('bambu_cloud_config', col_def)
            print(f"[MIGRATION] Added {col_name} to bambu_cloud_config")


def downgrade() -> None:
    op.drop_column('bambu_cloud_config', 'cloud_mqtt_last_message')
    op.drop_column('bambu_cloud_config', 'cloud_mqtt_connected')
    op.drop_column('bambu_cloud_config', 'cloud_mqtt_enabled')
    op.drop_column('bambu_cloud_config', 'dry_run_mode')
