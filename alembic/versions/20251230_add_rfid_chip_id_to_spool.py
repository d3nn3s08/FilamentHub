"""add rfid_chip_id to spool

Revision ID: 20251230_add_rfid_chip_id_to_spool
Revises: 20251230_add_ams_slot_to_spool
Create Date: 2025-12-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251230_add_rfid_chip_id_to_spool"
down_revision = "20251230_add_ams_slot_to_spool"
branch_labels = None
depends_on = None


def upgrade():
    # Add rfid_chip_id column (nullable text)
    conn = op.get_bind()
    existing = [r[1] for r in conn.execute(sa.text("PRAGMA table_info('spool')")).fetchall()]
    if "rfid_chip_id" not in existing:
        with op.batch_alter_table("spool") as batch_op:
            batch_op.add_column(sa.Column("rfid_chip_id", sa.String(), nullable=True))
    else:
        pass


def downgrade():
    conn = op.get_bind()
    existing = [r[1] for r in conn.execute(sa.text("PRAGMA table_info('spool')")).fetchall()]
    if "rfid_chip_id" in existing:
        with op.batch_alter_table("spool") as batch_op:
            batch_op.drop_column("rfid_chip_id")
    else:
        pass
