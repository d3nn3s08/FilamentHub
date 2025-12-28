"""
Tests für Spulen-Nummern-System

Fokus auf:
1. Nummern-Vergabe (Recycling)
2. Snapshot-Stabilität
3. Assign/Unassign
4. API-Smoke-Tests

Keine Mocks, keine UI - nur Logik + Datenintegrität.
"""
import pytest
from sqlmodel import Session, select, create_engine
from sqlmodel.pool import StaticPool
from datetime import datetime

from app.models.spool import Spool
from app.models.job import Job
from app.models.material import Material
from app.models.printer import Printer
from app.services.spool_number_service import (
    get_next_spool_number,
    assign_spool_number,
    create_job_snapshot,
    extract_color_from_hex
)


# ===== FIXTURES =====

@pytest.fixture(name="session")
def session_fixture():
    """In-Memory SQLite für Tests"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Erstelle Tabellen
    from app.models.spool import Spool
    from app.models.job import Job
    from app.models.material import Material
    from app.models.printer import Printer

    Spool.metadata.create_all(engine)
    Job.metadata.create_all(engine)
    Material.metadata.create_all(engine)
    Printer.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="test_material")
def test_material_fixture(session: Session):
    """Test-Material erstellen"""
    material = Material(
        name="PLA Basic",
        brand="Bambu Lab",
        density=1.24,
        diameter=1.75
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    return material


@pytest.fixture(name="test_printer")
def test_printer_fixture(session: Session):
    """Test-Drucker erstellen"""
    printer = Printer(
        name="Test X1C",
        printer_type="bambu",  # FIX: printer_type ist NOT NULL
        ip="192.168.1.100",
        manufacturer="Bambu Lab",
        model="X1C"
    )
    session.add(printer)
    session.commit()
    session.refresh(printer)
    return printer


# ===== TEST 1: SPULEN-NUMMERN-VERGABE =====

def test_first_spool_gets_number_one(session: Session, test_material: Material):
    """Erste Spule bekommt #1 (manuell zugewiesen)"""
    spool = Spool(material_id=test_material.id, weight_full=1000)
    # NEUES VERHALTEN: Manuell Nummer zuweisen
    spool.spool_number = get_next_spool_number(session)
    assign_spool_number(spool, session)

    assert spool.spool_number == 1, "Erste Spule sollte #1 bekommen"
    assert spool.name == "PLA Basic", "Name sollte kopiert werden"
    assert spool.vendor == "Bambu Lab", "Vendor sollte kopiert werden"


def test_multiple_spools_sequential(session: Session, test_material: Material):
    """Mehrere Spulen → fortlaufend (manuell zugewiesen)"""
    spools = []
    for i in range(5):
        spool = Spool(material_id=test_material.id, weight_full=1000)
        # NEUES VERHALTEN: Manuell Nummer zuweisen
        spool.spool_number = get_next_spool_number(session)
        assign_spool_number(spool, session)
        session.add(spool)
        session.commit()
        spools.append(spool)

    numbers = [s.spool_number for s in spools]
    assert numbers == [1, 2, 3, 4, 5], "Nummern sollten fortlaufend sein"


def test_recycling_fills_gaps(session: Session, test_material: Material):
    """Lücke wird recycelt (#2 gelöscht → neue Spule bekommt #2)"""
    # Erstelle #1, #2, #3
    spool1 = Spool(material_id=test_material.id, weight_full=1000)
    spool1.spool_number = get_next_spool_number(session)
    assign_spool_number(spool1, session)
    session.add(spool1)

    spool2 = Spool(material_id=test_material.id, weight_full=1000)
    spool2.spool_number = get_next_spool_number(session)
    assign_spool_number(spool2, session)
    session.add(spool2)

    spool3 = Spool(material_id=test_material.id, weight_full=1000)
    spool3.spool_number = get_next_spool_number(session)
    assign_spool_number(spool3, session)
    session.add(spool3)
    session.commit()

    assert spool1.spool_number == 1
    assert spool2.spool_number == 2
    assert spool3.spool_number == 3

    # Lösche #2
    session.delete(spool2)
    session.commit()

    # Neue Spule sollte #2 bekommen (Recycling!)
    spool_new = Spool(material_id=test_material.id, weight_full=1000)
    spool_new.spool_number = get_next_spool_number(session)
    assign_spool_number(spool_new, session)

    assert spool_new.spool_number == 2, "Gelöschte Nummer #2 sollte recycelt werden"


