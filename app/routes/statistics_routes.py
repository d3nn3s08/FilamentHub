from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.job import Job
from app.models.printer import Printer
from app.models.spool import Spool
from app.models.material import Material
from app.models.settings import Setting

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


DEFAULT_POWER_KW = 0.30  # fallback when printer has no power_consumption_kw


def _job_duration_hours(job: Job, now: datetime) -> float:
    start = job.started_at or now
    end = job.finished_at or now
    return max((end - start).total_seconds(), 0) / 3600.0


def _energy_for_job(job: Job, printers: Dict[str, Printer], now: datetime) -> tuple[float, float]:
    """Returns (energy_exact_kwh, energy_est_kwh)."""
    duration_h = _job_duration_hours(job, now)
    printer = printers.get(job.printer_id)
    power = printer.power_consumption_kw if printer else None
    if power is not None:
        return power * duration_h, 0.0
    return 0.0, DEFAULT_POWER_KW * duration_h


@router.get("/timeline")
def timeline(days: int = 30, session: Session = Depends(get_session)):
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    jobs = session.exec(select(Job).where(Job.started_at >= since)).all()
    printers = {p.id: p for p in session.exec(select(Printer)).all()}

    buckets: Dict[str, Dict[str, float]] = {}
    for job in jobs:
        day = (job.started_at or now).date().isoformat()
        b = buckets.setdefault(day, {"jobs": 0, "filament_g": 0.0, "duration_h": 0.0, "energy_kwh": 0.0})
        b["jobs"] += 1
        b["filament_g"] += job.filament_used_g or 0.0
        duration_h = _job_duration_hours(job, now)
        b["duration_h"] += duration_h
        exact, est = _energy_for_job(job, printers, now)
        b["energy_kwh"] += exact + est

    data = [
        {
            "date": day,
            "jobs": int(vals["jobs"]),
            "filament_g": round(vals["filament_g"], 2),
            "duration_h": round(vals["duration_h"], 2),
            "energy_kwh": round(vals["energy_kwh"], 3),
        }
        for day, vals in sorted(buckets.items())
    ]
    return {"days": days, "data": data}


@router.get("/timeline-by-material")
def timeline_by_material(days: int = 30, session: Session = Depends(get_session)):
    """Timeline gruppiert nach Material-Typ"""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    jobs = session.exec(select(Job).where(Job.started_at >= since)).all()
    spools = {s.id: s for s in session.exec(select(Spool)).all()}
    materials = {m.id: m for m in session.exec(select(Material)).all()}

    # Structure: buckets[date][material_name] = weight_g
    buckets: Dict[str, Dict[str, float]] = {}
    material_names = set()

    for job in jobs:
        day = (job.started_at or now).date().isoformat()
        # Try to get material from spool_id
        material_name = "Unbekannt"
        if job.spool_id:
            spool = spools.get(job.spool_id)
            if spool and spool.material_id:
                mat = materials.get(spool.material_id)
                if mat:
                    material_name = mat.name
        
        material_names.add(material_name)
        b = buckets.setdefault(day, {})
        b[material_name] = b.get(material_name, 0.0) + (job.filament_used_g or 0.0)

    # Build dataset structure for Chart.js
    dates = sorted(buckets.keys())
    datasets = {}
    for mat_name in sorted(material_names):
        datasets[mat_name] = [buckets[d].get(mat_name, 0.0) for d in dates]

    return {
        "days": days,
        "dates": dates,
        "datasets": [{"material": k, "data": v} for k, v in datasets.items()]
    }


@router.get("/timeline-costs")
def timeline_costs(days: int = 30, session: Session = Depends(get_session)):
    """Kosten-Entwicklung über Zeit"""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    jobs = session.exec(select(Job).where(Job.started_at >= since)).all()
    printers = {p.id: p for p in session.exec(select(Printer)).all()}
    price_setting = session.exec(select(Setting).where(Setting.key == "cost.electricity_price_kwh")).first()
    price_kwh = float(price_setting.value) if price_setting and price_setting.value else 0.30

    buckets: Dict[str, float] = {}
    cumulative_cost = 0.0
    daily_cumulative: Dict[str, float] = {}

    for job in sorted(jobs, key=lambda j: j.started_at or now):
        day = (job.started_at or now).date().isoformat()
        exact, est = _energy_for_job(job, printers, now)
        energy_kwh = exact + est
        cost = energy_kwh * price_kwh
        buckets[day] = buckets.get(day, 0.0) + cost
        cumulative_cost += cost
        daily_cumulative[day] = cumulative_cost

    dates = sorted(buckets.keys())
    return {
        "days": days,
        "dates": dates,
        "daily_cost": [round(buckets[d], 2) for d in dates],
        "cumulative_cost": [round(daily_cumulative[d], 2) for d in dates],
    }


