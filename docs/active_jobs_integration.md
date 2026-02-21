Kurz: Integration "Aktive Drucke"

Datum: 2025-12-30

Änderungen:

- Backend:
  - Neuer API-Contract: `/api/jobs/active` liefert ein Array von `JobRead`-Objekten.
  - `progress` ist optional und wird bei unbekanntem Fortschritt als `null` zurückgegeben.
  - Server berechnet `eta_seconds` (falls möglich) — Client darf keine ETA/Progress-Berechnung vornehmen.
  - `app/routes/jobs.py`: kleinere Robustheitsanpassung beim Setzen des `progress`-Feldes.

- Schema:
  - `app/models/job.py`: `JobRead` erweitert um `progress: Optional[float] = None` (nur für API-Ausgabe).

- Tests:
  - `tests/test_jobs_active.py` enthält Integrationstests für Leer- und Aktivfall (prüft HTTP 200, Array-Antwort, `progress` == null für aktive Jobs, `eta_seconds` vorhanden).

- Frontend (keine Architekturänderung):
  - `frontend/static/js/activePrintCard.js`: nutzt einmalig `/api/jobs/active` beim Seitenladen, mappt Jobs in das bestehende Renderer-Shape und ruft `renderActiveJobs()` auf. Kein Polling.
  - `frontend/static/js/dashboard.js`: doppelten Fetch entfernt, damit nur `activePrintCard.js` den Server-Feed nutzt.
  - React-Komponenten (`frontend/react/components/PrintProgressCard.jsx`, `frontend/react/containers/ActiveJobsPanel.jsx`) als Vorbereitung hinzugefügt, werden aktuell nicht per React-Root gemountet (kein Build- oder Runtime-Change).

API-Kontrakt:
- `progress: null` bedeutet "unbekannter Fortschritt" (Client muss das als leeren/—-Zustand darstellen).
- `eta_seconds`: int|null, vom Server berechnet.

Tests:
- Tests laufen lokal; beide Tests in `tests/test_jobs_active.py` bestehen.

Weiteres:
- CI-Integration empfohlen vor Release/Beta-Freeze.
- Bei Fragen prüfe `tests/test_jobs_active.py` und `frontend/static/js/activePrintCard.js`.
