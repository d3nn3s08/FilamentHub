import json
from app.services.ams_sync import sync_ams_slots

# Paste your AMS payload here (trimmed for readability)
payload = {
  "devices": [
    {
      "device_serial": "0309DA441501184",
      "printer_id": "c7d0e3d4-4e5e-47b7-aa87-1c2da3ec858c",
      "ts": "2026-01-16T11:12:40.822074Z",
      "online": True,
      "firmware": None,
      "signal": None,
      "ams_units": [
        {
          "printer_serial": "0309DA441501184",
          "printer_name": "A1 Mini",
          "ams_id": 0,
          "temp": 0,
          "humidity": "5",
          "active_tray": 255,
          "trays": [
            {
              "slot": 0,
              "tray_uuid": "0AD1C0E93D664E3DB889830977925A4D",
              "tag_uid": "AC3320D000000100",
              "remain_weight": None,
              "tray_weight": 1000,
              "remain_percent": None,
              "remaining_grams": 0,
              "total_len": 330000,
              "nozzle_temp_min": None,
              "nozzle_temp_max": None,
              "tray_type": "PLA",
              "tray_sub_brands": "PLA Basic",
              "tray_color": "00AE42FF"
            },
            {"slot":1,"tray_uuid":None,"tag_uid":None},
            {"slot":2,"tray_uuid":None,"tag_uid":None},
            {"slot":3,"tray_uuid":None,"tag_uid":None}
          ],
          "is_ams_lite": True
        },
        {
          "printer_serial": "0309DA441501184",
          "printer_name": "A1 Mini",
          "ams_id": 254,
          "temp": None,
          "humidity": None,
          "active_tray": 254,
          "trays": [
            {
              "slot": 254,
              "tray_uuid": "00000000000000000000000000000000",
              "tag_uid": "0000000000000000",
              "remain_weight": None,
              "tray_weight": 0,
              "remain_percent": None,
              "remaining_grams": 0,
              "total_len": None,
              "nozzle_temp_min": None,
              "nozzle_temp_max": None,
              "tray_type": "PLA",
              "tray_sub_brands": "",
              "tray_color": "18C241FF"
            }
          ],
          "is_ams_lite": True
        }
      ]
    }
  ]
}

# Extract ams_units for the first device
devices = payload.get("devices") or []
if not devices:
    print("No devices in payload")
    raise SystemExit(1)

device = devices[0]
ams_units = device.get("ams_units") or []
printer_id = device.get("printer_id")

print(f"Calling sync_ams_slots for printer_id={printer_id} with {len(ams_units)} units")
updated = sync_ams_slots(ams_units, printer_id=printer_id, auto_create=True)
print(f"sync_ams_slots returned: {updated}")
