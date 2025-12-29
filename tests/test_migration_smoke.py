import pytest
from app import database


def test_db_engine_connectable():
    # Simple smoke test: engine can be connected and sqlite_master queried
    try:
        with database.engine.connect() as conn:
            res = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
            # Connection ok if query returns (even if no tables exist yet)
            assert res is None or isinstance(res[0] if res else None, str) or res is None
    except Exception as exc:
        pytest.fail(f"DB engine not connectable: {exc}")
