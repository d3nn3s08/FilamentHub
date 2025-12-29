from fastapi import APIRouter, HTTPException
from typing import Any
import logging

import app.services.live_state as live_state_module
from app.services.ams_normalizer import normalize_live_state, normalize_device

router = APIRouter(prefix="/api/ams", tags=["AMS"])
logger = logging.getLogger(__name__)


@router.get("/")
async def list_ams() -> Any:
    logger.debug("Listing normalized AMS live state")
    live = live_state_module.get_all_live_state()
    return normalize_live_state(live)


@router.get("/{device}")
async def get_ams_device(device: str) -> Any:
    logger.debug("Getting normalized AMS for device %s", device)
    st = live_state_module.get_live_state(device)
    if not st:
        raise HTTPException(status_code=404, detail="Live state not found")
    return normalize_device(st)
