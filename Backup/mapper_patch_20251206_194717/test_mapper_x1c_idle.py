import json
from pathlib import Path

from app.services.universal_mapper import UniversalMapper


def test_mapper_x1c_idle_fixture():
    fixture = Path("tests/fixtures/x1c_idle.json")
    data = json.loads(fixture.read_text(encoding="utf-8"))

    mapper = UniversalMapper("X1C")
    pd = mapper.map(data)

    # PrinterData darf NIE komplett None sein
    assert pd is not None

    # State sollte immer gesetzt sein beim X1C
    assert pd.state is not None

    # Progress darf None oder float sein
    assert isinstance(pd.progress, (float, type(None)))

    # Temperaturprüfung robust: nur prüfen, wenn JSON Werte enthält
    raw_nozzle = (
        data.get("nozzle_temper")
        or data.get("nozzle_temp")
        or data.get("extruder_temp")
        or data.get("extruder", {}).get("temp")
    )
    if raw_nozzle is not None:
        assert pd.temperature["nozzle"] == float(raw_nozzle)
    else:
        # Falls JSON gar keine Temperatur liefert → darf Mapper None oder float setzen
        assert isinstance(pd.temperature["nozzle"], (float, type(None)))
    
    # Layer Daten müssen existieren, aber dürfen 0 sein
    assert "current" in pd.layer
    assert "total" in pd.layer
