import os
import tempfile
from app.routes import service_routes


def test_make_test_db_path_is_in_temp_and_unique():
    p1 = service_routes.make_test_db_path()
    p2 = service_routes.make_test_db_path()

    # Both paths should be inside the system temp directory
    tempdir = tempfile.gettempdir()
    assert os.path.commonpath([tempdir, p1]) == tempdir
    assert os.path.commonpath([tempdir, p2]) == tempdir

    # Paths should be different (unique per call)
    assert p1 != p2


def test_create_test_response_fields():
    r = service_routes.create_test_response(status="ok", message="All good")
    assert r["status"] == "ok"
    assert r["message"] == "All good"
    assert "timestamp" in r

    r2 = service_routes.create_test_response(status="fail", message="Bad", details="stacktrace")
    assert r2["status"] == "fail"
    assert r2["details"] == "stacktrace"
