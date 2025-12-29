from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select
from typing import List, Optional, Any
from datetime import datetime
from app.database import get_session
from app.models.job import Job, JobCreate, JobRead, JobSpoolUsage
from app.models.spool import Spool
from app.models.printer import Printer
from app.models.settings import Setting
import app.services.live_state as live_state_module
from app.services.eta import calculate_eta

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _compute_eta_for_job(job: Job, session: Session) -> Optional[int]:
    """Try to compute ETA for a Job using printer model and live-state payload.

    Returns seconds (int) or None.
    """
    try:
        printer = session.get(Printer, job.printer_id)
        if not printer:
            return None

        # Try to get live payload by cloud_serial
        cloud = printer.cloud_serial
        live_entry = live_state_module.get_live_state(cloud) if cloud else None
        payload = None
        if isinstance(live_entry, dict):
            payload = live_entry.get("payload") or {}

        # Normalize print payload
        print_data = None
        if isinstance(payload, dict):
            print_data = payload.get("print") or payload

        # Extract fields
        layer_num = None
        total_layer_num = None
        bambu_remaining_time = None

        if isinstance(print_data, dict):
            layer_num = print_data.get("layer_current") or print_data.get("layer_num") or print_data.get("layer") or print_data.get("layer_index")
            total_layer_num = print_data.get("layer_total") or print_data.get("layer_count") or print_data.get("total_layers")
            bambu_remaining_time = print_data.get("remain_time_s") or print_data.get("mc_remaining_time") or print_data.get("mc_remaining_seconds") or print_data.get("remaining_time") or print_data.get("remain")

        # Coerce types
        try:
            layer_num = int(layer_num) if layer_num is not None else None
        except Exception:
            layer_num = None
        try:
            total_layer_num = int(total_layer_num) if total_layer_num is not None else None
        except Exception:
            total_layer_num = None
        try:
            if bambu_remaining_time is not None:
                bambu_remaining_time = int(float(bambu_remaining_time))
        except Exception:
            bambu_remaining_time = None

        eta = calculate_eta(
            printer_model=printer.model if hasattr(printer, "model") else None,
            started_at=job.started_at,
            layer_num=layer_num,
            total_layer_num=total_layer_num,
            bambu_remaining_time=bambu_remaining_time,
        )
        if eta is not None and eta < 0:
            eta = 0
        return eta
    except Exception:
        return None


