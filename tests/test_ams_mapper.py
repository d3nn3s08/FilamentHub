import pytest

from app.services.universal_mapper import UniversalMapper
from app.services.printer_data import PrinterData
from app.services.ams_parser import parse_ams
from tests.ams_test_data import MULTI_AMS_JSON, EDGE_AMS_JSON, EMPTY_AMS_JSON


def _run_mapper(json_payload, mode="single"):
    mapper = UniversalMapper()
    mapper._get_setting_value = lambda key, default=None: mode
    out = PrinterData()
    mapper.map_ams_block(json_payload, out)
    return out


def test_single_mode_uses_first_module():
    out = _run_mapper(MULTI_AMS_JSON, mode="single")
    assert len(out.ams_units) == 1
    assert out.ams_units[0]["ams_id"] == 0


def test_multi_mode_returns_all():
    out = _run_mapper(MULTI_AMS_JSON, mode="multi")
    assert len(out.ams_units) == 2
    assert out.ams_units[1]["ams_id"] == 1


@pytest.mark.parametrize("payload", EMPTY_AMS_JSON)
def test_empty_payload_returns_empty_units(payload):
    out = _run_mapper(payload, mode="multi")
    assert out.ams_units == []


def test_edge_trays_no_crash():
    out = _run_mapper(EDGE_AMS_JSON, mode="multi")
    assert len(out.ams_units) == 1
    assert len(out.ams_units[0]["trays"]) == 4


def test_mapper_uses_real_parser():
    # ensure parse_ams runs and produces list
    parsed = parse_ams(MULTI_AMS_JSON)
    assert isinstance(parsed, list)
    out = _run_mapper(MULTI_AMS_JSON, mode="multi")
    assert len(out.ams_units) == len(parsed)
