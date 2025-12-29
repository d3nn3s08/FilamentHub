import builtins
import importlib
import os
import types

import pytest

from app.database import engine, init_db, run_migrations


class DummyConnection:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.executed = []

    def exec_driver_sql(self, value):
        next_value = next(self._responses, None)
        return types.SimpleNamespace(fetchone=lambda: next_value)

    def execute(self, value):
        self.executed.append(value)


class DummyContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


@pytest.fixture(autouse=True)
def restore_engine(monkeypatch):
    orig_connect = engine.connect
    orig_begin = engine.begin
    yield
    monkeypatch.setattr(engine, "connect", orig_connect)
    monkeypatch.setattr(engine, "begin", orig_begin)


def test_init_db_runs_migrations_and_sets_pragma(monkeypatch):
    executed = []

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def execute(self, value):
            executed.append(value)

    def fake_connect():
        return FakeConn()

    called = {"run": 0}

    monkeypatch.setattr("app.database.engine.connect", fake_connect)
    monkeypatch.setattr("app.database.run_migrations", lambda: called.__setitem__("run", 1))

    init_db()

    assert any("PRAGMA foreign_keys=ON" in str(value) for value in executed)
    assert called["run"] == 1


def test_run_migrations_handles_missing_alembic(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("alembic"):
            raise ImportError("stub")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Should simply return without raising
    run_migrations()

    monkeypatch.setattr(builtins, "__import__", real_import)


def test_run_migrations_stamps_when_version_missing(monkeypatch):
    fake_conn = DummyConnection([None, ("material",)])
    monkeypatch.setattr("app.database.engine.begin", lambda: DummyContext(fake_conn))

    fake_alembic = types.ModuleType("alembic")
    fake_command = types.SimpleNamespace(stamp=lambda cfg, rev: setattr(fake_command, "stamped", True),
                                         upgrade=lambda cfg, rev: setattr(fake_command, "upgraded", True))
    fake_alembic.command = fake_command

    class FakeConfig:
        def __init__(self, path):
            self.path = path

        def set_main_option(self, key, value):
            setattr(self, key, value)

    fake_config_module = types.ModuleType("alembic.config")
    fake_config_module.Config = FakeConfig

    monkeypatch.setitem(importlib.sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(importlib.sys.modules, "alembic.command", fake_command)
    monkeypatch.setitem(importlib.sys.modules, "alembic.config", fake_config_module)

    # Force alembic.ini path to exist
    monkeypatch.setattr(os.path, "exists", lambda path: True)

    run_migrations()

    assert getattr(fake_command, "stamped", False) is True
    assert getattr(fake_command, "upgraded", False) is False

