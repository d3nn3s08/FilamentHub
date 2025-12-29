import json
from datetime import datetime
from pathlib import Path
from app.services.job_tracking_service import JobTrackingService


def test_atomic_write_and_read(tmp_path):
    svc = JobTrackingService()
    svc.snapshots_file = Path(tmp_path) / "job_snapshots.json"

    # write a snapshot
    svc._save_snapshot(
        cloud_serial="cloud-1",
        printer_id="p1",
        job_id="job-1",
        job_name="TestJob",
        slot=0,
        layer_num=1,
        mc_percent=10,
        started_at=datetime.utcnow(),
        filament_start_mm=123.4,
    )

    # read it back
    loaded = svc._load_snapshot("cloud-1", "p1")
    assert loaded is not None
    assert loaded.get("job_id") == "job-1"
    filament_start_mm = loaded.get("filament_start_mm")
    assert filament_start_mm is not None
    assert float(filament_start_mm) == 123.4


def test_corrupt_snapshot_discard_and_overwrite(tmp_path):
    svc = JobTrackingService()
    svc.snapshots_file = Path(tmp_path) / "job_snapshots.json"

    # create a corrupt file
    svc.snapshots_file.parent.mkdir(parents=True, exist_ok=True)
    with open(svc.snapshots_file, "wb") as f:
        f.write(b"{ this is not valid json")

    # _load_snapshot should detect corruption and return None (and not raise)
    loaded = svc._load_snapshot("cloud-x", "px")
    assert loaded is None

    # _save_snapshot should overwrite the corrupt file and succeed
    svc._save_snapshot(
        cloud_serial="cloud-x",
        printer_id="px",
        job_id="job-x",
        job_name="JobX",
        slot=1,
        layer_num=2,
        mc_percent=50,
        started_at=datetime.utcnow(),
    )

    # now the file should be valid JSON and loadable
    with open(svc.snapshots_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "cloud-x" in data or "px" in data


def test_delete_snapshot(tmp_path):
    svc = JobTrackingService()
    svc.snapshots_file = Path(tmp_path) / "job_snapshots.json"

    # add two snapshots
    svc._save_snapshot("c1", "p1", "job-a", "A", 0, 0, 0, datetime.utcnow())
    svc._save_snapshot("c2", "p2", "job-b", "B", 0, 0, 0, datetime.utcnow())

    # ensure both exist
    with open(svc.snapshots_file, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    assert any(v.get("job_id") == "job-a" for v in all_data.values())
    assert any(v.get("job_id") == "job-b" for v in all_data.values())

    # delete one
    svc._delete_snapshot("c1", "p1")

    with open(svc.snapshots_file, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    assert not any(v.get("job_id") == "job-a" for v in all_data.values())
    assert any(v.get("job_id") == "job-b" for v in all_data.values())
