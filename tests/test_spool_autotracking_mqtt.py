import json

from sqlmodel import select, delete

from app.models.material import Material
from app.models.spool import Spool
from app.routes import mqtt_routes


class _FakeMsg:
    def __init__(self, topic: str, payload: str, qos: int = 0):
        self.topic = topic
        self.payload = payload.encode("utf-8")
        self.qos = qos


def _emit_mqtt_payload(payload: dict) -> None:
    msg = _FakeMsg("device/TESTSERIAL/report", json.dumps(payload))
    mqtt_routes.on_message(None, {}, msg)


def test_mqtt_autotracking_creates_material_and_spool(db_session):
    # Arrange
    db_session.exec(delete(Spool))
    db_session.exec(delete(Material))
    db_session.commit()
    payload = {
        "print": {
            "ams": {
                "ams": [
                    {
                        "tray": [
                            {
                                "tray_id": 1,
                                "tray_type": "PLA",
                                "tray_color": "FF0000",
                                "remain_percent": 75,
                                "tag_uid": "TAG-001",
                            }
                        ]
                    }
                ]
            }
        }
    }

    # Act
    _emit_mqtt_payload(payload)

    # Assert
    materials = db_session.exec(select(Material)).all()
    spools = db_session.exec(select(Spool)).all()
    assert len(materials) == 1
    assert len(spools) == 1
    assert spools[0].material_id == materials[0].id
    assert materials[0].name == "PLA"
    assert spools[0].label == "AMS Slot 1"
    assert spools[0].remain_percent == 75.0


def test_mqtt_autotracking_does_not_duplicate_material(db_session):
    # Arrange
    db_session.exec(delete(Spool))
    db_session.exec(delete(Material))
    db_session.commit()
    payload = {
        "print": {
            "ams": {
                "ams": [
                    {
                        "tray": [
                            {
                                "tray_id": 1,
                                "tray_type": "PLA",
                                "tray_color": "FF0000",
                                "remain_percent": 75,
                                "tag_uid": "TAG-001",
                            }
                        ]
                    }
                ]
            }
        }
    }

    # Act
    _emit_mqtt_payload(payload)
    _emit_mqtt_payload(payload)

    # Assert
    materials = db_session.exec(select(Material)).all()
    spools = db_session.exec(select(Spool)).all()
    assert len(materials) == 1
    assert len(spools) == 1
