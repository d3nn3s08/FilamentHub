from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import select, Session
from typing import List

from app.database import get_session
from app.models.material import Material, MaterialCreateSchema, MaterialUpdateSchema, MaterialReadSchema

router = APIRouter(prefix="/api/materials", tags=["Materials"])

def _normalize_material_payload(data: MaterialCreateSchema | MaterialUpdateSchema) -> dict:
    payload = data.model_dump(exclude_unset=True)
    # remove fields that are not persisted (e.g. material_type/type alias)
    payload.pop("material_type", None)
    # normalize printer_slot strings like "AMS-1" to int
    slot = payload.get("printer_slot")
    if isinstance(slot, str):
        digits = "".join(filter(str.isdigit, slot))
        payload["printer_slot"] = int(digits) if digits else None
    return payload


@router.get("/", response_model=List[MaterialReadSchema])
def list_materials(session: Session = Depends(get_session)):
    result = session.exec(select(Material)).all()
    return [MaterialReadSchema.model_validate(m) for m in result]


@router.get("/{material_id}", response_model=MaterialReadSchema)
def get_material(material_id: str, session: Session = Depends(get_session)):
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    return MaterialReadSchema.model_validate(material)


@router.post("/", response_model=MaterialReadSchema, status_code=status.HTTP_201_CREATED)
def create_material(data: MaterialCreateSchema, session: Session = Depends(get_session)):
    exists = session.exec(select(Material).where(Material.name == data.name, Material.brand == getattr(data, "brand", None))).first()
    if exists:
        raise HTTPException(status_code=409, detail="Material existiert bereits")
    try:
        payload = _normalize_material_payload(data)
        material = Material(**payload)
        session.add(material)
        session.commit()
        session.refresh(material)
        return MaterialReadSchema.model_validate(material)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Validierung: {e}")


@router.put("/{material_id}", response_model=MaterialReadSchema)
def update_material(material_id: str, data: MaterialUpdateSchema, session: Session = Depends(get_session)):
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    update_data = _normalize_material_payload(data)
    for key, value in update_data.items():
        setattr(material, key, value)
    try:
        session.add(material)
        session.commit()
        session.refresh(material)
        return MaterialReadSchema.model_validate(material)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Validierung: {e}")


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(material_id: str, session: Session = Depends(get_session)):
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material nicht gefunden")
    session.delete(material)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
