from fastapi import APIRouter, HTTPException
from typing import Any

from app.services.live_state import get_live_state

router = APIRouter(prefix="/api/live-state", tags=["LiveState"])


@router.get("/{device_id}")
async def get_live_state_endpoint(device_id: str) -> Any:
    st = get_live_state(device_id)
    if not st:
        raise HTTPException(status_code=404, detail="Live state not found")
    return st


from app.services.live_state import get_all_live_state


@router.get("/")
async def list_live_state() -> Any:
    return get_all_live_state()
