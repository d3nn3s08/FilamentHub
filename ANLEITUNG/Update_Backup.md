# Update & Backup

## Update-Prozess
1. Prüfe, ob neue Versionen verfügbar sind (GitHub Releases oder Pull).
2. Repository aktualisieren:
   ```bash
   git pull
   ```
3. Virtuelle Umgebung aktivieren und Abhängigkeiten aktualisieren:
   ```bash
   pip install -r requirements.txt
   ```
4. Bei größeren Updates: Migrationen ausführen
   ```bash
   alembic upgrade head
   ```
5. App neu starten.

## Backup (DB + Logs)
- Die Debug/Service-UI hat einen Backup-Button: erzeugt ein ZIP mit Datenbank + Logfiles unter `data/backups/filamenthub_backup_<timestamp>.zip`.
- Datenbank liegt standardmäßig unter `data/filamenthub.db`.
- Alternative manuell:
  ```bash
  cp data/filamenthub.db /backup/filamenthub.db
  ```
- Für Docker: Volume sichern (`docker cp` oder direktes Volume-Backup).

## Wiederherstellung
- Gesichertes DB-File zurück in `data/` kopieren.
- App neu starten.

## Hinweise
- Vor jedem Update Backup anlegen!
- Bei Problemen siehe [Fehlermeldung.md](Fehlermeldung.md)
