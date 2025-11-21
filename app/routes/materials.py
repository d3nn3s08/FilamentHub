from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, Session
from typing import List

from app.database import get_session
from app.models.material import Material, MaterialCreate, MaterialRead

router = APIRouter(prefix="/api/materials", tags=["Materials"])


@router.get("/", response_model=List[MaterialRead])
def list_materials(session: Session = Depends(get_session)):
    result = session.exec(select(Material)).all()
    return result


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(material_id: str, session: Session = Depends(get_session)):
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    return material


@router.post("/", response_model=MaterialRead)
def create_material(data: MaterialCreate, session: Session = Depends(get_session)):
    material = Material.from_orm(data)
    session.add(material)
    session.commit()
    session.refresh(material)
    return material


@router.put("/{material_id}", response_model=MaterialRead)
def update_material(material_id: str, data: MaterialCreate, session: Session = Depends(get_session)):
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(material, key, value)

    session.add(material)
    session.commit()
    session.refresh(material)
    return material


@router.delete("/{material_id}")
def delete_material(material_id: str, session: Session = Depends(get_session)):
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    session.delete(material)
    session.commit()
    return {"status": "deleted"}
