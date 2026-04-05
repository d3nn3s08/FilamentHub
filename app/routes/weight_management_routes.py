"""
FastAPI Routes for Weight Management and History

Provides endpoints for:
- Conflict resolution (Cloud vs DB)
- Weight history retrieval
- Archived spools by number
- Spool empty marking
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlmodel import Session, select
import asyncio
import json

from app.database import get_session
from app.models.spool import Spool
from app.models.weight_history import WeightHistory, WeightHistoryRead
from app.services.ams_weight_manager import (
    resolve_weight_conflict,
    mark_spool_empty,
)

router = APIRouter(prefix="/api/weight", tags=["weight-management"])

# ========================================
# Global Pub/Sub für Weight Conflicts
# ========================================
# Each connected client gets its own queue
connected_clients: set = set()

# Smart Resolve: Track resolved conflicts to prevent re-triggering
# Format: {spool_uuid: {"resolved_at": timestamp}}
_resolved_conflicts: dict = {}
RESOLVE_COOLDOWN_SECONDS = 300  # 5 minutes cooldown after resolve


def mark_conflict_resolved(spool_uuid: str, cloud_weight: float, db_weight: float):
    """Mark a conflict as resolved - won't trigger again for 5 minutes"""
    import time
    _resolved_conflicts[spool_uuid] = {
        "resolved_at": time.time()
    }
    print(f"[WEIGHT SSE] Conflict marked as resolved for {spool_uuid} - cooldown {RESOLVE_COOLDOWN_SECONDS}s")


def clear_resolved_conflict(spool_uuid: str):
    """Clear resolved state for a spool"""
    if spool_uuid in _resolved_conflicts:
        del _resolved_conflicts[spool_uuid]
        print(f"[WEIGHT SSE] Resolved state cleared for {spool_uuid}")


async def broadcast_weight_conflict(conflict_data: dict):
    """Broadcasts weight conflict to ALL connected clients"""
    import time

    spool_uuid = conflict_data.get('spool_uuid')

    # Smart Resolve: Skip if this conflict was recently resolved
    if spool_uuid and spool_uuid in _resolved_conflicts:
        resolved = _resolved_conflicts[spool_uuid]
        elapsed = time.time() - resolved.get('resolved_at', 0)

        if elapsed < RESOLVE_COOLDOWN_SECONDS:
            remaining = int(RESOLVE_COOLDOWN_SECONDS - elapsed)
            print(f"[WEIGHT SSE] Skipping conflict for spool {conflict_data.get('spool_number')} - resolved {int(elapsed)}s ago, cooldown {remaining}s remaining")
            return
        else:
            # Cooldown expired - clear and allow new conflict
            clear_resolved_conflict(spool_uuid)

    print(f"[WEIGHT SSE] Broadcasting to {len(connected_clients)} clients: {conflict_data.get('spool_number')}")

    # Send to all connected clients
    disconnected = set()
    for client_queue in connected_clients:
        try:
            client_queue.put_nowait(conflict_data)
        except Exception as e:
            print(f"[WEIGHT SSE] Failed to send to client: {e}")
            disconnected.add(client_queue)

    # Clean up disconnected clients
    for q in disconnected:
        connected_clients.discard(q)


# ========================================
# Request/Response Models
# ========================================

class ConflictResolutionRequest(BaseModel):
    """Request for conflict resolution"""
    spool_uuid: str
    selected_source: str  # "db" or "cloud"
    cloud_weight: float
    db_weight: float


class MarkEmptyRequest(BaseModel):
    """Request to mark spool as empty"""
    spool_uuid: str


class ArchivedSpoolResponse(BaseModel):
    """Response for archived spools"""
    uuid: str
    last_number: int
    color: Optional[str]
    vendor: Optional[str]
    emptied_at: Optional[str]
    total_changes: int


# ========================================
# Routes
# ========================================

