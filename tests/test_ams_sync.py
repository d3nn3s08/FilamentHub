from app.services.ams_sync import sync_ams_slots
from tests.conftest import DummySpool


def test_sync_normal(fake_session_env):
    spools, _ = fake_session_env
    spools.extend(
        [
            DummySpool(tag_uid="TAG1", remain_percent=5),
            DummySpool(tray_uuid="UUID-A1", remain_percent=10),
        ]
    )

    ams_units = [
        {
            "trays": [
                {"tray_id": 0, "tag_uid": "TAG1", "remain": 30, "tray_type": "PLA"},
                {"tray_id": 1, "tray_uuid": "UUID-A1", "remain_percent": 60},
            ]
        }
    ]

    updated = sync_ams_slots(ams_units, printer_id="P1", auto_create=False)
    assert updated == 2
    assert spools[0].remain_percent == 30
    assert spools[1].remain_percent == 60


def test_sync_multi_ams(fake_session_env):
    spools, _ = fake_session_env
    spools.append(DummySpool(tray_uuid="UUID-A1-S2", remain_percent=1))
    ams_units = [
        {
            "ams_id": 0,
            "trays": [{"tray_id": 2, "tray_uuid": "UUID-A1-S2", "remain_percent": 55}],
        },
        {
            "ams_id": 1,
            "trays": [{"tray_id": 1, "tray_uuid": "UUID-A9-S1", "remain_percent": 20}],
        },
    ]

    updated = sync_ams_slots(ams_units, printer_id="P2", auto_create=False)
    # nur ein Match vorhanden
    assert updated == 1
    assert spools[0].remain_percent == 55


def test_sync_empty_trays(fake_session_env):
    spools, _ = fake_session_env
    spools.append(DummySpool(tag_uid="X"))
    ams_units = [{"trays": []}]
    updated = sync_ams_slots(ams_units, auto_create=False)
    assert updated == 0
    assert spools[0].remain_percent == 0.0


def test_sync_invalid_tray_uuid(fake_session_env):
    spools, _ = fake_session_env
    spools.append(DummySpool(tray_uuid="UUID-GOOD", remain_percent=15))
    ams_units = [{"trays": [{"tray_id": None, "tray_uuid": None, "remain_percent": 80}]}]
    updated = sync_ams_slots(ams_units, auto_create=False)
    assert updated == 0
    assert spools[0].remain_percent == 15
