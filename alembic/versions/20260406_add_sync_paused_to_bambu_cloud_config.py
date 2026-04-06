"""add_sync_paused_to_bambu_cloud_config

Adds sync_paused column to bambu_cloud_config table.

Revision ID: 20260406_add_sync_paused_to_bambu_cloud_config
Revises: 20260307_add_mmu_fields_to_printer
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260406_add_sync_paused_to_bambu_cloud_config'
down_revision: Union[str, Sequence[str], None] = '20260307_add_mmu_fields_to_printer'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [col['name'] for col in inspector.get_columns('bambu_cloud_config')]

    if 'sync_paused' not in existing_cols:
        op.add_column('bambu_cloud_config', sa.Column('sync_paused', sa.Boolean(), nullable=False, server_default='0'))
        print("[MIGRATION] Added sync_paused to bambu_cloud_config")


def downgrade() -> None:
    op.drop_column('bambu_cloud_config', 'sync_paused')
