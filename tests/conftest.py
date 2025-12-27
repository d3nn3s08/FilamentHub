import pytest
import os
import sys
from pathlib import Path
from sqlmodel import SQLModel, create_engine
from sqlalchemy.sql.elements import BinaryExpression

test_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(test_root))

from tests.helpers import ensure_admin_password_hash

ensure_admin_password_hash()

# Test database path
TEST_DB_PATH = os.path.join(test_root, "data", "test_filamenthub.db")

# Ensure test DB path is used by the application before app imports engine
os.environ["FILAMENTHUB_DB_PATH"] = TEST_DB_PATH

from app.database import engine

import app.models.job  # ensure SQLModel metadata registered
import app.models.material
import app.models.printer
import app.models.spool
import app.models.settings


class Field:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other) -> bool:
        return self.name == getattr(other, "name", None)


class DummySpool:
    tag_uid = Field("tag_uid")
    tray_uuid = Field("tray_uuid")
    ams_slot = Field("ams_slot")

    def __init__(self, **kwargs):
        self.material_id = kwargs.get("material_id")
        self.printer_id = kwargs.get("printer_id")
        self.ams_slot = kwargs.get("ams_slot")
        self.last_slot = kwargs.get("last_slot")
        self.tag_uid = kwargs.get("tag_uid")
        self.tray_uuid = kwargs.get("tray_uuid")
        self.tray_color = kwargs.get("tray_color")
        self.tray_type = kwargs.get("tray_type")
        self.remain_percent = kwargs.get("remain_percent", 0.0)
        self.weight_current = kwargs.get("weight_current")
        self.weight_full = kwargs.get("weight_full")
        self.weight_empty = kwargs.get("weight_empty")
        self.last_seen = kwargs.get("last_seen")
        self.first_seen = kwargs.get("first_seen")
        self.used_count = kwargs.get("used_count", 0)
        self.label = kwargs.get("label")


class DummyMaterial:
    name = Field("name")
    brand = Field("brand")

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "mat-1")
        self.name = kwargs.get("name")
        self.brand = kwargs.get("brand")
        self.color = kwargs.get("color")
        self.density = kwargs.get("density")
        self.diameter = kwargs.get("diameter")


class FakeResult:
    def __init__(self, items):
        self.items = items

    def first(self):
        return self.items[0] if self.items else None


class FakeSelect:
    def __init__(self, model):
        self.model = model
        self.filters = []

    def where(self, condition):
        self.filters.append(condition)
        return self


def fake_select(model):
    return FakeSelect(model)


class FakeSession:
    def __init__(self, spools, materials):
        self._spools = spools
        self._materials = materials

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def exec(self, select_obj):
        if select_obj.model is DummyMaterial:
            return FakeResult(self._materials)
        if select_obj.model is DummySpool:
            items = self._spools
            for flt in select_obj.filters:
                if isinstance(flt, tuple) and flt[0] == "eq":
                    _, field, expected = flt
                    items = [s for s in items if getattr(s, field, None) == expected]
                elif isinstance(flt, BinaryExpression):
                    key = flt.left.key
                    value = getattr(flt.right, "value", None)
                    items = [s for s in items if getattr(s, key, None) == value]
            return FakeResult(items)
        return FakeResult([])

    def add(self, obj):
        if isinstance(obj, DummySpool) and obj not in self._spools:
            self._spools.append(obj)
        if isinstance(obj, DummyMaterial) and obj not in self._materials:
            self._materials.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        return None

    def rollback(self):
        return None


@pytest.fixture
def fake_session_env(monkeypatch):
    """
    Monkeypatch ams_sync Session/select/Spool/Material to in-memory fakes.
    Returns (spools, materials) lists for inspection.
    """
    from app.services import ams_sync

    spools = []
    materials = []

    monkeypatch.setattr(ams_sync, "Session", lambda engine=None: FakeSession(spools, materials))
    monkeypatch.setattr(ams_sync, "select", fake_select)
    monkeypatch.setattr(ams_sync, "Spool", DummySpool)
    monkeypatch.setattr(ams_sync, "Material", DummyMaterial)
    monkeypatch.setattr(ams_sync, "engine", None)

    return spools, materials


@pytest.fixture(autouse=True, scope="session")
def reset_db():
    # Testdatenbank löschen, falls vorhanden
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    # Tabellen neu anlegen
    SQLModel.metadata.create_all(engine)
    yield
    # Nach den Tests optional wieder löschen
    try:
        engine.dispose()
    except Exception:
        pass
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture
def db_session():
    """Provide a simple Session fixture tests can opt into.

    Note: This does not automatically wrap sessions created directly
    with `Session(engine)` in tests — consider migrating tests to use
    this fixture or implement a per-test engine/connection strategy.
    """
    from sqlmodel import Session as _Session

    sess = _Session(engine)
    try:
        yield sess
    finally:
        try:
            sess.rollback()
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass
