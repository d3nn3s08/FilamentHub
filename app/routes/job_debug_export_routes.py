import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.database import get_session
from app.routes.config_routes import _load_config
from app.services.job_debug_export_service import get_job_debug_export_service

router = APIRouter(prefix="/api/debug/job-exports", tags=["Debug Job Exports"])
logger = logging.getLogger("app")


@router.get("")
@router.get("/")
def list_job_exports(session: Session = Depends(get_session)):
    service = get_job_debug_export_service()
    config = _load_config(session)
    debug_cfg = config.get("debug", {}).get("job_export", {})
    return {
        "enabled": bool(debug_cfg.get("enabled", False)),
        "max_jobs": int(debug_cfg.get("max_jobs", 2) or 2),
        "exports": service.list_exports(),
    }


@router.get("/{log_id}/download")
def download_job_export(log_id: str):
    service = get_job_debug_export_service()
    file_path = service.get_export_file(log_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Job-Export nicht gefunden")

    filename = Path(file_path).name
    return FileResponse(
        path=file_path,
        media_type="application/json",
        filename=filename,
    )