def _coerce_dt(value: Any, now: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return now
    return now


@router.get("/", response_model=List[JobRead])
def get_all_jobs(session: Session = Depends(get_session)):
    """Alle Druckaufträge abrufen"""
    jobs = session.exec(select(Job).order_by(Job.started_at.desc())).all() # type: ignore
    # Attach ETA where possible (non-blocking)
    for j in jobs:
        try:
            j.eta_seconds = _compute_eta_for_job(j, session)
        except Exception:
            j.eta_seconds = None
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
        # compute ETA and inject
        try:
            item["eta_seconds"] = _compute_eta_for_job(job, session)
        except Exception:
            item["eta_seconds"] = None
        item["usages"] = [u.model_dump() for u in usages]
        result.append(item)
    return result


@router.get("/stats/summary")
def get_job_stats(session: Session = Depends(get_session)):
    """Job-Statistiken abrufen"""
    jobs = session.exec(select(Job)).all()
    
    total_jobs = len(jobs)
    total_filament_g = sum((job.filament_used_g or 0.0) for job in jobs)
    total_filament_m = sum((job.filament_used_mm or 0.0) for job in jobs) / 1000  # mm to m

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
        start = _coerce_dt(job.started_at, now)
        end = _coerce_dt(job.finished_at, now)
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
    try:
        job.eta_seconds = _compute_eta_for_job(job, session)
    except Exception:
        job.eta_seconds = None
    return job


@router.post("/", response_model=JobRead)
def create_job(job: JobCreate, session: Session = Depends(get_session)):
    """Neuen Druckauftrag anlegen"""
    db_job = Job.model_validate(job)

    # Wenn Spule zugewiesen und Verbrauch vorhanden: Von Spule abziehen
    if db_job.spool_id and db_job.filament_used_g and db_job.filament_used_g > 0:
        spool = session.get(Spool, db_job.spool_id)
        if spool:
            # Gewicht abziehen
            if spool.weight_current is not None:
                new_weight = max(0, float(spool.weight_current) - float(db_job.filament_used_g))
                spool.weight_current = new_weight

                # Prozentsatz neu berechnen
                if spool.weight_full and spool.weight_empty:
                    weight_range = float(spool.weight_full) - float(spool.weight_empty)
                    if weight_range > 0:
                        spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                        spool.remain_percent = max(0, min(100, spool.remain_percent))  # Clamp auf 0-100

                # Spule als "leer" markieren wenn unter 50g
                if new_weight < 50:
                    spool.is_empty = True

                session.add(spool)

    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        db_job.eta_seconds = None
    return db_job


@router.put("/{job_id}", response_model=JobRead)
def update_job(job_id: str, job: JobCreate, session: Session = Depends(get_session)):
    """Druckauftrag aktualisieren"""
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    # Merke alte Werte für Differenz-Berechnung
    old_spool_id = db_job.spool_id
    old_used_g = db_job.filament_used_g or 0

    job_data = job.model_dump(exclude_unset=True)
    for key, value in job_data.items():
        setattr(db_job, key, value)

    # Wenn Spule oder Verbrauch geändert wurde: Gewicht anpassen
    new_spool_id = db_job.spool_id
    new_used_g = db_job.filament_used_g or 0

    # Fall 1: Spule wurde geändert oder hinzugefügt
    if new_spool_id and new_spool_id != old_spool_id and new_used_g > 0:
        spool = session.get(Spool, new_spool_id)
        if spool:
            # Ganzen Verbrauch abziehen
            if spool.weight_current is not None:
                new_weight = max(0, float(spool.weight_current) - float(new_used_g))
                spool.weight_current = new_weight

                # Prozentsatz neu berechnen
                if spool.weight_full and spool.weight_empty:
                    weight_range = float(spool.weight_full) - float(spool.weight_empty)
                    if weight_range > 0:
                        spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                        spool.remain_percent = max(0, min(100, spool.remain_percent))

                if new_weight < 50:
                    spool.is_empty = True

                session.add(spool)

    # Fall 2: Gleiche Spule, aber Verbrauch hat sich geändert
    elif new_spool_id and new_spool_id == old_spool_id and new_used_g != old_used_g:
        spool = session.get(Spool, new_spool_id)
        if spool and spool.weight_current is not None:
            # Differenz berechnen und anpassen
            diff_g = new_used_g - old_used_g
            new_weight = max(0, float(spool.weight_current) - diff_g)
            spool.weight_current = new_weight

            # Prozentsatz neu berechnen
            if spool.weight_full and spool.weight_empty:
                weight_range = float(spool.weight_full) - float(spool.weight_empty)
                if weight_range > 0:
                    spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                    spool.remain_percent = max(0, min(100, spool.remain_percent))

            if new_weight < 50:
                spool.is_empty = True

            session.add(spool)

    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        db_job.eta_seconds = None
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

        # Status auf "Aktiv" setzen bei manueller Zuweisung (wenn nicht leer)
        if not spool.is_empty and spool.status != "Aktiv":
            spool.status = "Aktiv"
            spool.is_open = True
            session.add(spool)

    db_job.spool_id = payload.spool_id
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        db_job.eta_seconds = None
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

    # Status auf "Aktiv" setzen bei manueller Zuweisung (wenn nicht leer)
    if not spool.is_empty and spool.status != "Aktiv":
        spool.status = "Aktiv"
        spool.is_open = True

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
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        db_job.eta_seconds = None
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
