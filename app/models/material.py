from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4


class MaterialBase(SQLModel):
    name: str
    brand: Optional[str] = None
    color: Optional[str] = None  # HEX oder Text
    density: float = 1.24  # g/cm³, Standard PLA
    diameter: float = 1.75  # mm
    notes: Optional[str] = None


class Material(MaterialBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


class MaterialCreate(MaterialBase):
    pass


class MaterialRead(MaterialBase):
    id: str
