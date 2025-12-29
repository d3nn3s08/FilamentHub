# MUSTFixes Checkliste  FilamentHub

Kurz: Konkrete, prüfbare Schritte pro Problemfeld mit Dateiangaben, PatchSkizzen, Tests und Aufwandsschätzungen.

---

## 1) Migrationen & DBKonsistenz prüfen und erzwingen
- Dateien:
  - alembic/versions/20251228_add_eta_seconds_to_job.py
  - app/database.py
  - alembic/env.py
- Ziel: Sicherstellen, dass alle AlembicRevisionen auf der produktiven DB angewendet sind; failfast auf Startup wenn Schema fehlt.
- PatchSkizze:
  - In `app/database.py` hinzufügen: `verify_schema_or_exit()`  
    - Prüft per `PRAGMA table_info('job')` auf erwartete Spalten (`eta_seconds`, `filament_start_mm`, ).  
    - Bei Fehlen: `logger.error(...)` + `sys.exit(1)` mit Hinweis `alembic upgrade head`.
  - In `app/main.py` vor AppStart `verify_schema_or_exit()` aufrufen.
- Tests:
  - `tests/test_migrations_check.py`
    - Positive: Erstelle temp sqlite DB, führe `alembic upgrade head` (subprocess)  assert `PRAGMA table_info('job')` enthält `eta_seconds`.
    - Negative: Simuliere fehlende Migration  assert `verify_schema_or_exit()` raise/exit.
- Aufwand: medium, ca. 23 h.

---

## 2) Atomare SnapshotIO & KorruptionsRecovery
- Datei:
  - app/services/job_tracking_service.py
- Ziel: Vermeidung von race conditions und JSONKorruption beim Schreiben/Lesen von `data/job_snapshots.json`.
- PatchSkizze:
  - Schreibe snapshots in `job_snapshots.json.tmp` und `os.replace()` zur Finaldatei (atomic rename).  
  - Beim Lesen: fange `JSONDecodeError` ab, wenn vorhanden: versuche `.tmp` wiederherzustellen oder lege `.bak` an und initialisiere leere Struktur.  
  - Optional: `portalocker` für file lock verwenden.
  - Auf Exceptions: `logger.exception(...)` statt stiller Fehler.
- Tests:
  - `tests/test_job_snapshot_io.py`
    - Normaler Save/Load.
    - Simulierter paralleler Write (Threads/processes)  assert gültiges JSON.
    - Korruptionsfall  assert recovery erstellt `.bak` und liefert default.
- Aufwand: medium, ca. 4 h.

---

## 3) Replace `except:` durch gezieltes ExceptionHandling & Logging
- Dateien (Beispiele):
  - app/routes/mqtt_routes.py
  - app/routes/scanner_routes.py
- Ziel: Keine stillen Fehler; klare Logs und konsistente HTTPFehlerantworten.
- PatchSkizze:
  - Ersetze `except:` mit `except Exception as exc:`; rufe `logger.exception(...)`.  
  - In HTTPRouten: bei unerwartetem Fehler `raise HTTPException(status_code=500, detail="internal error")`.
  - Bei erwartbaren Fehlern: spezifisch (z.B. `KeyError`, `ValueError`, `sqlite3.Error`) behandeln.
- Tests:
  - `tests/test_routes_error_handling.py`
    - Mocke fehlerhafte Eingabe  assert HTTP 500 & logEintrag.
- Aufwand: medium, ca. 36 h.

---

## 4) Konsolidieren DBAccess: entferne direkte `sqlite3`Aufrufe in Routen
- Dateien:
  - app/routes/database_routes.py
  - scripts/get_bambu_printer.py (nur scripts; optional)
- Ziel: Einheitliche DBAPI (SQLModel/Session) in LaufzeitRouten; vermeide Lock/ABIInkonsistenzen.
- PatchSkizze:
  - Ersetze `sqlite3.connect(DB_PATH)` in Routen durch `with Session(engine) as session:`.
  - Falls Scripts `sqlite3` verwenden, dokumentieren oder refactoren.
- Tests:
  - `tests/test_database_routes_api.py` auf Sessionbasierte Implementierung anpassen.
- Aufwand: medium, ca. 610 h.

---

## 5) Tests für kritische Pfade: ETA, Job resume/finalize, Snapshot Recovery
- Dateien:
  - app/services/eta/*
  - app/services/job_tracking_service.py
- Ziel: Absichern der BusinessLogik gegen Regressionen.
- TestSkizzen:
  - `tests/test_eta_algorithms.py`: edge cases (0 layers, negative times, fallback switching).
  - `tests/test_job_resume_and_finalize.py`: Simuliere restart, restore via snapshot, finalize mit primary/fallback.
  - `tests/test_snapshot_corruption_recovery.py`: corrupted file recovery.
- Aufwand: lowmedium, ca. 812 h.

---

## Zusatz: CI & StartChecks (kurz)
- Füge CIJob hinzu:
  - `pip install -r requirements-dev.txt`
  - `alembic upgrade head` gegen temp DB oder `alembic --sql` Check
  - `pytest --maxfail=1 -q`
- Dokumentiere DBBackup Hinweis in README/RELEASE.md (Backup vor Upgrade).

---

## Priorität & Reihenfolge (schnelle Empfehlung)
1. Migrationen & DBKonsistenz prüfen (blocker)  
2. Atomare SnapshotIO (hohes DatenverlustRisiko)  
3. Replace bare `except:` (Fehlersuche + Stabilität)  
4. Konsolidieren DBAccess in Routen (Inkonsistenzquelle)  
5. Tests für kritische Pfade (stabile Basis)

