from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, Session
from typing import List

from app.database import get_session
from app.models.spool import Spool, SpoolCreate, SpoolRead

router = APIRouter(prefix="/api/spools", tags=["Spools"])


@router.get("/", response_model=List[SpoolRead])
def list_spools(session: Session = Depends(get_session)):
    result = session.exec(select(Spool)).all()
    return result


@router.get("/{spool_id}", response_model=SpoolRead)
def get_spool(spool_id: str, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    return spool


@router.post("/", response_model=SpoolRead)
def create_spool(data: SpoolCreate, session: Session = Depends(get_session)):
    spool = Spool.from_orm(data)
    session.add(spool)
    session.commit()
    session.refresh(spool)
    return spool


@router.put("/{spool_id}", response_model=SpoolRead)
def update_spool(spool_id: str, data: SpoolCreate, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(spool, key, value)

    session.add(spool)
    session.commit()
    session.refresh(spool)
    return spool


@router.delete("/{spool_id}")
def delete_spool(spool_id: str, session: Session = Depends(get_session)):
    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")
    session.delete(spool)
    session.commit()
    return {"status": "deleted"}
