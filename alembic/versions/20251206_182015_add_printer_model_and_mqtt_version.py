"""Add model and mqtt_version to printer"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251206_182015_add_printer_model_and_mqtt_version"
down_revision: Union[str, Sequence[str], None] = "20251204_01_add_settings_and_userflag"
branch_labels = None
depends_on = None

def upgrade():
    # add with server_default for backfill
    op.add_column("printer", sa.Column("model", sa.String(length=32), nullable=False, server_default="X1C"))
    op.add_column("printer", sa.Column("mqtt_version", sa.String(length=8), nullable=False, server_default="311"))
    # drop defaults after data is populated
    with op.batch_alter_table("printer") as batch_op:
        batch_op.alter_column("model", server_default=None)
        batch_op.alter_column("mqtt_version", server_default=None)


def downgrade():
    op.drop_column("printer", "mqtt_version")
    op.drop_column("printer", "model")
