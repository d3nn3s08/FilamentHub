from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from app.database import engine
from app.models.lexikon import LexikonEntry, LexikonEntryCreate, LexikonEntryUpdate, LexikonEntryRead
from datetime import datetime
from typing import List

router = APIRouter(prefix="/api/lexikon", tags=["lexikon"])


def get_session():
    with Session(engine) as session:
        yield session


@router.get("/entries", response_model=List[LexikonEntryRead])
def get_all_entries(session: Session = Depends(get_session)):
    """Get all lexikon entries"""
    entries = session.exec(select(LexikonEntry)).all()
    return entries


@router.get("/entries/{entry_id}", response_model=LexikonEntryRead)
def get_entry(entry_id: str, session: Session = Depends(get_session)):
    """Get a specific lexikon entry by ID"""
    entry = session.get(LexikonEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("/entries", response_model=LexikonEntryRead)
def create_entry(entry_data: LexikonEntryCreate, session: Session = Depends(get_session)):
    """Create a new lexikon entry"""
    now = datetime.utcnow().isoformat()

    entry = LexikonEntry(
        **entry_data.model_dump(),
        created_at=now,
        updated_at=now
    )

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.put("/entries/{entry_id}", response_model=LexikonEntryRead)
def update_entry(
    entry_id: str,
    entry_data: LexikonEntryUpdate,
    session: Session = Depends(get_session)
):
    """Update an existing lexikon entry"""
    entry = session.get(LexikonEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_data = entry_data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow().isoformat()

    for key, value in update_data.items():
        setattr(entry, key, value)

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: str, session: Session = Depends(get_session)):
    """Delete a lexikon entry"""
    entry = session.get(LexikonEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    session.delete(entry)
    session.commit()
    return {"message": "Entry deleted successfully"}