@router.post("/resolve_conflict")
async def api_resolve_weight_conflict(
    request: ConflictResolutionRequest,
    session: Session = Depends(get_session)
):
    """
    Resolves weight conflict between Cloud and DB

    Frontend calls this after user selection in dialog
    """
    result = resolve_weight_conflict(
        spool_uuid=request.spool_uuid,
        selected_source=request.selected_source,
        cloud_weight=request.cloud_weight,
        db_weight=request.db_weight,
        user="admin",  # TODO: Get from auth
        session=session
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Mark conflict as resolved - prevents re-triggering until values change
    mark_conflict_resolved(
        spool_uuid=request.spool_uuid,
        cloud_weight=request.cloud_weight,
        db_weight=result.get("updated_weight", request.db_weight)
    )

    return result


@router.get("/spools/{spool_uuid}/history", response_model=List[WeightHistoryRead])
async def get_spool_history(
    spool_uuid: str,
    session: Session = Depends(get_session)
):
    """
    Gets weight history for a spool (UUID-based!)

    Important: UUID, not number!
    """
    stmt = select(WeightHistory).where(
        WeightHistory.spool_uuid == spool_uuid
    ).order_by(
        WeightHistory.timestamp.desc()
    )

    history = session.exec(stmt).all()

    return [
        WeightHistoryRead(
            id=h.id,
            spool_uuid=h.spool_uuid,
            spool_number=h.spool_number,
            old_weight=h.old_weight,
            new_weight=h.new_weight,
            source=h.source,
            change_reason=h.change_reason,
            ams_type=h.ams_type,
            user=h.user,
            timestamp=h.timestamp,
            details=h.details
        )
        for h in history
    ]


@router.get("/spools/number/{spool_number}/archived", response_model=List[ArchivedSpoolResponse])
async def get_archived_spools_for_number(
    spool_number: int,
    session: Session = Depends(get_session)
):
    """
    Gets all archived spools for a specific number

    For archive function in history view
    """
    stmt = select(Spool).where(
        Spool.last_number == spool_number,
        Spool.is_active == False
    ).order_by(
        Spool.emptied_at.desc()
    )

    archived = session.exec(stmt).all()

    result = []
    for spool in archived:
        # Count history entries
        count_stmt = select(WeightHistory).where(
            WeightHistory.spool_uuid == spool.tray_uuid
        )
        history_count = len(session.exec(count_stmt).all())

        result.append(
            ArchivedSpoolResponse(
                uuid=spool.tray_uuid,
                last_number=spool.last_number,
                color=spool.color,
                vendor=spool.vendor,
                emptied_at=spool.emptied_at,
                total_changes=history_count
            )
        )

    return result


@router.post("/spools/mark_empty")
async def api_mark_spool_empty(
    request: MarkEmptyRequest,
    session: Session = Depends(get_session)
):
    """
    Marks spool as empty and releases number

    Frontend calls this when spool is completely consumed
    """
    result = mark_spool_empty(
        spool_uuid=request.spool_uuid,
        user="admin",  # TODO: Get from auth
        session=session
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ========================================
# Server-Sent Events (SSE) für Weight Conflicts
# ========================================

@router.get("/conflicts/stream")
async def weight_conflicts_stream():
    """
    SSE endpoint for real-time weight conflict notifications

    Frontend connects to this endpoint to receive conflict alerts
    """
    # Create a queue for this specific client
    client_queue = asyncio.Queue()
    connected_clients.add(client_queue)
    print(f"[WEIGHT SSE] Client connected. Total clients: {len(connected_clients)}")

    async def event_generator():
        from app.main import is_app_shutting_down
        try:
            while not is_app_shutting_down():
                try:
                    # Wait for next conflict event for THIS client
                    conflict_data = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=30.0  # Heartbeat every 30s
                    )

                    # Send event to client
                    yield f"data: {json.dumps(conflict_data)}\n\n"

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
                except asyncio.CancelledError:
                    # Client disconnected or server shutdown
                    break
                except Exception as e:
                    print(f"[WEIGHT SSE] Error: {e}")
                    yield f"data: {{\"error\": \"stream_error\"}}\n\n"
                    await asyncio.sleep(1)
        finally:
            # Clean up when client disconnects
            connected_clients.discard(client_queue)
            print(f"[WEIGHT SSE] Client disconnected. Total clients: {len(connected_clients)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ========================================
# TEST ENDPOINT - Simulate Conflict
# ========================================

@router.post("/conflicts/test/{spool_number}")
async def test_trigger_conflict(
    spool_number: int,
    session: Session = Depends(get_session)
):
    """
    TEST ONLY: Manually trigger a weight conflict for a spool number

    This broadcasts a conflict event to all connected clients
    """
    # Find active spool with this number
    stmt = select(Spool).where(
        Spool.spool_number == spool_number,
        Spool.is_active == True
    )
    spool = session.exec(stmt).first()

    if not spool:
        raise HTTPException(status_code=404, detail=f"Keine aktive Spule mit Nummer {spool_number} gefunden")

    # Create fake conflict
    db_weight = float(spool.weight_current or 0)
    conflict_data = {
        "type": "weight_conflict",
        "spool_uuid": spool.tray_uuid,
        "spool_number": spool.spool_number,
        "material_name": f"{spool.vendor or ''} {spool.color or ''}".strip() or "Unbekannt",
        "cloud_weight": db_weight + 50.0,  # Simulate cloud is 50g more
        "db_weight": db_weight,
        "difference": 50.0,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Broadcast to all listeners
    await broadcast_weight_conflict(conflict_data)

    return {
        "success": True,
        "message": f"Konflikt für Spule #{spool_number} ausgelöst",
        "conflict": conflict_data
    }
