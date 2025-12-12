"""
Synthetische Testdaten für AMS-Parser/-Mapper.
"""

SINGLE_AMS_JSON = {
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
            }
        ]
    }
}

MULTI_AMS_JSON = {
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

EDGE_AMS_JSON = {
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

OLD_FORMAT_AMS_JSON = {
    "ams": {
        "tray_0": {"tray_id": 0, "tray_uuid": "UUID-OLD-0", "material": "PLA"},
        "tray_1": {"tray_id": 1, "tray_uuid": "UUID-OLD-1", "material": "PETG"},
        "tray_2": {"tray_id": 2, "tray_uuid": "UUID-OLD-2", "material": None},
        "tray_3": {"tray_id": 3, "tray_uuid": "UUID-OLD-3", "material": "ABS"},
        "active_tray": 1,
    }
}

EMPTY_AMS_JSON = [
    {},
    {"ams": None},
    {"print": {}},
]
