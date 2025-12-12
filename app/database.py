import logging
import os
from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine

DB_PATH = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def run_migrations() -> None:
    """Führt Alembic-Migrationen bis head aus (Baseline + Updates)."""
    logging.info("Starte Alembic-Migrationen...")
    try:
        from alembic import command  # type: ignore
        from alembic.config import Config  # type: ignore
    except ImportError:
        logging.warning("Alembic nicht installiert, Migrationen werden übersprungen.")
        return

    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        alembic_ini = os.path.join(base_dir, "alembic.ini")
        if not os.path.exists(alembic_ini):
            logging.warning("alembic.ini nicht gefunden, Migrationen werden übersprungen.")
            return
        cfg = Config(alembic_ini)
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
        cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))

        with engine.begin() as conn:
            has_version = bool(
                conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
                ).fetchone()
            )
            has_material = bool(
                conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='material'"
                ).fetchone()
            )
        if not has_version and has_material:
            logging.info("Bestehende Tabellen ohne alembic_version gefunden, setze Revision auf head.")
            command.stamp(cfg, "head")
            return

        logging.info("Führe Alembic upgrade head aus...")
        command.upgrade(cfg, "head")
        logging.info("Alembic-Migrationen erfolgreich abgeschlossen.")
    except Exception as exc:
        logging.error("Alembic-Migration fehlgeschlagen: %s", exc)
        raise


def init_db() -> None:
    """
    Setzt SQLite-Constraints und führt Migrationen aus.
    Tabellen werden ausschließlich über Alembic verwaltet.
    """
    logging.info("Initialisiere Datenbank...")
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
        logging.info("Foreign Keys aktiviert.")
    except Exception as exc:
        logging.error("Fehler beim Aktivieren der Foreign Keys: %s", exc)

    try:
        run_migrations()
    except Exception as exc:
        logging.error("Fehler bei Migrationen: %s", exc)
    logging.info("Datenbank-Initialisierung abgeschlossen.")


def get_session():
    """
    Dependency für FastAPI-Routen.
    """
    with Session(engine) as session:
        yield session
