from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select
from typing import List, Optional
from datetime import datetime
from app.database import get_session
from app.models.job import Job, JobCreate, JobRead, JobSpoolUsage
from app.models.spool import Spool
from app.models.printer import Printer
from app.models.settings import Setting

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/", response_model=List[JobRead])
def get_all_jobs(session: Session = Depends(get_session)):
    """Alle Druckaufträge abrufen"""
    jobs = session.exec(select(Job).order_by(Job.started_at.desc())).all() # type: ignore
    return jobs

@router.get("/with-usage")
def get_all_jobs_with_usage(session: Session = Depends(get_session)):
    """Alle Jobs inkl. Spulenverbrauch (job_spool_usage) liefern"""
    jobs = session.exec(select(Job).order_by(Job.started_at.desc())).all()
    result = []
    for job in jobs:
        usages = session.exec(
            select(JobSpoolUsage).where(JobSpoolUsage.job_id == job.id).order_by(JobSpoolUsage.order_index)
        ).all()
        item = job.model_dump()
        item["usages"] = [u.model_dump() for u in usages]
        result.append(item)
    return result


@router.get("/stats/summary")
def get_job_stats(session: Session = Depends(get_session)):
    """Job-Statistiken abrufen"""
    jobs = session.exec(select(Job)).all()
    
    total_jobs = len(jobs)
    total_filament_g = sum(job.filament_used_g for job in jobs)
    total_filament_m = sum(job.filament_used_mm for job in jobs) / 1000  # mm to m

    completed_jobs = [job for job in jobs if job.finished_at is not None]
    active_jobs = total_jobs - len(completed_jobs)

    # Energie-Berechnung
    now = datetime.utcnow()
    default_power_kw = 0.30  # Schätzung wenn kein Wert hinterlegt
    power_exact_kwh = 0.0
    power_est_kwh = 0.0
    total_duration_h = 0.0

    # Schnellzugriff: alle Printer laden
    printers = {p.id: p for p in session.exec(select(Printer)).all()}

    for job in jobs:
        start = job.started_at
        end = job.finished_at or now
        duration_h = max((end - start).total_seconds(), 0) / 3600.0
        total_duration_h += duration_h

        printer = printers.get(job.printer_id)
        power = printer.power_consumption_kw if printer else None
        if power is not None:
            power_exact_kwh += power * duration_h
        else:
            power_est_kwh += default_power_kw * duration_h

    energy_kwh = power_exact_kwh + power_est_kwh

    # Strompreis laden
    price_setting = session.exec(select(Setting).where(Setting.key == "cost.electricity_price_kwh")).first()
    price_kwh = float(price_setting.value) if price_setting and price_setting.value else None
    energy_cost = energy_kwh * price_kwh if price_kwh is not None else None

    return {
        "total_jobs": total_jobs,
        "completed_jobs": len(completed_jobs),
        "active_jobs": active_jobs,
        "total_filament_g": round(total_filament_g, 2),
        "total_filament_m": round(total_filament_m, 2),
        "total_duration_h": round(total_duration_h, 2),
        "energy_kwh_exact": round(power_exact_kwh, 3),
        "energy_kwh_estimated": round(power_est_kwh, 3),
        "energy_kwh_total": round(energy_kwh, 3),
        "energy_cost_total": round(energy_cost, 2) if energy_cost is not None else None,
        "energy_price_kwh": price_kwh,
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


class JobSpoolUpdate(SQLModel):
    spool_id: Optional[str] = None


class JobManualUsageUpdate(SQLModel):
    """Model für manuelle Verbrauchseingabe bei Jobs ohne AMS"""
    spool_id: Optional[str] = None  # Spule zuordnen (Pflicht!)
    used_g: Optional[float] = None   # Verbrauch in Gramm
    used_mm: Optional[float] = None  # Verbrauch in Millimetern


@router.patch("/{job_id}/spool", response_model=JobRead)
def override_job_spool(job_id: str, payload: JobSpoolUpdate, session: Session = Depends(get_session)):
    """
    Spulen-Zuordnung eines Jobs überschreiben (oder entfernen).
    spool_id None entfernt die Zuordnung.
    """
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    if payload.spool_id:
        spool = session.get(Spool, payload.spool_id)
        if not spool:
            raise HTTPException(status_code=400, detail="Spule nicht gefunden")

    db_job.spool_id = payload.spool_id
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


@router.patch("/{job_id}/manual-usage", response_model=JobRead)
def update_manual_usage(job_id: str, payload: JobManualUsageUpdate, session: Session = Depends(get_session)):
    """
    Manuelle Verbrauchseingabe für Jobs ohne AMS-Tracking.
    Spule muss zugeordnet werden (Pflicht), dann wird Verbrauch von Spule abgezogen.
    """
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    # Spule ist Pflicht!
    if not payload.spool_id:
        raise HTTPException(status_code=400, detail="Spule muss zugeordnet werden")

    spool = session.get(Spool, payload.spool_id)
    if not spool:
        raise HTTPException(status_code=400, detail="Spule nicht gefunden")

    # Spule zuordnen
    db_job.spool_id = payload.spool_id

    # Verbrauch setzen (mindestens einer muss angegeben sein)
    if payload.used_g is None and payload.used_mm is None:
        raise HTTPException(status_code=400, detail="Verbrauch (used_g oder used_mm) muss angegeben werden")

    if payload.used_mm is not None:
        db_job.filament_used_mm = payload.used_mm
    if payload.used_g is not None:
        db_job.filament_used_g = payload.used_g

    # Von Spule abziehen (wenn Gewicht vorhanden)
    if payload.used_g and spool.weight_current is not None:
        new_weight = max(0, float(spool.weight_current) - float(payload.used_g))
        spool.weight_current = new_weight

        # Spule als "leer" markieren wenn unter 50g
        if new_weight < 50:
            spool.is_empty = True

        session.add(spool)

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
