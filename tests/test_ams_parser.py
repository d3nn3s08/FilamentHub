import pytest

from app.services.ams_parser import parse_ams
from tests.ams_test_data import (
    SINGLE_AMS_JSON,
    MULTI_AMS_JSON,
    EDGE_AMS_JSON,
    OLD_FORMAT_AMS_JSON,
    EMPTY_AMS_JSON,
)


def test_single_ams_parsed():
    result = parse_ams(SINGLE_AMS_JSON)
    assert isinstance(result, list)
    assert len(result) == 1
    unit = result[0]
    assert unit.get("ams_id") == 0
    assert unit.get("active_tray") == 1
    assert len(unit.get("trays") or []) == 4


def test_multi_ams_parsed():
    result = parse_ams(MULTI_AMS_JSON)
    assert len(result) == 2
    assert result[1].get("ams_id") == 1
    assert result[1].get("active_tray") == 2
    assert len(result[1].get("trays") or []) == 4


def test_edge_trays_no_crash():
    result = parse_ams(EDGE_AMS_JSON)
    assert len(result) == 1
    assert len(result[0].get("trays") or []) == 4


def test_old_format_trays():
    result = parse_ams(OLD_FORMAT_AMS_JSON)
    # parser darf leere Liste zurückgeben; wichtig ist, dass kein Fehler auftritt
    assert isinstance(result, list)


@pytest.mark.parametrize("payload", EMPTY_AMS_JSON)
def test_empty_payload_returns_empty_list(payload):
    result = parse_ams(payload)
    assert result == []
