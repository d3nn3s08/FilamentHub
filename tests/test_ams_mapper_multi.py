import pytest

from app.services.ams_parser import parse_ams
from app.services.universal_mapper import UniversalMapper
from app.services.printer_data import PrinterData

# -----------------------------
# Testdaten
# -----------------------------
TEST_JSON_MULTI = {
    "ams": {
        "modules": [
            {
                "ams_id": 0,
                "active_tray": 1,
                "tray_count": 4,
                "trays": [
                    {"tray_id": 0, "tray_uuid": "UUID-A0-S0", "material": "PLA"},
                    {"tray_id": 1, "tray_uuid": "UUID-A0-S1", "material": "PETG"},
                    {"tray_id": 2, "tray_uuid": None, "material": None},
                    {"tray_id": 3, "tray_uuid": "UUID-A0-S3", "material": "ABS"},
                ],
            },
            {
                "ams_id": 1,
                "active_tray": 2,
                "tray_count": 4,
                "trays": [
                    {"tray_id": 0, "tray_uuid": "UUID-A1-S0", "material": "PA"},
                    {"tray_id": 1, "tray_uuid": "UUID-A1-S1", "material": None},
                    {"tray_id": 2, "tray_uuid": "UUID-A1-S2", "material": "TPU"},
                    {"tray_id": 3, "tray_uuid": None, "material": None},
                ],
            },
        ]
    }
}

TEST_JSON_EDGE = {
    "ams": {
        "modules": [
            {
                "ams_id": 2,
                "active_tray": None,
                "tray_count": 4,
                "trays": [
                    {"tray_id": 0, "tray_uuid": None, "material": None},
                    {"tray_id": 1, "tray_uuid": "UUID-E1", "material": None},
                    {"tray_id": 2, "tray_uuid": "UUID-E2", "material": "PLA"},
                    {"tray_id": 3, "tray_uuid": None, "material": None},
                ],
            }
        ]
    }
}


def test_multi_ams_two_modules():
    mapper = UniversalMapper()
    mapper._get_setting_value = lambda key, default=None: "multi"
    out = PrinterData()

    mapper.map_ams_block(TEST_JSON_MULTI, out)

    assert len(out.ams_units) == 2
    assert out.ams_units[0]["ams_id"] == 0
    assert out.ams_units[0]["active_tray"] == 1
    assert len(out.ams_units[0]["trays"]) == 4
    assert out.ams_units[1]["ams_id"] == 1
    assert out.ams_units[1]["active_tray"] == 2
    assert len(out.ams_units[1]["trays"]) == 4


def test_single_mode_reduces_to_first():
    mapper = UniversalMapper()
    mapper._get_setting_value = lambda key, default=None: "single"
    out = PrinterData()

    mapper.map_ams_block(TEST_JSON_MULTI, out)

    assert len(out.ams_units) == 1
    assert out.ams_units[0]["ams_id"] == 0
    assert len(out.ams_units[0]["trays"]) == 4


@pytest.mark.parametrize(
    "payload",
    [{}, {"ams": None}, {"print": {}}],
)
def test_empty_ams_payload(payload):
    mapper = UniversalMapper()
    mapper._get_setting_value = lambda key, default=None: "multi"
    out = PrinterData()

    mapper.map_ams_block(payload, out)

    assert out.ams_units == []


def test_edge_case_incomplete_trays():
    mapper = UniversalMapper()
    mapper._get_setting_value = lambda key, default=None: "multi"
    out = PrinterData()

    mapper.map_ams_block(TEST_JSON_EDGE, out)

    assert len(out.ams_units) == 1
    assert len(out.ams_units[0]["trays"]) == 4