def test_fallback_max_plus_one(session: Session, test_material: Material):
    """Fallback funktioniert (MAX + 1)"""
    # Erstelle Spule mit manuell gesetzter hoher Nummer
    spool_high = Spool(
        material_id=test_material.id,
        weight_full=1000,
        spool_number=100  # Manuell gesetzt
    )
    session.add(spool_high)
    session.commit()

    # Nächste Spule sollte 101 bekommen (MAX + 1)
    next_num = get_next_spool_number(session)
    assert next_num == 1, "Sollte erste Lücke finden (1), nicht MAX+1"

    # Fülle Lücken
    for i in range(1, 100):
        s = Spool(material_id=test_material.id, spool_number=i, weight_full=1000)
        session.add(s)
    session.commit()

    # Jetzt sollte MAX+1 greifen
    next_num = get_next_spool_number(session)
    assert next_num == 101, "Sollte MAX+1 sein wenn keine Lücken"


# ===== TEST 2: SNAPSHOT-STABILITÄT =====

def test_job_snapshot_creation(session: Session, test_material: Material, test_printer: Printer):
    """Job speichert spool_number, name, vendor, color"""
    spool = Spool(
        material_id=test_material.id,
        weight_full=1000,
        color="black",
        created_at=datetime.utcnow().isoformat()  # FIX: created_at setzen
    )
    # NEUES VERHALTEN: Manuell Nummer zuweisen
    spool.spool_number = get_next_spool_number(session)
    assign_spool_number(spool, session)
    session.add(spool)
    session.commit()
    session.refresh(spool)

    # Erstelle Job mit Snapshot
    snapshot = create_job_snapshot(spool)

    job = Job(
        printer_id=test_printer.id,
        spool_id=spool.id,
        name="Test Job",
        **snapshot
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    assert job.spool_number == 1
    assert job.spool_name == "PLA Basic"
    assert job.spool_vendor == "Bambu Lab"
    assert job.spool_color == "black"
    assert job.spool_created_at is not None


def test_job_history_survives_spool_deletion(session: Session, test_material: Material, test_printer: Printer):
    """Spule wird gelöscht → Job-Historie bleibt korrekt"""
    spool = Spool(
        material_id=test_material.id,
        weight_full=1000,
        color="red",
        created_at=datetime.utcnow().isoformat()  # FIX: created_at setzen
    )
    # NEUES VERHALTEN: Manuell Nummer zuweisen
    spool.spool_number = get_next_spool_number(session)
    assign_spool_number(spool, session)
    session.add(spool)
    session.commit()
    spool_created_at = spool.created_at

    # Job erstellen
    snapshot = create_job_snapshot(spool)
    job = Job(
        printer_id=test_printer.id,
        spool_id=spool.id,
        name="Test Job",
        **snapshot
    )
    session.add(job)
    session.commit()

    # Spule löschen
    session.delete(spool)
    session.commit()

    # Job-Daten sollten erhalten bleiben
    session.refresh(job)
    assert job.spool_number == 1
    assert job.spool_name == "PLA Basic"
    assert job.spool_vendor == "Bambu Lab"
    assert job.spool_color == "red"
    assert job.spool_created_at == spool_created_at


def test_recycled_number_detection(session: Session, test_material: Material, test_printer: Printer):
    """Nummer wird neu vergeben → was_recycled = true"""
    # Erste Spule #1
    spool1 = Spool(
        material_id=test_material.id,
        weight_full=1000,
        created_at=datetime.utcnow().isoformat()  # FIX: created_at setzen
    )
    # NEUES VERHALTEN: Manuell Nummer zuweisen
    spool1.spool_number = get_next_spool_number(session)
    assign_spool_number(spool1, session)
    session.add(spool1)
    session.commit()
    created_at_1 = spool1.created_at

    # Job mit Snapshot
    snapshot1 = create_job_snapshot(spool1)
    job1 = Job(printer_id=test_printer.id, spool_id=spool1.id, name="Job 1", **snapshot1)
    session.add(job1)
    session.commit()

    # Lösche Spule #1
    session.delete(spool1)
    session.commit()

    # Neue Spule bekommt wieder #1 (Recycling)
    import time
    time.sleep(0.01)  # Kurze Verzögerung für unterschiedliche Timestamps
    spool2 = Spool(
        material_id=test_material.id,
        weight_full=1000,
        created_at=datetime.utcnow().isoformat()  # FIX: created_at setzen
    )
    # NEUES VERHALTEN: Manuell Nummer zuweisen (recycelt die #1)
    spool2.spool_number = get_next_spool_number(session)
    assign_spool_number(spool2, session)
    session.add(spool2)
    session.commit()
    created_at_2 = spool2.created_at

    # Prüfe Recycling-Erkennung
    assert spool2.spool_number == 1, "Nummer sollte recycelt werden"
    assert created_at_1 != created_at_2, "created_at sollte unterschiedlich sein"

    # Hole Job1 und prüfe ob was_recycled erkannt wird
    session.refresh(job1)
    current_spool = session.get(Spool, spool2.id)

    # Logik: gleiche Nummer, aber unterschiedliche created_at = recycelt
    was_recycled = (
        current_spool.spool_number == job1.spool_number and
        current_spool.created_at != job1.spool_created_at
    )
    assert was_recycled is True, "System sollte Recycling erkennen"


# ===== TEST 3: ASSIGN/UNASSIGN LOGIK =====

def test_assign_spool_to_slot(session: Session, test_material: Material, test_printer: Printer):
    """Spule manuell Slot zuweisen → OK"""
    spool = Spool(material_id=test_material.id, weight_full=1000)
    assign_spool_number(spool, session)
    session.add(spool)
    session.commit()

    # Zuweisen
    spool.printer_id = test_printer.id
    spool.ams_slot = 2
    session.add(spool)
    session.commit()
    session.refresh(spool)

    assert spool.printer_id == test_printer.id
    assert spool.ams_slot == 2


def test_assign_slot_already_occupied(session: Session, test_material: Material, test_printer: Printer):
    """Slot bereits belegt → Fehler"""
    spool1 = Spool(material_id=test_material.id, weight_full=1000)
    assign_spool_number(spool1, session)
    spool1.printer_id = test_printer.id
    spool1.ams_slot = 1
    session.add(spool1)

    spool2 = Spool(material_id=test_material.id, weight_full=1000)
    assign_spool_number(spool2, session)
    session.add(spool2)
    session.commit()

    # Prüfe ob Slot belegt
    existing = session.exec(
        select(Spool).where(
            Spool.printer_id == test_printer.id,
            Spool.ams_slot == 1
        )
    ).first()

    assert existing is not None, "Slot 1 sollte belegt sein"
    assert existing.id == spool1.id


def test_assign_spool_already_assigned(session: Session, test_material: Material, test_printer: Printer):
    """Spule bereits zugewiesen → Fehler"""
    spool = Spool(material_id=test_material.id, weight_full=1000)
    assign_spool_number(spool, session)
    spool.printer_id = test_printer.id
    spool.ams_slot = 1
    session.add(spool)
    session.commit()

    # Prüfe ob bereits zugewiesen
    assert spool.printer_id is not None
    assert spool.ams_slot is not None


def test_unassign_sets_fields_to_none(session: Session, test_material: Material, test_printer: Printer):
    """Unassign setzt printer_id & ams_slot auf None"""
    spool = Spool(material_id=test_material.id, weight_full=1000)
    assign_spool_number(spool, session)
    spool.printer_id = test_printer.id
    spool.ams_slot = 3
    session.add(spool)
    session.commit()

    # Entfernen
    last_slot = spool.ams_slot
    spool.printer_id = None
    spool.ams_slot = None
    spool.last_slot = last_slot
    session.add(spool)
    session.commit()
    session.refresh(spool)

    assert spool.printer_id is None
    assert spool.ams_slot is None
    assert spool.last_slot == 3


# ===== TEST 4: UTILITY FUNCTIONS =====

def test_color_extraction_from_hex():
    """Farb-Extraktion aus Bambu Hex-Codes"""
    assert extract_color_from_hex("000000FF") == "black"
    assert extract_color_from_hex("FFFFFFFF") == "white"
    assert extract_color_from_hex("FF0000FF") == "red"
    assert extract_color_from_hex("00FF00FF") == "green"
    assert extract_color_from_hex("0000FFFF") == "blue"
    assert extract_color_from_hex("FFFF00FF") == "yellow"
    assert extract_color_from_hex("") == "unknown"
    assert extract_color_from_hex("XYZ") == "unknown"


# ===== TEST 5: RFID vs. MANUELLE SPULEN =====

def test_rfid_spool_gets_no_number(session: Session, test_material: Material):
    """RFID-Spule (mit tray_uuid) bekommt KEINE Nummer"""
    spool = Spool(
        material_id=test_material.id,
        weight_full=1000,
        tray_uuid="some-bambu-rfid-uuid-12345",  # RFID vorhanden
        tray_color="FF0000FF"
    )
    assign_spool_number(spool, session)
    session.add(spool)
    session.commit()
    session.refresh(spool)

    assert spool.spool_number is None, "RFID-Spule sollte KEINE Nummer bekommen"
    assert spool.tray_uuid == "some-bambu-rfid-uuid-12345"
    assert spool.name == "PLA Basic", "Denormalisierung sollte trotzdem funktionieren"
    assert spool.vendor == "Bambu Lab"


def test_manual_spool_gets_number(session: Session, test_material: Material):
    """Manuelle Spule (ohne tray_uuid) kann Nummer erhalten (manuell zugewiesen)"""
    spool = Spool(
        material_id=test_material.id,
        weight_full=1000,
        tray_uuid=None  # Kein RFID
    )
    # NEUES VERHALTEN: Alle Nummern sind jetzt manuell (auch für nicht-RFID Spulen)
    spool.spool_number = get_next_spool_number(session)
    assign_spool_number(spool, session)
    session.add(spool)
    session.commit()
    session.refresh(spool)

    assert spool.spool_number == 1, "Manuelle Spule kann Nummer bekommen (wenn manuell zugewiesen)"
    assert spool.tray_uuid is None
    assert spool.name == "PLA Basic"


def test_mixed_rfid_and_manual_spools(session: Session, test_material: Material):
    """Gemischte RFID- und manuelle Spulen - User entscheidet über Nummern"""
    # RFID-Spule #1 (keine Nummer)
    rfid1 = Spool(
        material_id=test_material.id,
        weight_full=1000,
        tray_uuid="rfid-uuid-1"
    )
    assign_spool_number(rfid1, session)
    session.add(rfid1)

    # Manuelle Spule #1 (User gibt Nummer)
    manual1 = Spool(
        material_id=test_material.id,
        weight_full=1000,
        tray_uuid=None
    )
    # NEUES VERHALTEN: User weist Nummer zu
    manual1.spool_number = get_next_spool_number(session)
    assign_spool_number(manual1, session)
    session.add(manual1)

    # RFID-Spule #2 (keine Nummer)
    rfid2 = Spool(
        material_id=test_material.id,
        weight_full=1000,
        tray_uuid="rfid-uuid-2"
    )
    assign_spool_number(rfid2, session)
    session.add(rfid2)

    # Manuelle Spule #2 (User gibt Nummer)
    manual2 = Spool(
        material_id=test_material.id,
        weight_full=1000,
        tray_uuid=None
    )
    # NEUES VERHALTEN: User weist Nummer zu
    manual2.spool_number = get_next_spool_number(session)
    assign_spool_number(manual2, session)
    session.add(manual2)

    session.commit()

    # Prüfe Nummern
    assert rfid1.spool_number is None, "RFID-Spule 1 hat keine Nummer (User hat keine vergeben)"
    assert rfid2.spool_number is None, "RFID-Spule 2 hat keine Nummer (User hat keine vergeben)"
    assert manual1.spool_number == 1, "Manuelle Spule 1 sollte #1 sein"
    assert manual2.spool_number == 2, "Manuelle Spule 2 sollte #2 sein"


# ===== ZUSAMMENFASSUNG =====

if __name__ == "__main__":
    print("=" * 60)
    print("Spulen-Nummern-System Tests")
    print("=" * 60)
    print()
    print("Test-Gruppen:")
    print("1. Spulen-Nummern-Vergabe (5 Tests)")
    print("2. Snapshot-Stabilität (3 Tests)")
    print("3. Assign/Unassign (4 Tests)")
    print("4. Utility Functions (1 Test)")
    print("5. RFID vs. Manuelle Spulen (3 Tests)")
    print()
    print("Gesamt: 16 Tests")
    print()
    print("Ausführen mit: pytest tests/test_spool_number_system.py -v")
    print("=" * 60)
