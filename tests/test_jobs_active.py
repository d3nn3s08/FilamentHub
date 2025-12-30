from fastapi.testclient import TestClient
from app.main import app
from app.database import get_session, engine
from sqlmodel import Session
from app.models.printer import Printer
from app.models.job import Job
from datetime import datetime
import uuid

client = TestClient(app)


def create_test_printer(session: Session) -> Printer:
    p = Printer(id=str(uuid.uuid4()), name="test-printer", printer_type="manual")
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def create_test_job(session: Session, printer_id: str) -> Job:
    j = Job(printer_id=printer_id, name="test-job", started_at=datetime.utcnow())
    session.add(j)
    session.commit()
    session.refresh(j)
    return j


def test_get_active_jobs_empty():
    # Ensure endpoint returns an array even when no active jobs
    res = client.get("/api/jobs/active")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_get_active_jobs_with_job():
    # Insert temporary printer + job, call endpoint, then cleanup
    with Session(engine) as session:
        printer = create_test_printer(session)
        job = create_test_job(session, printer.id)

        res = client.get("/api/jobs/active")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

        # Find our job in the response
        found = None
        for item in data:
            if item.get("id") == job.id:
                found = item
                break
        assert found is not None, "Created job not present in /api/jobs/active response"

        # progress must be None for active jobs (server-side contract)
        assert ("progress" in found) and (found.get("progress") is None)

        # eta_seconds should be present (may be None)
        assert "eta_seconds" in found

        # Cleanup
        session.delete(job)
        session.delete(printer)
        session.commit()
