# FilamentHub TODO

## Phase 1 - Basisfunktionen
1. [x] DB Editor Tab im UI anlegen
2. [x] Backend-Endpunkt fuer schreibende SQL-Queries
3. [x] UI mit Ergebnis-/Fehleranzeige erweitern (Editor-Output, Query-Output)

## Phase 2 - Sicherheit / Admin (rot)
4. [ ] Passwortschutz fuer kritische Funktionen (DB-Editor, Migration, Backup, Admin)
5. [ ] Separater Tab mit Passwortabfrage fuer kritische Funktionen

## Phase 3 - Deployment / Migration
6. [ ] Docker/Pi-Images: alembic.ini und alembic/ ins Image aufnehmen; Schreibrechte auf data/filamenthub.db sicherstellen
7. [ ] Start-Skripte: Vor App-Start alembic upgrade head (oder init_db()) ausfuehren
8. [ ] Releases: Alembic mit ausliefern und Migrationen automatisch ausfuehren
9. [ ] Option: Bei fehlendem Alembic Start abbrechen statt warnen

## Phase 4 - CI / Tests
10. [ ] CI-Job: alembic upgrade head gegen frische DB
11. [ ] Tests im Service-Tab mit Test-DB, init_db vor pytest
12. [ ] Coverage ueber Smoke-Tests mit Test-DB

## Phase 5 - Integrationen / Services
13. [ ] Test: Drucker-DB-Eintrag und Status im Debug/Status-API pruefen
14. [ ] Optionaler Auto-Connector fuer MQTT/Moonraker

## Phase 6 - Backup
15. [x] Backup-Funktion ergaenzt (DB) mit Trigger im Debug-Tab

## Phase 7 - MQTT / Debug-Center
### Low Effort
16. [ ] Topic-Liste mit Count + letzte Zeit + Klick fuer Detail
17. [ ] Feld-Kacheln (Temperaturen, Fortschritt)
18. [ ] Nachrichten-Rate (Linienplot)

### Medium
19. [ ] Diff-Viewer mit Highlight nur Veraenderungen
20. [x] JSON-Baum mit Collapse
21. [ ] Alert-Regeln (Schwellenwerte im UI)

### Fehlerbehebung / Logging
22. [ ] MQTT-Logrotation auf RotatingFileHandler umstellen (Zugriffsfehler mqtt_messages.log beheben)

### High Impact
23. [ ] Aggregationspanel + Health Monitor
24. [ ] Kompakter Topic-Explorer
25. [ ] Feld-Inspector (Live-Kacheln mit Farbstatus)
26. [ ] Nachrichten-Rate Monitor (Diagramm)
27. [ ] Diff-Viewer fuer Topic-Aenderungen
28. [ ] Alert-Regeln: Schwellenwert + Popup/Sound
29. [ ] Payload-Suche + Favoriten
30. [ ] Strukturierter JSON-Baum mit Copy-Buttons
31. [ ] Export/Snapshot Button
32. [ ] Aggregationspanel: Durchschnitt/Min/Max
33. [ ] MQTT Health Panel
