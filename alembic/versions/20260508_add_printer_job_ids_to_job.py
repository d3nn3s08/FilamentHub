"""add printer job identifiers to job

Revision ID: 20260508_add_printer_job_ids
Revises: 20260406_02_add_missing_bambu_cloud_columns
Create Date: 2026-05-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260508_add_printer_job_ids"
down_revision: Union[str, Sequence[str], None] = "20260406_02_add_missing_bambu_cloud_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("job")}

    if "printer_job_id" not in existing_cols:
        op.add_column("job", sa.Column("printer_job_id", sa.String(), nullable=True))
    if "printer_subtask_id" not in existing_cols:
        op.add_column("job", sa.Column("printer_subtask_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("job", "printer_subtask_id")
    op.drop_column("job", "printer_job_id")
