from app.services.ams_parser import parse_ams
from app.services.universal_mapper import UniversalMapper
from app.services.printer_data import PrinterData
from app.services.ams_sync import sync_ams_slots
from tests.ams_test_data import SINGLE_AMS_JSON, MULTI_AMS_JSON, EDGE_AMS_JSON
from tests.conftest import DummySpool


def _map_units(raw_json, mode="multi"):
    mapper = UniversalMapper()
    mapper._get_setting_value = lambda key, default=None: mode
    out = PrinterData()
    mapper.map_ams_block(raw_json, out)
    return out


def test_end_to_end_single(fake_session_env):
    spools, _ = fake_session_env
    spools.append(DummySpool(tray_uuid="UUID-A0-S1", remain_percent=0))

    parsed = parse_ams(SINGLE_AMS_JSON)
    out = _map_units(SINGLE_AMS_JSON, mode="single")
    assert len(parsed) == 1
    assert len(out.ams_units) == 1

    updated = sync_ams_slots(out.ams_units, auto_create=False)
    assert updated >= 1
    assert spools[0].remain_percent == 0.0 or spools[0].remain_percent == parsed[0]["trays"][1].get("remain_percent", 0.0)
    # PrinterData should be serializable
    as_dict = out.to_dict()
    assert "ams_units" in as_dict


def test_end_to_end_multi(fake_session_env):
    spools, _ = fake_session_env
    spools.append(DummySpool(tray_uuid="UUID-A1-S2", remain_percent=5))

    parsed = parse_ams(MULTI_AMS_JSON)
    out = _map_units(MULTI_AMS_JSON, mode="multi")
    assert len(parsed) == 2
    assert len(out.ams_units) == 2

    updated = sync_ams_slots(out.ams_units, auto_create=False)
    assert updated >= 1


def test_end_to_end_edge(fake_session_env):
    spools, _ = fake_session_env
    spools.append(DummySpool(tray_uuid="UUID-E2", remain_percent=2))

    parsed = parse_ams(EDGE_AMS_JSON)
    out = _map_units(EDGE_AMS_JSON, mode="multi")
    assert len(parsed) == 1
    assert len(out.ams_units) == 1

    updated = sync_ams_slots(out.ams_units, auto_create=False)
    assert updated >= 1
