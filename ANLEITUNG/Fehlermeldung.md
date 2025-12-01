# FilamentHub – Troubleshooting & Lösungen

## 1. Datenbank kann nicht beschrieben werden
**Problem:**
Fehlermeldung: „Keine Schreibrechte auf data/filamenthub.db“
**Lösung:**
- Prüfe, ob der Benutzer/Container Schreibrechte auf den Ordner `data/` hat.
- Unter Docker: `-v $(pwd)/data:/app/data` und `--user` korrekt setzen.
- Unter Windows: Als Admin ausführen oder Ordnerrechte prüfen.

---

## 2. Migrationen laufen nicht automatisch
**Problem:**
Tabellen fehlen, App startet ohne Fehler, aber keine Datenbankstruktur.
**Lösung:**
- Prüfe, ob `alembic.ini` und der Ordner `alembic/` vorhanden sind.
- Starte manuell: `alembic upgrade head`
- Prüfe, ob `init_db()` im Code beim App-Start aufgerufen wird.

---

## 3. Alembic nicht installiert / nicht gefunden
**Problem:**
Fehlermeldung: „alembic: command not found“
**Lösung:**
- Im venv: `pip install alembic`
- Prüfe, ob das venv aktiviert ist (`.venv\Scripts\Activate.ps1` unter Windows).
- Im Dockerfile: `RUN pip install -r requirements.txt`

---

## 4. Webinterface nicht erreichbar
**Problem:**
Browser zeigt „Seite nicht gefunden“ oder „Connection refused“.
**Lösung:**
- Prüfe, ob die App läuft (`python run.py` oder `uvicorn app.main:app`).
- Prüfe die Portfreigabe (Standard: 8080).
- Unter Docker: Port mit `-p 8000:8000` freigeben.

---

## 5. Logs werden nicht geschrieben / Debugcenter leer
**Problem:**
Keine Einträge im Logfile, Debugcenter zeigt nichts an.
**Lösung:**
- Prüfe, ob die Logging-Konfiguration (`config.yaml`) korrekt ist.
- Stelle sicher, dass der Ordner `logs/app/` existiert und beschreibbar ist.
- Starte die App neu, prüfe die Logdatei.

---

## 6. Beispiel-Daten fehlen nach Setup
**Problem:**
Nach dem ersten Start sind keine Drucker, Materialien oder Spulen vorhanden.
**Lösung:**
- Führe das zentrale Setup-Skript aus (z. B. `python setup.py`), das Beispiel-Daten einträgt.
- Alternativ: Manuell im Webinterface anlegen.

---

## 7. Docker-Container startet nicht
**Problem:**
Fehlermeldung beim Start, Container beendet sich sofort.
**Lösung:**
- Prüfe die Logs mit `docker logs <container>`.
- Prüfe, ob alle Umgebungsvariablen und Volumes korrekt gesetzt sind.
- Stelle sicher, dass alle Abhängigkeiten installiert sind (`requirements.txt`).
