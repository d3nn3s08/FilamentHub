from typing import Optional
from uuid import uuid4

from sqlmodel import SQLModel, Field as SQLField


class AMSTrayBase(SQLModel):
    ams_unit_id: Optional[str] = SQLField(default=None, foreign_key="amsunit.id")
    tray_index: Optional[int] = None
    tray_uuid: Optional[str] = None
    remaining_weight: Optional[float] = None
    material_type: Optional[str] = None
    last_seen: Optional[str] = None
    metadata: Optional[str] = None


class AMSTray(AMSTrayBase, table=True):
    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True)


class AMSTrayRead(AMSTrayBase):
    id: str

