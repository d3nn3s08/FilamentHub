"""
Mini-Tests für JobTrackingService

Testet:
- Start → Update → Finish Lifecycle
- Slot-Wechsel während Druck
- Verbrauchsberechnung
"""

import pytest
from datetime import datetime
from sqlmodel import Session, select
from app.database import engine
from app.models.job import Job
from app.models.spool import Spool
from app.models.material import Material
from app.models.printer import Printer
from app.services.job_tracking_service import JobTrackingService


@pytest.fixture
def service():
    """Neuer Service für jeden Test"""
    return JobTrackingService()


@pytest.fixture
def test_printer():
    """Test-Drucker anlegen"""
    with Session(engine) as session:
        printer = Printer(
            name="Test X1C",
            printer_type="bambu",
            cloud_serial="01S00TEST123",
            ip_address="192.168.1.100"
        )
        session.add(printer)
        session.commit()
        session.refresh(printer)
        yield printer
        # Cleanup
        session.delete(printer)
        session.commit()


@pytest.fixture
def test_material():
    """Test-Material anlegen"""
    with Session(engine) as session:
        material = Material(
            name="PLA Test",
            brand="Bambu Lab",
            color="#FF0000",
            density=1.24,
            diameter=1.75
        )
        session.add(material)
        session.commit()
        session.refresh(material)
        yield material
        # Cleanup
        session.delete(material)
        session.commit()


@pytest.fixture
def test_spool(test_printer, test_material):
    """Test-Spule anlegen"""
    with Session(engine) as session:
        spool = Spool(
            material_id=test_material.id,
            printer_id=test_printer.id,
            ams_slot=0,
            weight_full=1000.0,
            weight_empty=200.0,
            weight_current=1000.0,
            remain_percent=100.0
        )
        session.add(spool)
        session.commit()
        session.refresh(spool)
        yield spool
        # Cleanup
        session.delete(spool)
        session.commit()


def test_job_start(service, test_printer, test_spool):
    """Test 1: Job Start erkennt PRINTING State und legt Job an"""
    payload = {
        "print": {
            "gcode_state": "PRINTING",
            "subtask_name": "test_model.3mf",
            "ams": {
                "tray_now": 0,
                "tray_tar": 0
            }
        }
    }

    ams_data = [{
        "trays": [{
            "tray_id": 0,
            "remain": 100,
            "total_len": 100000
        }]
    }]

    result = service.process_message(
        cloud_serial="01S00TEST123",
        parsed_payload=payload,
        printer_id=test_printer.id,
        ams_data=ams_data
    )

    assert result is not None
    assert result["status"] == "started"
    assert "01S00TEST123" in service.active_jobs

    # Prüfe DB
    with Session(engine) as session:
        job = session.get(Job, result["job_id"])
        assert job is not None
        assert job.status == "running"
        assert job.name == "test_model.3mf"
        assert job.spool_id == test_spool.id
        # Cleanup
        session.delete(job)
        session.commit()


def test_job_update_verbrauch(service, test_printer, test_spool):
    """Test 2: Job Update berechnet Verbrauch korrekt"""
    # Start Job
    start_payload = {
        "print": {
            "gcode_state": "PRINTING",
            "subtask_name": "verbrauch_test.3mf",
            "ams": {"tray_now": 0, "tray_tar": 0}
        }
    }

    ams_start = [{
        "trays": [{
            "tray_id": 0,
            "remain": 100,
            "total_len": 100000
        }]
    }]

    result = service.process_message(
        cloud_serial="01S00TEST123",
        parsed_payload=start_payload,
        printer_id=test_printer.id,
        ams_data=ams_start
    )
    job_id = result["job_id"]

    # Update: Verbrauch von 100% → 80% (20% verbraucht)
    update_payload = {
        "print": {
            "gcode_state": "PRINTING",
            "ams": {"tray_now": 0, "tray_tar": 0}
        }
    }

    ams_update = [{
        "trays": [{
            "tray_id": 0,
            "remain": 80,
            "total_len": 100000
        }]
    }]

    result = service.process_message(
        cloud_serial="01S00TEST123",
        parsed_payload=update_payload,
        printer_id=test_printer.id,
        ams_data=ams_update
    )

    assert result["status"] == "updated"
    assert result["used_g"] > 0  # Verbrauch sollte berechnet sein

    # Cleanup
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job:
            session.delete(job)
            session.commit()


