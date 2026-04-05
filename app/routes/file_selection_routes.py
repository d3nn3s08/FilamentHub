"""
File Selection Routes - API für manuelle File-Auswahl bei Low-Confidence-Matches

Wenn Title-Matching Score < 60%, wird User aufgefordert richtige Datei auszuwählen.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models.file_selection_pending import FileSelectionPending
from app.models.job import Job
from app.routes.notification_routes import broadcast_notification

router = APIRouter()
logger = logging.getLogger("app")


@router.get("/api/file-selection/pending")
def get_pending_selections(session: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    Liefert alle ausstehenden File-Auswahl-Requests

    Returns:
        {
            "pending": [
                {
                    "id": 1,
                    "job_id": "abc123",
                    "job_name": "Rainbow Benchy",
                    "best_match": {
                        "filename": "benchy.3mf",
                        "title": "Benchy",
                        "score": 38
                    },
                    "candidates": [...]
                }
            ]
        }
    """
    pending = session.exec(
        select(FileSelectionPending)
        .where(FileSelectionPending.status == "pending")
        .order_by(FileSelectionPending.created_at.desc())
    ).all()

    result = []
    for p in pending:
        try:
            candidates = json.loads(p.candidates_json) if p.candidates_json else []
        except Exception:
            candidates = []

        result.append({
            "id": p.id,
            "job_id": p.job_id,
            "job_name": p.job_name,
            "target_filename": p.target_filename,
            "best_match": {
                "filename": p.best_match_filename,
                "title": p.best_match_title,
                "score": p.best_match_score
            } if p.best_match_filename else None,
            "candidates": candidates,
            "created_at": p.created_at.isoformat()
        })

    return {"pending": result}


@router.post("/api/file-selection/{selection_id}/resolve")
async def resolve_file_selection(
    selection_id: int,
    request: Request,
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Löst ausstehende File-Auswahl auf

    Body:
        {
            "filename": "Heart_of_Dragon.gcode.3mf"  # User-Auswahl
        }

    Returns:
        {
            "success": true,
            "weight_g": 74.28  # Extrahiertes Gewicht
        }
    """
    pending = session.get(FileSelectionPending, selection_id)
    if not pending:
        raise HTTPException(status_code=404, detail="File selection nicht gefunden")

    if pending.status != "pending":
        raise HTTPException(status_code=400, detail="File selection bereits aufgelöst")

    payload = await request.json()
    selected_filename = payload.get("filename")

    if not selected_filename:
        raise HTTPException(status_code=400, detail="filename fehlt")

    # Validiere dass Datei in Kandidaten ist
    try:
        candidates = json.loads(pending.candidates_json) if pending.candidates_json else []
        valid_filenames = [c["filename"] for c in candidates]
        if selected_filename not in valid_filenames:
            raise HTTPException(status_code=400, detail=f"Datei '{selected_filename}' nicht in Kandidaten")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Kandidaten-Daten beschädigt")

    # Download und extrahiere Gewicht
    try:
        from app.services.gcode_ftp_service import GCodeFTPService
        ftp_service = GCodeFTPService()

        weight = ftp_service._download_and_extract_weight(
            printer_ip=pending.printer_ip,
            api_key=pending.api_key,
            filename=selected_filename
        )

        if not weight:
            raise HTTPException(status_code=500, detail="Konnte Gewicht nicht extrahieren")

        # Update Job mit Gewicht
        job = session.get(Job, pending.job_id)
        if job and not job.filament_used_g:
            job.filament_used_g = weight
            session.add(job)

        # Markiere als resolved
        pending.status = "resolved"
        pending.resolved_filename = selected_filename
        pending.resolved_weight_g = weight
        pending.resolved_at = datetime.utcnow()

        session.add(pending)
        session.commit()

        logger.info(
            f"[FILE SELECTION] Resolved: job={pending.job_id} "
            f"file='{selected_filename}' weight={weight}g"
        )

        return {
            "success": True,
            "filename": selected_filename,
            "weight_g": weight
        }

    except Exception as e:
        logger.exception(f"[FILE SELECTION] Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Download: {str(e)}")


@router.post("/api/file-selection/{selection_id}/cancel")
async def cancel_file_selection(
    selection_id: int,
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Bricht File-Auswahl ab (nutze neueste Datei als Fallback)
    """
    pending = session.get(FileSelectionPending, selection_id)
    if not pending:
        raise HTTPException(status_code=404, detail="File selection nicht gefunden")

    if pending.status != "pending":
        raise HTTPException(status_code=400, detail="File selection bereits aufgelöst")

    pending.status = "cancelled"
    pending.resolved_at = datetime.utcnow()

    session.add(pending)
    session.commit()

    logger.info(f"[FILE SELECTION] Cancelled: job={pending.job_id}")

    return {"success": True, "message": "File selection abgebrochen"}


async def create_file_selection_request(
    session: Session,
    job_id: str,
    job_name: str,
    printer_ip: str,
    api_key: str,
    target_filename: str,
    candidates: List[Dict[str, Any]],
    best_match: Optional[Dict[str, Any]] = None
) -> FileSelectionPending:
    """
    Erstellt File-Selection-Request und broadcasted Notification

    Args:
        candidates: [{"filename": "...", "title": "...", "score": 85}, ...]
        best_match: {"filename": "...", "title": "...", "score": 38}
    """
    # Erstelle DB-Eintrag
    pending = FileSelectionPending(
        job_id=job_id,
        job_name=job_name,
        printer_ip=printer_ip,
        api_key=api_key,
        target_filename=target_filename,
        best_match_filename=best_match["filename"] if best_match else None,
        best_match_score=best_match["score"] if best_match else None,
        best_match_title=best_match["title"] if best_match else None,
        candidates_json=json.dumps(candidates),
        status="pending"
    )

    session.add(pending)
    session.commit()
    session.refresh(pending)

    # Broadcast Notification an Frontend
    notification_payload = {
        "id": "file_selection_required",
        "type": "warn",
        "label": "Datei-Auswahl erforderlich",
        "message": f"Für Job '{job_name}' konnte keine eindeutige Datei gefunden werden. Bitte wähle die richtige Datei aus.",
        "persistent": True,
        "context": {
            "selection_id": pending.id,
            "job_id": job_id,
            "job_name": job_name,
            "best_match": best_match,
            "num_candidates": len(candidates)
        }
    }

    try:
        await broadcast_notification(notification_payload)
        logger.info(
            f"[FILE SELECTION] Created request: id={pending.id} job={job_id} "
            f"candidates={len(candidates)}"
        )
    except Exception as e:
        logger.exception(f"[FILE SELECTION] Failed to broadcast notification: {e}")

    return pending
