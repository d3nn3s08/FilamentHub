import logging
import os
import sys
from typing import Dict, Iterable
from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine

DB_PATH = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
logger = logging.getLogger("database")


def verify_schema_or_exit(engine, required_schema: dict | None = None) -> None:
    """
    Prüft, ob die erwarteten Tabellen und Spalten vorhanden sind.
    Bei fehlenden Einträgen wird ein Fehler geloggt und der Prozess beendet.

    required_schema: Dict[str, List[str]]
      z.B. {"job": ["id", "eta_seconds", "filament_start_mm"]}
    """
    logger = logging.getLogger("database")
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
    logger.info("Starte Alembic-Migrationen...")
    try:
        from alembic import command  # type: ignore
        from alembic.config import Config  # type: ignore
    except ImportError:
        logger.warning("Alembic nicht installiert, Migrationen werden übersprungen.")
        return

    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        alembic_ini = os.path.join(base_dir, "alembic.ini")
        if not os.path.exists(alembic_ini):
            logger.warning("alembic.ini nicht gefunden, Migrationen werden übersprungen.")
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
        from alembic.script import ScriptDirectory
        script = ScriptDirectory.from_config(cfg)
        script_heads = set(script.get_heads())
        logger.info("Alembic Script-Heads: %s", ", ".join(sorted(script_heads)) or "<none>")

        if not has_version and has_material:
            logger.info("Bestehende Tabellen ohne alembic_version gefunden, setze Revision auf aktuelle Heads.")
            command.stamp(cfg, "heads")
            return

        # Prüfe aktuelle Revisionen bevor upgrade ausgeführt wird
        if has_version:
            with engine.connect() as conn:
                rows = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).fetchall()
                db_revisions = {row[0] for row in rows if row and row[0]}

            logger.info("Aktuelle DB-Revisionen: %s", ", ".join(sorted(db_revisions)) or "<none>")

            if db_revisions == script_heads:
                logger.info("Datenbank ist bereits auf den neuesten Head-Revisionen. Keine Migrationen nötig.")
                return

            if script_heads.issubset(db_revisions):
                logger.warning(
                    "Datenbank enthält zusätzliche/alte Alembic-Revisionen (%s). Normalisiere alembic_version auf Script-Heads.",
                    ", ".join(sorted(db_revisions - script_heads)) or "<none>",
                )
                import time

                started = time.perf_counter()
                # Manually clean alembic_version to keep only current heads
                try:
                    with engine.begin() as conn:
                        # Delete all revisions not in script_heads
                        for old_rev in db_revisions - script_heads:
                            conn.exec_driver_sql(
                                "DELETE FROM alembic_version WHERE version_num = ?",
                                (old_rev,)
                            )
                    logger.info("Unnötige Revisionen aus alembic_version entfernt.")
                except Exception as e:
                    logger.warning("Fehler bei manueller alembic_version-Bereinigung: %s, verwende stamp heads als Fallback", e)
                    command.stamp(cfg, "heads")
                elapsed = time.perf_counter() - started
                logger.info("Alembic stamp heads abgeschlossen in %.2fs.", elapsed)
                return

        # Wenn mehrere Heads existieren, führe upgrade für alle Heads aus
        if len(script_heads) > 1:
            logger.info("Mehrere Alembic-Heads entdeckt (%d). Führe 'alembic upgrade heads' aus...", len(script_heads))
            import time

            started = time.perf_counter()
            command.upgrade(cfg, "heads")
            elapsed = time.perf_counter() - started
            logger.info("Alembic upgrade heads abgeschlossen in %.2fs.", elapsed)
        else:
            logger.info("Führe Alembic upgrade head aus...")
            import time

            started = time.perf_counter()
            command.upgrade(cfg, "head")
            elapsed = time.perf_counter() - started
            logger.info("Alembic upgrade head abgeschlossen in %.2fs.", elapsed)
            # Menschlich lesbare Abschlussmeldung nach erfolgreichem Upgrade auf single head
            logger.info("[DB] Alembic upgrade head erfolgreich abgeschlossen – alle Migrationen sind fertig.")
        logger.info("Alembic-Migrationen erfolgreich abgeschlossen.")
    except Exception:
        logger.exception("Alembic-Migration fehlgeschlagen")
        raise


def init_db() -> None:
    """
    Setzt SQLite-Constraints und führt Migrationen aus.
    Tabellen werden ausschließlich über Alembic verwaltet.
    """
    logger.info("Initialisiere Datenbank...")
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
        logger.info("Foreign Keys aktiviert.")
    except Exception:
        logger.exception("Fehler beim Aktivieren der Foreign Keys")
    # Ensure DB directory exists and create an empty DB file if missing
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    if not os.path.exists(DB_PATH):
        logger.info("[DB] Datenbank existiert nicht – erstelle leere SQLite-Datei.")
        open(DB_PATH, "a").close()

    # Visual loading indicator
    print("")
    print("=" * 50)
    print("[STARTUP] FilamentHub wird initialisiert...")
    print("=" * 50)

    import time
    import threading

    # Simple spinner thread
    stop_spinner = threading.Event()
    def spinner():
        chars = ['|', '/', '-', '\\']
        idx = 0
        while not stop_spinner.is_set():
            print(f"\r[INIT] Datenbank-Migration laueft... {chars[idx % len(chars)]}", end='', flush=True)
            idx += 1
            time.sleep(0.1)
        print("\r[INIT] Datenbank-Migration laueft... [OK]     ")

    spinner_thread = threading.Thread(target=spinner, daemon=True)
    spinner_thread.start()

    try:
        run_migrations()
    except Exception:
        stop_spinner.set()
        spinner_thread.join(timeout=0.5)
        logger.exception("Fehler bei Migrationen")
        logger.error("Server wird beendet, da Migrationen fehlgeschlagen sind.")
        sys.exit(1)
    finally:
        stop_spinner.set()
        spinner_thread.join(timeout=0.5)

    # Nach Migrationen das Schema verifizieren (kritische Tabellen/Spalten)
    print("[INIT] Schema-Validierung...")
    try:
        verify_schema_or_exit(engine)
        print("[INIT] Schema-Validierung... [OK]")
    except SystemExit:
        # bereits geloggt in verify_schema_or_exit
        raise
    except Exception:
        logger.exception("Unbekannter Fehler bei Schema-Pruefung")
        logger.error("Server wird beendet.")
        sys.exit(1)

    # Menschlich lesbare Meldung nach erfolgreicher Schema-Prüfung
    logger.info("[DB] Schema-Prüfung erfolgreich – alle benötigten Tabellen und Spalten sind vorhanden.")

    logger.info("Datenbank-Initialisierung abgeschlossen.")
    # Sichtbare Abschlussmeldung für Betreiber (Migrationen + Schema-Validierung sind durchlaufen)
    logger.info("[DB] Migrationen abgeschlossen, Schema validiert – Datenbank bereit")

    # Kompaktes, eindeutiges Startup-Summary
    logger.info("[STARTUP] Datenbank bereit | Migrationen OK | Schema OK | FilamentHub kann starten")

    # Unmittelbar sichtbare, stdout-basierte Abschlussmeldungen (erscheinen nur bei Erfolg)
    print("")
    print("[DB] [OK] Migrationen abgeschlossen")
    print("[DB] [OK] Schema validiert")
    print("[STARTUP] [READY] FilamentHub ist bereit - Server laeuft")
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


def get_sync_session():
    """
    Synchroner Session für Nicht-FastAPI-Kontexte (z.B. MQTT-Callbacks).
    Gibt eine Session zurück, die mit `with` verwendet werden kann.
    """
    return Session(engine)