def test_job_finish(service, test_printer, test_spool):
    """Test 3: Job Finish finalisiert Verbrauch und Status"""
    # Start
    start_payload = {
        "print": {
            "gcode_state": "PRINTING",
            "subtask_name": "finish_test.3mf",
            "ams": {"tray_now": 0, "tray_tar": 0}
        }
    }

    ams_data = [{
        "trays": [{
            "tray_id": 0,
            "remain": 100,
            "total_len": 100000
        }]
    }]

    result = service.process_message(
        cloud_serial="01S00TEST123",
        parsed_payload=start_payload,
        printer_id=test_printer.id,
        ams_data=ams_data
    )
    job_id = result["job_id"]

    # Finish: State FINISH mit Verbrauch
    finish_payload = {
        "print": {
            "gcode_state": "FINISH",
            "ams": {"tray_now": 0, "tray_tar": 0}
        }
    }

    ams_finish = [{
        "trays": [{
            "tray_id": 0,
            "remain": 75,  # 25% verbraucht
            "total_len": 100000
        }]
    }]

    result = service.process_message(
        cloud_serial="01S00TEST123",
        parsed_payload=finish_payload,
        printer_id=test_printer.id,
        ams_data=ams_finish
    )

    assert result["status"] == "completed"
    assert result["used_g"] > 0
    assert "01S00TEST123" not in service.active_jobs  # RAM cleanup

    # Prüfe DB
    with Session(engine) as session:
        job = session.get(Job, job_id)
        assert job.status == "completed"
        assert job.finished_at is not None
        assert job.filament_used_g > 0
        # Cleanup
        session.delete(job)
        session.commit()


def test_slot_wechsel(service, test_printer, test_material):
    """Test 4: Slot-Wechsel erzeugt Multi-Spool Tracking"""
    with Session(engine) as session:
        # Spule Slot 0
        spool0 = Spool(
            material_id=test_material.id,
            printer_id=test_printer.id,
            ams_slot=0,
            weight_full=1000.0,
            weight_empty=200.0,
            remain_percent=100.0
        )
        # Spule Slot 1
        spool1 = Spool(
            material_id=test_material.id,
            printer_id=test_printer.id,
            ams_slot=1,
            weight_full=1000.0,
            weight_empty=200.0,
            remain_percent=100.0
        )
        session.add(spool0)
        session.add(spool1)
        session.commit()
        session.refresh(spool0)
        session.refresh(spool1)

        try:
            # Start mit Slot 0
            start_payload = {
                "print": {
                    "gcode_state": "PRINTING",
                    "subtask_name": "multi_color.3mf",
                    "ams": {"tray_now": 0, "tray_tar": 0}
                }
            }

            ams_start = [{
                "trays": [
                    {"tray_id": 0, "remain": 100, "total_len": 100000},
                    {"tray_id": 1, "remain": 100, "total_len": 100000}
                ]
            }]

            result = service.process_message(
                cloud_serial="01S00TEST123",
                parsed_payload=start_payload,
                printer_id=test_printer.id,
                ams_data=ams_start
            )
            job_id = result["job_id"]

            # Wechsel zu Slot 1
            switch_payload = {
                "print": {
                    "gcode_state": "PRINTING",
                    "ams": {"tray_now": 1, "tray_tar": 1}
                }
            }

            ams_switch = [{
                "trays": [
                    {"tray_id": 0, "remain": 80, "total_len": 100000},  # 20% verbraucht
                    {"tray_id": 1, "remain": 100, "total_len": 100000}
                ]
            }]

            result = service.process_message(
                cloud_serial="01S00TEST123",
                parsed_payload=switch_payload,
                printer_id=test_printer.id,
                ams_data=ams_switch
            )

            # Prüfe Multi-Spool Info im RAM
            job_info = service.active_jobs.get("01S00TEST123")
            assert job_info is not None
            assert len(job_info["usages"]) == 1  # Ein finalisierter Slot
            assert job_info["slot"] == 1  # Aktueller Slot

            # Finish
            finish_payload = {
                "print": {
                    "gcode_state": "FINISH",
                    "ams": {"tray_now": 1, "tray_tar": 1}
                }
            }

            ams_finish = [{
                "trays": [
                    {"tray_id": 0, "remain": 80, "total_len": 100000},
                    {"tray_id": 1, "remain": 90, "total_len": 100000}  # 10% verbraucht
                ]
            }]

            result = service.process_message(
                cloud_serial="01S00TEST123",
                parsed_payload=finish_payload,
                printer_id=test_printer.id,
                ams_data=ams_finish
            )

            assert result["status"] == "completed"

            # Cleanup Job
            job = session.get(Job, job_id)
            if job:
                session.delete(job)
                session.commit()

        finally:
            # Cleanup Spools
            session.delete(spool0)
            session.delete(spool1)
            session.commit()


