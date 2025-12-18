# Roadmap 0.1.x-alpha

## UI / Navigation & globales Design
- [x] Globales Layout basierend auf printers-modern (Sidebar, Header, Cards).
- [x] Mini-User-Menü (Avatar, Dropdown, Theme Toggle-Vorbereitung).
- [ ] Theme-Handling finalisieren (Persistenz, Light/Dark Assets, About-Modal).
- [ ] Sections verfeinern (Dashboard-KPIs, Karten, Charts).

## Multi-AMS & Spulenhandling
- [ ] AMS-Integration (Slots/Reports) sichtbar im Dashboard und Spulen-Views.
- [ ] Spulen-Bestand mit Warnungen/Filter.

## Statistiken / Graphen
- [ ] Drucker-/Job-Performance-Charts.
- [ ] Filament-Verbrauch pro Material/AMS.

## Experimentelle Features
- [ ] Theme Toggle erweitern (Auto/OS-Mode, individuelle Paletten).
- [ ] About-Dialog mit Systeminfos.

## Vorbereitung Beta/Stable
- [ ] Konsistente Navigation und Seiten (dashboard/materials/spools/printers/jobs/statistics/settings).
- [ ] Tests für Routing, Templates, Theme-Switch.
- [ ] Dokumentation ergänzen (CHANGELOG/README/TODO aktuell halten).

## Recent progress (2025-12-18)
- Tests: mehrere API-tests ergänzt (`service_routes`, `database_routes`) und lokal ausgeführt.
- Test infra: Per-run temporäre Test-DBs und `init_db()`-flow etabliert (plattformunabhängig).
- Refactor: MQTT payload processing isolated to `app/services/mqtt_payload_processor.py` to simplify `on_message()`.
- Migrations: minor Alembic migration fix applied to align models and schema.

## Near-term priorities
- [ ] Raise coverage for `app/routes/service_routes.py` by adding focused endpoint tests.
- [ ] Harden `database_routes` error paths (vacuum/backup edge cases) and add tests.
- [ ] Add lightweight unit tests for pure helpers (UniversalMapper/parse_ams parse_job integration points).

