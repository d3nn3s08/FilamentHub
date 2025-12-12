# Entwickleranleitung

## Projektstruktur
- `app/` – Backend, Modelle, Routen
- `frontend/` – UI, Templates, JS/CSS
- `services/` – externe Schnittstellen
- `data/` – Datenbank
- `docs/` – Dokumentation

## PR-Workflow
1. Forke das Repo
2. Eigenen Branch erstellen
3. Code schreiben und lokal testen
4. Committen und pushen
5. Pull Request erstellen

## Tests
- pytest verwenden
- API-Funktionen isoliert testen
- Keine echten Drucker/MQTT/Cloud im Test

## Code-Richtlinien
- Python 3.10+
- Einheitliche Struktur
- Kommentare bei komplexer Logik
- Neue Modelle: PR muss DB-Änderungen erwähnen

## Hinweise
- Feedback und Beiträge sind willkommen!