def test_cancelled_job(service, test_printer, test_spool):
    """Test 5: Job Cancel setzt korrekten Status"""
    # Start
    start_payload = {
        "print": {
            "gcode_state": "PRINTING",
            "subtask_name": "cancelled_test.3mf",
            "ams": {"tray_now": 0, "tray_tar": 0}
        }
    }

    ams_data = [{
        "trays": [{
            "tray_id": 0,
            "remain": 100,
            "total_len": 100000
        }]
    }]

    result = service.process_message(
        cloud_serial="01S00TEST123",
        parsed_payload=start_payload,
        printer_id=test_printer.id,
        ams_data=ams_data
    )
    job_id = result["job_id"]

    # Cancel
    cancel_payload = {
        "print": {
            "gcode_state": "CANCELLED",
            "ams": {"tray_now": 0, "tray_tar": 0}
        }
    }

    result = service.process_message(
        cloud_serial="01S00TEST123",
        parsed_payload=cancel_payload,
        printer_id=test_printer.id,
        ams_data=ams_data
    )

    assert result["status"] == "cancelled"

    # Cleanup
    with Session(engine) as session:
        job = session.get(Job, job_id)
        assert job.status == "cancelled"
        session.delete(job)
        session.commit()


def test_error_states_mapping(service, test_printer, test_spool):
    """Test 6: Error-State-Mapping für alle Bambu-Zustände"""
    test_cases = [
        ("FAILED", "failed"),
        ("ERROR", "error"),
        ("EXCEPTION", "exception"),
        ("ABORT", "aborted"),
        ("ABORTED", "aborted"),
        ("STOPPED", "stopped"),
        ("CANCELLED", "cancelled"),
        ("CANCELED", "cancelled"),
    ]

    for gcode_state, expected_status in test_cases:
        # Start Job
        start_payload = {
            "print": {
                "gcode_state": "PRINTING",
                "subtask_name": f"test_{gcode_state}.3mf",
                "ams": {"tray_now": 0, "tray_tar": 0}
            }
        }

        ams_data = [{
            "trays": [{
                "tray_id": 0,
                "remain": 100,
                "total_len": 100000
            }]
        }]

        result = service.process_message(
            cloud_serial="01S00TEST123",
            parsed_payload=start_payload,
            printer_id=test_printer.id,
            ams_data=ams_data
        )
        job_id = result["job_id"]

        # End mit Error State
        end_payload = {
            "print": {
                "gcode_state": gcode_state,
                "ams": {"tray_now": 0, "tray_tar": 0}
            }
        }

        result = service.process_message(
            cloud_serial="01S00TEST123",
            parsed_payload=end_payload,
            printer_id=test_printer.id,
            ams_data=ams_data
        )

        assert result["status"] == expected_status, f"State {gcode_state} sollte {expected_status} ergeben"

        # Cleanup
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                session.delete(job)
                session.commit()


def test_verbrauch_berechnung(service, test_printer, test_material):
    """Test 7: Verbrauchsberechnung mm + g ist korrekt"""
    with Session(engine) as session:
        spool = Spool(
            material_id=test_material.id,
            printer_id=test_printer.id,
            ams_slot=0,
            weight_full=1000.0,  # 1kg voll
            weight_empty=200.0,   # 200g leer = 800g Filament
            remain_percent=100.0
        )
        session.add(spool)
        session.commit()
        session.refresh(spool)

        try:
            # Start bei 100%
            start_payload = {
                "print": {
                    "gcode_state": "PRINTING",
                    "subtask_name": "calc_test.3mf",
                    "ams": {"tray_now": 0, "tray_tar": 0}
                }
            }

            ams_start = [{
                "trays": [{
                    "tray_id": 0,
                    "remain": 100,
                    "total_len": 100000  # 100m
                }]
            }]

            result = service.process_message(
                cloud_serial="01S00TEST123",
                parsed_payload=start_payload,
                printer_id=test_printer.id,
                ams_data=ams_start
            )
            job_id = result["job_id"]

            # Finish bei 75% = 25% verbraucht
            finish_payload = {
                "print": {
                    "gcode_state": "FINISH",
                    "ams": {"tray_now": 0, "tray_tar": 0}
                }
            }

            ams_finish = [{
                "trays": [{
                    "tray_id": 0,
                    "remain": 75,  # 25% verbraucht
                    "total_len": 100000
                }]
            }]

            result = service.process_message(
                cloud_serial="01S00TEST123",
                parsed_payload=finish_payload,
                printer_id=test_printer.id,
                ams_data=ams_finish
            )

            # Erwartung:
            # 25% von 100000mm = 25000mm
            # 25% von 800g = 200g
            job = session.get(Job, job_id)
            assert job.filament_used_mm == pytest.approx(25000, abs=10)
            assert job.filament_used_g == pytest.approx(200, abs=5)

            # Cleanup
            session.delete(job)
            session.commit()

        finally:
            session.delete(spool)
            session.commit()
