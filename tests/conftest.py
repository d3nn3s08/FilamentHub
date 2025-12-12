import pytest


class Field:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)


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
