# API-Dokumentation

## Übersicht
FilamentHub bietet eine REST-API für Material, Spool, Drucker und Jobs.

## Endpunkte (Beispiele)

### Material
- `GET /api/materials` – Liste aller Materialien
- `POST /api/materials` – Neues Material anlegen
- `GET /api/materials/{id}` – Material abrufen
- `PUT /api/materials/{id}` – Material aktualisieren
- `DELETE /api/materials/{id}` – Material löschen

### Spool
- `GET /api/spools` – Liste aller Spulen
- `POST /api/spools` – Neue Spule anlegen
- `GET /api/spools/{id}` – Spule abrufen
- `PUT /api/spools/{id}` – Spule aktualisieren
- `DELETE /api/spools/{id}` – Spule löschen

### Drucker
- `GET /api/printers` – Liste aller Drucker
- `POST /api/printers` – Drucker anlegen
- `GET /api/printers/{id}` – Drucker abrufen
- `PUT /api/printers/{id}` – Drucker aktualisieren
- `DELETE /api/printers/{id}` – Drucker löschen

### Jobs
- `GET /api/jobs` – Liste aller Druckjobs
- `POST /api/jobs` – Job anlegen
- `GET /api/jobs/{id}` – Job abrufen
- `PUT /api/jobs/{id}` – Job aktualisieren
- `DELETE /api/jobs/{id}` – Job löschen

## Beispiel-Request
```http
POST /api/materials
Content-Type: application/json

{
  "name": "PLA Rot",
  "type": "PLA",
  "color": "Rot",
  "manufacturer": "TestMaker",
  "density": 1.24,
  "diameter": 1.75
}
```

## Authentifizierung
- Aktuell keine Authentifizierung (optional für spätere Versionen)

## Weitere Infos
- Swagger/OpenAPI-Doku unter `/docs` im Webinterface
