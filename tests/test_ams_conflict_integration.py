from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
import services.bambu_service as bambu_service_mod
from services.bambu_service import BambuService
from app.models.spool import Spool
from app.models.ams_conflict import AmsConflict
from app.routes import ams_conflicts as ams_conflicts_route
from app.main import app


def setup_in_memory_db():
    # Use a shared in-memory SQLite that works across threads/connections
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def get_session_for_engine(engine):
    def _gen():
        with Session(engine) as session:
            yield session
    return _gen


def test_conflict_creation_and_cancel_and_confirm():
    engine = setup_in_memory_db()

    # prepare session and data
    with Session(engine) as session:
        manual = Spool(material_id="m1", ams_id="AMS1", ams_slot=2, ams_source="manual", assigned=True, is_active=True)
        rfid = Spool(material_id="m1")
        session.add(manual)
        session.add(rfid)
        session.commit()
        session.refresh(manual)
        session.refresh(rfid)
        manual_id = manual.id
        rfid_id = rfid.id

    # Monkeypatch get_session used in bambu_service and route module to use in-memory engine
    bambu_service_mod.get_session = get_session_for_engine(engine)
    ams_conflicts_route.get_session = get_session_for_engine(engine)

    # Call BambuService._sync_spool which should detect manual existing spool and create conflict
    svc = BambuService(printer_id="P1", host="h", access_code="a", serial="s")
    # call internal method
    svc._sync_spool(ams_id=1, ams_slot=2, rfid="SOME_RFID", material_type="PLA", color="#fff", remaining_weight=100.0, tray_payload={"tray_uuid":"SOME_RFID"})

    # Verify conflict created
    from sqlmodel import select
    with Session(engine) as session:
        conflicts = session.exec(select(AmsConflict)).all()
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.manual_spool_id == manual_id
        assert conflict.slot == 2

    client = TestClient(app)
    # Monkeypatch route's get_session inside app.routes.ams_conflicts already done

    # Cancel conflict
    res = client.post('/api/ams/conflict/cancel', json={"ams_id":"AMS1","slot":2})
    assert res.status_code == 200

    with Session(engine) as session:
        c = session.exec(select(AmsConflict)).first()
        assert c is not None
        assert c.status == 'cancelled'

    # Create another conflict for confirm path (clean previous conflicts first)
    from sqlmodel import delete
    with Session(engine) as session:
        session.exec(delete(AmsConflict))
        session.commit()
        conflict = AmsConflict(ams_id="AMS1", slot=2, manual_spool_id=manual_id, rfid_payload="{}")
        session.add(conflict)
        session.commit()

    res2 = client.post('/api/ams/conflict/confirm', json={
        "ams_id":"AMS1",
        "slot":2,
        "manual_spool_id":manual_id,
        "rfid_spool_id":rfid_id
    })
    assert res2.status_code == 200

    # verify manual cleared and rfid assigned
    with Session(engine) as session:
        m = session.get(Spool, manual_id)
        r = session.get(Spool, rfid_id)
        assert m is not None
        assert r is not None
        assert m.ams_id is None
        assert m.assigned is False
        assert r.ams_id == "AMS1"
        assert r.ams_slot == 2
        assert r.ams_source == "rfid"
        # conflict marked confirmed
        c = session.exec(select(AmsConflict).where(AmsConflict.slot==2)).first()
        assert c is not None
        assert c.status == 'confirmed'
