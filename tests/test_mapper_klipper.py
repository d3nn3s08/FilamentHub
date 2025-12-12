from app.services.universal_mapper import UniversalMapper


def test_mapper_klipper_basic():
    data = {
        "status": {
            "print_stats": {"state": "printing", "progress": 0.5, "filename": "test.gcode", "print_duration": 120},
            "heater_bed": {"temperature": 60},
            "extruder": {"temperature": 215},
            "fan": {"speed": 0.8},
            "display_status": {"layer": 3, "total_layer": 10, "estimated_time_remaining": 600},
            "temperature_sensor": {"chamber": {"temperature": 35}},
        }
    }
    mapper = UniversalMapper("KLIPPER")
    pd = mapper.map(data)

    assert pd.state == "printing"
    assert pd.progress == 50.0
    assert pd.temperature["nozzle"] == 215
    assert pd.temperature["bed"] == 60
    assert pd.temperature["chamber"] == 35
    assert pd.fan["part_cooling"] == 80.0
    assert pd.layer["current"] == 3
    assert pd.layer["total"] == 10
    assert pd.job["file"] == "test.gcode"
    assert pd.job["time_remaining"] == 600
