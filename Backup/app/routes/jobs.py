from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.database import get_session
from app.models.job import Job, JobCreate, JobRead

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/", response_model=List[JobRead])
def get_all_jobs(session: Session = Depends(get_session)):
    """Alle Druckaufträge abrufen"""
    jobs = session.exec(select(Job).order_by(Job.started_at.desc())).all() # type: ignore
    return jobs


@router.get("/stats/summary")
def get_job_stats(session: Session = Depends(get_session)):
    """Job-Statistiken abrufen"""
    jobs = session.exec(select(Job)).all()
    
    total_jobs = len(jobs)
    total_filament_g = sum(job.filament_used_g for job in jobs)
    total_filament_m = sum(job.filament_used_mm for job in jobs) / 1000  # mm to m
    
    # Abgeschlossene Jobs
    completed_jobs = [job for job in jobs if job.finished_at is not None]
    
    return {
        "total_jobs": total_jobs,
        "completed_jobs": len(completed_jobs),
        "active_jobs": total_jobs - len(completed_jobs),
        "total_filament_g": round(total_filament_g, 2),
        "total_filament_m": round(total_filament_m, 2)
    }


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: Session = Depends(get_session)):
    """Einzelnen Druckauftrag abrufen"""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")
    return job


@router.post("/", response_model=JobRead)
def create_job(job: JobCreate, session: Session = Depends(get_session)):
    """Neuen Druckauftrag anlegen"""
    db_job = Job.model_validate(job)
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


@router.put("/{job_id}", response_model=JobRead)
def update_job(job_id: str, job: JobCreate, session: Session = Depends(get_session)):
    """Druckauftrag aktualisieren"""
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")
    
    job_data = job.model_dump(exclude_unset=True)
    for key, value in job_data.items():
        setattr(db_job, key, value)
    
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


@router.delete("/{job_id}")
def delete_job(job_id: str, session: Session = Depends(get_session)):
    """Druckauftrag löschen"""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")
    
    session.delete(job)
    session.commit()
    return {"success": True, "message": "Druckauftrag gelöscht"}
