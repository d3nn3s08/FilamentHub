"""merge multiple heads: 20251230_create_ams_unit_and_tray + 550975ecab37

Revision ID: 20251230_merge_heads_550975ecab37
Revises: 20251230_create_ams_unit_and_tray,550975ecab37
Create Date: 2025-12-30
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20251230_merge_heads_550975ecab37"
down_revision = ("20251230_create_ams_unit_and_tray", "550975ecab37")
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge-only revision. No schema changes.
    pass


def downgrade():
    # Nothing to do on downgrade for a merge node.
    pass
