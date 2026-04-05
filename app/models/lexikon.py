from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, ConfigDict


class LexikonEntryBase(SQLModel):
    """Base model for Lexikon entries"""
    title: str
    category: str  # material, term, property, spool
    icon: str = "📚"
    description: str
    keywords: Optional[str] = None  # Comma-separated keywords for search

    # Properties (JSON-like key-value pairs)
    property_1_label: Optional[str] = None
    property_1_value: Optional[str] = None
    property_2_label: Optional[str] = None
    property_2_value: Optional[str] = None
    property_3_label: Optional[str] = None
    property_3_value: Optional[str] = None
    property_4_label: Optional[str] = None
    property_4_value: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LexikonEntry(LexikonEntryBase, table=True):
    __tablename__ = "lexikon_entries"  # type: ignore[reportAssignmentType]
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)


# Pydantic Schemas
class LexikonEntryCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    category: str
    icon: str = "📚"
    description: str
    keywords: Optional[str] = None

    property_1_label: Optional[str] = None
    property_1_value: Optional[str] = None
    property_2_label: Optional[str] = None
    property_2_value: Optional[str] = None
    property_3_label: Optional[str] = None
    property_3_value: Optional[str] = None
    property_4_label: Optional[str] = None
    property_4_value: Optional[str] = None


class LexikonEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None

    property_1_label: Optional[str] = None
    property_1_value: Optional[str] = None
    property_2_label: Optional[str] = None
    property_2_value: Optional[str] = None
    property_3_label: Optional[str] = None
    property_3_value: Optional[str] = None
    property_4_label: Optional[str] = None
    property_4_value: Optional[str] = None


class LexikonEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: str
    icon: str
    description: str
    keywords: Optional[str] = None

    property_1_label: Optional[str] = None
    property_1_value: Optional[str] = None
    property_2_label: Optional[str] = None
    property_2_value: Optional[str] = None
    property_3_label: Optional[str] = None
    property_3_value: Optional[str] = None
    property_4_label: Optional[str] = None
    property_4_value: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
