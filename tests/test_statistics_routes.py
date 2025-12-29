from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.database import engine
from app.main import app
from app.models.job import Job
from app.models.material import Material
from app.models.printer import Printer
from app.models.spool import Spool
from app.models.settings import Setting
from app.routes.statistics_routes import _energy_for_job, _job_duration_hours, DEFAULT_POWER_KW


client = TestClient(app)


@pytest.fixture(scope="module")
def stats_seed():
    now = datetime.utcnow()
    with Session(engine) as session:
        printer = Printer(name="stat-printer", printer_type="bambu", power_consumption_kw=0.5)
        session.add(printer)
        session.commit()
        session.refresh(printer)

        material = Material(name="PLA Gold", brand="Glass")
        session.add(material)
        session.commit()
        session.refresh(material)

        material_name = material.name
        printer_id = printer.id

        spool = Spool(material_id=material.id)
        session.add(spool)
        session.commit()
        session.refresh(spool)

        job = Job(
            printer_id=printer.id,
            spool_id=spool.id,
            filament_used_g=12.5,
            started_at=now - timedelta(hours=2),
            finished_at=now - timedelta(hours=1),
            name="Stats Job",
        )
        session.add(job)
        session.commit()

        session.exec(delete(Setting).where(Setting.key == "cost.electricity_price_kwh"))
        price_setting = Setting(key="cost.electricity_price_kwh", value="0.5")
        session.add(price_setting)
        session.commit()

    return {
        "date": (now - timedelta(hours=2)).date().isoformat(),
        "duration_h": 1.0,
        "energy_kwh": 0.5,
        "material_name": material_name,
        "printer_id": printer_id,
        "price_kwh": 0.5,
    }


def test_timeline(stats_seed):
    resp = client.get("/api/statistics/timeline?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 7
    assert body["data"]
    match = next((day for day in body["data"] if day["date"] == stats_seed["date"]), None)
    assert match is not None
    assert match["jobs"] >= 1
    assert match["filament_g"] >= round(12.5, 2)
    assert match["duration_h"] >= round(stats_seed["duration_h"], 2)
    assert match["energy_kwh"] >= round(stats_seed["energy_kwh"], 3)


def test_timeline_by_material(stats_seed):
    resp = client.get("/api/statistics/timeline-by-material?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 7
    assert stats_seed["material_name"] in [entry["material"] for entry in body["datasets"]]


def test_timeline_costs(stats_seed):
    resp = client.get("/api/statistics/timeline-costs?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["daily_cost"]
    if stats_seed["date"] in body["dates"]:
        idx = body["dates"].index(stats_seed["date"])
        expected = round(stats_seed["energy_kwh"] * stats_seed["price_kwh"], 2)
        assert body["daily_cost"][idx] >= expected
        assert body["cumulative_cost"][idx] >= expected


def test_heatmap_contains_seed_day(stats_seed):
    resp = client.get("/api/statistics/heatmap?days=7")
    assert resp.status_code == 200
    days = resp.json()["data"]
    matching = [entry for entry in days if entry["date"] == stats_seed["date"]]
    assert matching
    assert matching[0]["jobs"] >= 1


def test_by_printer_includes_stats(stats_seed):
    resp = client.get("/api/statistics/by-printer")
    assert resp.status_code == 200
    printers = resp.json()
    assert any(p["printer_id"] == stats_seed["printer_id"] for p in printers)


def test_by_material_reports_filament(stats_seed):
    resp = client.get("/api/statistics/by-material")
    assert resp.status_code == 200
    materials = resp.json()
    assert isinstance(materials, list)
    matching = [item for item in materials if item["material_name"] == stats_seed["material_name"]]
    assert matching
    assert matching[0]["total_weight_g"] == 12.5
    assert matching[0]["spools"] >= 1


def test_costs_endpoint(stats_seed):
    resp = client.get("/api/statistics/costs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["energy_kwh_total"] >= round(stats_seed["energy_kwh"], 3)
    assert body["energy_cost_total"] >= round(stats_seed["energy_kwh"] * stats_seed["price_kwh"], 2)
    assert body["energy_price_kwh"] == stats_seed["price_kwh"]


def test_costs_endpoint_handles_missing_price_setting(stats_seed):
    with Session(engine) as session:
        session.exec(delete(Setting).where(Setting.key == "cost.electricity_price_kwh"))
        session.commit()

    resp = client.get("/api/statistics/costs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["energy_price_kwh"] is None
    assert body["energy_cost_total"] is None

    with Session(engine) as session:
        session.add(Setting(key="cost.electricity_price_kwh", value=str(stats_seed["price_kwh"])))
        session.commit()


def test_timeline_by_material_includes_unknown_material(stats_seed):
    now = datetime.utcnow()
    unknown_job_id = None
    with Session(engine) as session:
        job = Job(
            printer_id=stats_seed["printer_id"],
            spool_id="missing-spool",
            name="Unknown material job",
            filament_used_g=3.3,
            started_at=now - timedelta(minutes=45),
            finished_at=now,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        unknown_job_id = job.id

    resp = client.get("/api/statistics/timeline-by-material?days=1")
    assert resp.status_code == 200
    materials = resp.json()["datasets"]
    assert any(entry["material"] == "Unbekannt" for entry in materials)

    if unknown_job_id:
        with Session(engine) as session:
            session.exec(delete(Job).where(Job.id == unknown_job_id))
            session.commit()


def test_energy_helpers_reflect_printer_power():
    now = datetime.utcnow()
    job = Job(
        printer_id="helper-printer",
        name="helper",
        filament_used_g=0,
        finished_at=now,
        started_at=now - timedelta(hours=2),
    )
    printer = Printer(
        id="helper-printer",
        name="helper",
        printer_type="manual",
        power_consumption_kw=0.4,
    )
    exact, estimated = _energy_for_job(job, {printer.id: printer}, now)
    assert pytest.approx(exact, abs=1e-6) == 0.4 * 2
    assert estimated == 0.0


def test_job_duration_and_default_energy():
    now = datetime.utcnow()
    job = Job(
        printer_id="duration-printer",
        name="duration",
        filament_used_g=0,
        started_at=now - timedelta(hours=1),
        finished_at=None,
    )
    duration = _job_duration_hours(job, now)
    assert pytest.approx(duration, abs=1e-6) == 1.0
    exact, estimated = _energy_for_job(job, {}, now)
    assert exact == 0.0
    assert pytest.approx(estimated, abs=1e-6) == DEFAULT_POWER_KW * duration
