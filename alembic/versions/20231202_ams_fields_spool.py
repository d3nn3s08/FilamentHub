"""add ams fields to spool

Revision ID: 20231202_ams_fields
Revises: 4e2c1c9d8b3e
Create Date: 2023-12-02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20231202_ams_fields"
down_revision = "4e2c1c9d8b3e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("spool") as batch_op:
        batch_op.add_column(sa.Column("printer_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("ams_slot", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tag_uid", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tray_uuid", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tray_color", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tray_type", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("remain_percent", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("last_seen", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_spool_printer_id_printer",
            "printer",
            ["printer_id"],
            ["id"],
            ondelete=None,
        )


def downgrade():
    with op.batch_alter_table("spool") as batch_op:
        batch_op.drop_constraint("fk_spool_printer_id_printer", type_="foreignkey")
        batch_op.drop_column("last_seen")
        batch_op.drop_column("remain_percent")
        batch_op.drop_column("tray_type")
        batch_op.drop_column("tray_color")
        batch_op.drop_column("tray_uuid")
        batch_op.drop_column("tag_uid")
        batch_op.drop_column("ams_slot")
        batch_op.drop_column("printer_id")
