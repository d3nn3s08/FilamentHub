from sqlmodel import SQLModel, create_engine, Session
from app.services.job_tracking_service import JobTrackingService
from app.models.spool import Spool


def test_finalize_current_with_spool():
    # In-memory engine for isolated test
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    # Insert a spool
    spool = Spool(material_id="m1", weight_full=1200.0, weight_empty=200.0)
    with Session(engine) as session:
        session.add(spool)
        session.commit()
        session.refresh(spool)

        svc = JobTrackingService()

        info = {
            "spool_id": spool.id,
            "slot": 1,
            "start_remain": 100.0,
            "last_remain": 95.0,
            "start_total_len": 20000,
        }

        res = svc._finalize_current(session, info)
        assert res is not None
        # 5% of 20000 mm -> 1000 mm
        assert abs(res["used_mm"] - 1000.0) < 1e-6
        # 5% of (1200-200)=1000g -> 50g
        assert abs(res["used_g"] - 50.0) < 1e-6

