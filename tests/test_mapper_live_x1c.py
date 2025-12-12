import json
from pathlib import Path

import pytest

from app.services.universal_mapper import UniversalMapper

SAMPLE_DIR = Path("tests/live_samples")
SAMPLES = [
    "x1c_idle.json",
    "x1c_heating.json",
    "x1c_printing.json",
    "x1c_pause.json",
    "x1c_finish.json",
]


@pytest.mark.parametrize("filename", SAMPLES)
def test_live_sample_mapping(filename):
    sample_path = SAMPLE_DIR / filename
    if not sample_path.exists():
        pytest.skip(f"Live sample missing: {filename}")

    data = json.loads(sample_path.read_text(encoding="utf-8"))
    mapper = UniversalMapper("X1C")
    pd = mapper.map(data)

    assert pd.state is not None
    assert isinstance(pd.progress, (float, type(None)))
    assert isinstance(pd.temperature.get("nozzle"), (float, type(None)))
    assert isinstance(pd.temperature.get("bed"), (float, type(None)))
    assert isinstance(pd.temperature.get("chamber"), (float, type(None)))
    assert isinstance(pd.layer.get("current"), (int, type(None)))
    assert isinstance(pd.layer.get("total"), (int, type(None)))
    assert isinstance(pd.job.get("file"), (str, type(None)))
