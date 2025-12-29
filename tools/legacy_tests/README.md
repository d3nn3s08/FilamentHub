Moved legacy / manual test scripts

Files moved here from `tests/` because they are manual scripts, live collectors or
alternative implementations that must not be collected by pytest.

List of files:
- mqtt_publish_example.py  (manual MQTT publisher)
- legacy_printer_mapper.py (alternative mapper implementation)
- printer_service_tool.py  (service helper)
- printer_mqtt_client_tool.py (manual MQTT client)
- printer_data_tool.py     (PrinterData helper)
- collect_mapper_live.py   (live collector; saves fixture payloads)
- legacy_db_crud.py        (ad-hoc DB script)

Do NOT run `pytest` in this directory. These files are retained for manual
inspection or tooling only.
