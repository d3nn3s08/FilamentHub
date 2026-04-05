"""add_mmu_fields_to_printer

Adds Happy Hare MMU support fields to the printer table:
  - has_mmu       (BOOLEAN, default False)
  - mmu_type      (VARCHAR, nullable)  — z.B. "ERCF", "Tradrack", "BoxTurtle"
  - mmu_gate_count (INTEGER, nullable) — wird automatisch aus Happy Hare erkannt

Revision ID: 20260307_add_mmu_fields_to_printer
Revises: bfb91b256607
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260307_add_mmu_fields_to_printer'
down_revision: Union[str, Sequence[str], None] = ('bfb91b256607', '20260228_fix_weight_history_drop_fk')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: MMU-Felder zur printer-Tabelle hinzufügen."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = [col['name'] for col in inspector.get_columns('printer')]

    if 'has_mmu' not in existing_cols:
        op.add_column('printer', sa.Column('has_mmu', sa.Boolean(), nullable=False, server_default='0'))
        print("[MIGRATION] Added has_mmu to printer")

    if 'mmu_type' not in existing_cols:
        op.add_column('printer', sa.Column('mmu_type', sa.String(), nullable=True))
        print("[MIGRATION] Added mmu_type to printer")

    if 'mmu_gate_count' not in existing_cols:
        op.add_column('printer', sa.Column('mmu_gate_count', sa.Integer(), nullable=True))
        print("[MIGRATION] Added mmu_gate_count to printer")


def downgrade() -> None:
    """Downgrade: MMU-Felder wieder entfernen."""
    op.drop_column('printer', 'mmu_gate_count')
    op.drop_column('printer', 'mmu_type')
    op.drop_column('printer', 'has_mmu')
