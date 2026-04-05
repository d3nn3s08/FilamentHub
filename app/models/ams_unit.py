from typing import Optional
from uuid import uuid4

from sqlmodel import SQLModel, Field as SQLField
import sqlalchemy as sa


class AMSUnitBase(SQLModel):
    cloud_serial: Optional[str] = None
    name: Optional[str] = None
    trays_count: Optional[int] = None
    last_seen: Optional[str] = None
    # Avoid name `metadata` which conflicts with SQLAlchemy DeclarativeMeta.metadata
    # Persist to existing DB column named `metadata` using sa_column to keep schema stable.
    metadata_json: Optional[str] = SQLField(default=None, sa_column=sa.Column('metadata', sa.Text(), nullable=True))  # JSON text


class AMSUnit(AMSUnitBase, table=True):
    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True)


class AMSUnitRead(AMSUnitBase):
    id: str