@router.get("/heatmap")
def heatmap(days: int = 90, session: Session = Depends(get_session)):
    """Heatmap-Daten für Druckaktivität"""
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    jobs = session.exec(select(Job).where(Job.started_at >= since)).all()

    activity: Dict[str, Dict[str, Any]] = {}
    for job in jobs:
        day = (job.started_at or now).date().isoformat()
        a = activity.setdefault(day, {"jobs": 0, "filament_g": 0.0, "duration_h": 0.0})
        a["jobs"] += 1
        a["filament_g"] += job.filament_used_g or 0.0
        duration_h = _job_duration_hours(job, now)
        a["duration_h"] += duration_h

    # Generate all dates in range
    all_dates = []
    for i in range(days):
        date = (now - timedelta(days=days - i - 1)).date()
        all_dates.append(date.isoformat())

    result = []
    for date in all_dates:
        data = activity.get(date, {"jobs": 0, "filament_g": 0.0, "duration_h": 0.0})
        result.append({
            "date": date,
            "jobs": data["jobs"],
            "filament_g": round(data["filament_g"], 1),
            "duration_h": round(data["duration_h"], 2),
        })

    return {"days": days, "data": result}


@router.get("/by-printer")
def by_printer(session: Session = Depends(get_session)):
    now = datetime.utcnow()
    jobs = session.exec(select(Job)).all()
    printers = {p.id: p for p in session.exec(select(Printer)).all()}

    agg: Dict[str, Dict[str, Any]] = {}
    for job in jobs:
        pid = job.printer_id
        if not pid:
            continue
        printer = printers.get(pid)
        b = agg.setdefault(pid, {
            "printer_id": pid,
            "printer_name": printer.name if printer else "Unbekannt",
            "jobs": 0,
            "filament_g": 0.0,
            "duration_h": 0.0,
            "energy_kwh": 0.0,
        })
        b["jobs"] += 1
        b["filament_g"] += job.filament_used_g or 0.0
        duration_h = _job_duration_hours(job, now)
        b["duration_h"] += duration_h
        exact, est = _energy_for_job(job, printers, now)
        b["energy_kwh"] += exact + est

    return list(agg.values())


@router.get("/by-material")
def by_material(session: Session = Depends(get_session)):
    materials = {m.id: m for m in session.exec(select(Material)).all()}
    spools = {s.id: s for s in session.exec(select(Spool)).all()}
    jobs = session.exec(select(Job)).all()

    agg: Dict[str, Dict[str, Any]] = {}
    
    # Aggregate from jobs (actual usage)
    for job in jobs:
        if not job.spool_id:
            continue
        spool = spools.get(job.spool_id)
        if not spool or not spool.material_id:
            continue
        mid = spool.material_id
        mat = materials.get(mid)
        b = agg.setdefault(mid, {
            "material_id": mid,
            "material_name": mat.name if mat else "Unbekannt",
            "brand": mat.brand if mat else None,
            "color": getattr(mat, "color", None),
            "spools": 0,
            "total_weight_g": 0.0,
        })
        b["total_weight_g"] += job.filament_used_g or 0.0
    
    # Count unique spools per material
    spool_counts: Dict[str, set] = {}
    for spool in spools.values():
        if spool.material_id:
            spool_counts.setdefault(spool.material_id, set()).add(spool.id)
    
    for mid, b in agg.items():
        b["spools"] = len(spool_counts.get(mid, set()))

    return list(agg.values())


@router.get("/costs")
def costs(session: Session = Depends(get_session)):
    now = datetime.utcnow()
    jobs = session.exec(select(Job)).all()
    printers = {p.id: p for p in session.exec(select(Printer)).all()}
    price_setting = session.exec(select(Setting).where(Setting.key == "cost.electricity_price_kwh")).first()
    price_kwh = float(price_setting.value) if price_setting and price_setting.value else None

    energy_total = 0.0
    for job in jobs:
        exact, est = _energy_for_job(job, printers, now)
        energy_total += exact + est

    energy_cost = energy_total * price_kwh if price_kwh is not None else None
    return {
        "energy_kwh_total": round(energy_total, 3),
        "energy_cost_total": round(energy_cost, 2) if energy_cost is not None else None,
        "energy_price_kwh": price_kwh,
    }
