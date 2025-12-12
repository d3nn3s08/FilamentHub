from sqlmodel import SQLModel, Field
from typing import Optional

class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Optional[str] = None

class UserFlag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    flag: str
    value: bool = False
