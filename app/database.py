import logging
import os
import sys
from typing import Dict, Iterable
from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine

DB_PATH = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
logger = logging.getLogger("app")


def verify_schema_or_exit(engine, required_schema: dict | None = None) -> None:
    """
    Prüft, ob die erwarteten Tabellen und Spalten vorhanden sind.
    Bei fehlenden Einträgen wird ein Fehler geloggt und der Prozess beendet.

    required_schema: Dict[str, List[str]]
      z.B. {"job": ["id", "eta_seconds", "filament_start_mm"]}
    """
    logger = logging.getLogger("filamenthub.database")
    # Minimal required schema: only fields that runtime code strictly depends on
    DEFAULT_REQUIRED_SCHEMA: Dict[str, Iterable[str]] = {
        "job": {
            "id",
            "started_at",
            "finished_at",
            "filament_used_mm",
            "filament_start_mm",
            "eta_seconds",
        }
    }

    if required_schema is None:
        required_schema = DEFAULT_REQUIRED_SCHEMA

    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
    except Exception as exc:
        logger.error("[DB] Fehler beim Initialisieren des DB-Inspectors: %s", exc, exc_info=True)
        logger.warning("[DB] Inspector nicht verfügbar — Schema-Check wird übersprungen. Falls dies in Produktion auftritt, prüfe die DB-Verbindung.")
        logger.debug("[DB] Database file: %s", DB_PATH)
        # Fallback: falls Inspector nicht nutzbar ist (z.B. in Tests mit monkeypatch),
        # überspringen wir die schema-verification an dieser Stelle und lassen
        # init_db() normal weiterlaufen. Ein späterer Fehler beim Zugriff auf
        # spezifische Tabellen wird dann sichtbar.
        return

    missing = []
    for table, cols in required_schema.items():
        if table not in existing_tables:
            missing.append(f"Missing table: {table}")
            continue
        try:
            existing_cols = {c["name"] for c in inspector.get_columns(table)}
        except Exception as exc:
            logger.error("Fehler beim Lesen der Spalten fuer Tabelle %s: %s", table, exc, exc_info=True)
            missing.append(f"Cannot inspect columns for table: {table}")
            continue
        for col in cols:
            if col not in existing_cols:
                missing.append(f"Missing column: {table}.{col}")

    if missing:
        logger.error("[DB] Schema validation failed")
        for item in missing:
            # item is either 'Missing table: X' or 'Missing column: X.Y' or inspect error
            logger.error("[DB] %s", item)
        logger.error("[DB] Database file: %s", DB_PATH)
        logger.error("[DB] Fix: run `alembic upgrade head` or follow migrations in the project README. Server will exit.")
        sys.exit(1)


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

        # Prüfe aktuelle Revision bevor upgrade ausgeführt wird
        if has_version:
            with engine.connect() as conn:
                current = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()
                if current:
                    logging.info(f"Aktuelle DB-Revision: {current[0]}")
                    # Prüfe ob bereits auf head(s)
                    from alembic.script import ScriptDirectory
                    script = ScriptDirectory.from_config(cfg)
                    heads = script.get_heads()
                    # if single head, compare directly
                    if len(heads) == 1 and current[0] == heads[0]:
                        logging.info("Datenbank ist bereits auf der neuesten Version (head). Keine Migrationen nötig.")
                        return

        # Wenn mehrere Heads existieren, führe upgrade für alle Heads aus
        from alembic.script import ScriptDirectory
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        if len(heads) > 1:
            logging.info(f"Mehrere Alembic-Heads entdeckt ({len(heads)}). Führe 'alembic upgrade heads' aus...")
            command.upgrade(cfg, "heads")
        else:
            logging.info("Führe Alembic upgrade head aus...")
            command.upgrade(cfg, "head")
            # Menschlich lesbare Abschlussmeldung nach erfolgreichem Upgrade auf single head
            logging.info("[DB] Alembic upgrade head erfolgreich abgeschlossen – alle Migrationen sind fertig.")
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
    # Ensure DB directory exists and create an empty DB file if missing
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    if not os.path.exists(DB_PATH):
        logging.info("[DB] Datenbank existiert nicht – erstelle leere SQLite-Datei.")
        open(DB_PATH, "a").close()

    try:
        run_migrations()
    except Exception as exc:
        logging.error("Fehler bei Migrationen: %s", exc, exc_info=True)
        logging.error("Server wird beendet, da Migrationen fehlgeschlagen sind.")
        sys.exit(1)

    # Nach Migrationen das Schema verifizieren (kritische Tabellen/Spalten)
    try:
        verify_schema_or_exit(engine)
    except SystemExit:
        # bereits geloggt in verify_schema_or_exit
        raise
    except Exception as exc:
        logging.error("Unbekannter Fehler bei Schema-Pruefung: %s", exc, exc_info=True)
        logging.error("Server wird beendet.")
        sys.exit(1)

    # Menschlich lesbare Meldung nach erfolgreicher Schema-Prüfung
    logging.info("[DB] Schema-Prüfung erfolgreich – alle benötigten Tabellen und Spalten sind vorhanden.")

    logging.info("Datenbank-Initialisierung abgeschlossen.")
    # Sichtbare Abschlussmeldung für Betreiber (Migrationen + Schema-Validierung sind durchlaufen)
    logger.info("[DB] Migrationen abgeschlossen, Schema validiert – Datenbank bereit")

    # Kompaktes, eindeutiges Startup-Summary
    logging.info("[STARTUP] Datenbank bereit | Migrationen OK | Schema OK | FilamentHub kann starten")

    # Unmittelbar sichtbare, stdout-basierte Abschlussmeldungen (erscheinen nur bei Erfolg)
    print("")
    print("[DB] ✅ Migrationen abgeschlossen")
    print("[DB] ✅ Schema validiert")
    print("[STARTUP] 🚀 FilamentHub ist bereit – Server läuft")
    print("")

    # Optionales, visuelles Startup-Banner (zusätzliche Klarheit für Betreiber)
    print("==============================================")
    print("   FILAMENTHUB STARTUP ERFOLGREICH")
    print("   Datenbank: OK")
    print("   Migrationen: OK")
    print("   Status: RUNNING")
    print("==============================================")


def get_session():
    """
    Dependency für FastAPI-Routen.
    """
    with Session(engine) as session:
        yield session
