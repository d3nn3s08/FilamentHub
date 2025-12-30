from sqlmodel import SQLModel, create_engine, Session
from app.models.spool import Spool
from app.models.ams_conflict import AmsConflict
from services.ams_assignment_service import assign_spool_manual, assign_spool_rfid, remove_spool_from_ams


def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_manual_assign_and_confirm_flow():
    engine = setup_in_memory_db()
    with Session(engine) as session:
        # Create two spools: manual and rfid
        manual = Spool(material_id="mat1")
        rfid = Spool(material_id="mat1")
        session.add(manual)
        session.add(rfid)
        session.commit()
        session.refresh(manual)
        session.refresh(rfid)

        # Manual assign
        assign_spool_manual(manual.id, "AMS_X", 2, session=session)
        session.refresh(manual)
        assert manual.ams_id == "AMS_X"
        assert manual.ams_slot == 2
        assert manual.ams_source == "manual"
        assert manual.assigned is True

        # Simulate user confirmation: remove manual and assign RFID
        remove_spool_from_ams(manual.id, session=session)
        assign_spool_rfid(rfid.id, "AMS_X", 2, session=session)
        session.refresh(manual)
        session.refresh(rfid)

        assert manual.ams_id is None
        assert manual.ams_slot is None
        assert manual.assigned is False

        assert rfid.ams_id == "AMS_X"
        assert rfid.ams_slot == 2
        assert rfid.ams_source == "rfid"
        assert rfid.assigned is True


def test_rfid_assign_on_empty_slot():
    engine = setup_in_memory_db()
    with Session(engine) as session:
        s = Spool(material_id="mat1")
        session.add(s)
        session.commit()
        session.refresh(s)

        assign_spool_rfid(s.id, "AMS_Y", 5, session=session)
        session.refresh(s)
        assert s.ams_id == "AMS_Y"
        assert s.ams_slot == 5
        assert s.ams_source == "rfid"
        assert s.assigned is True
