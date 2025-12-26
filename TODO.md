# FilamentHub TODO

## 🔴 PRIORITÄT 1 - KRITISCH (Stabilität)
- [ ] MQTT Auto-Reconnect implementieren (Exponential Backoff, max 10 attempts)
- [ ] Database-Indizes hinzufügen (job.printer_id, job.status, job.started_at)
- [ ] Pagination für Jobs-API (skip/limit Parameter)

## 🟠 PRIORITÄT 2 - WICHTIG (Features)
- [ ] JSON Inspector: Search/Filter-Funktion
- [ ] JSON Inspector: Copy-to-Clipboard für Felder
- [ ] MQTT Message Retention (SQLite-Tabelle, 7-Tage-Cleanup)
- [ ] MQTT Charts (Chart.js, Temperature/Progress Line-Charts)

## 🟡 PRIORITÄT 3 - PRO-FEATURES
- [ ] Deep Probe UI-Integration finalisieren (Backend ✅, UI ⚠️)
- [ ] Device Fingerprint UI-Integration finalisieren (Backend ✅, UI ⚠️)
- [ ] AMS Deep Inspect UI implementieren
- [ ] Config Manager UI (Pro): Skeleton + JS anbinden

## 🟢 PRIORITÄT 4 - OPTIONAL (Performance)
- [ ] LRU-Cache für häufige DB-Abfragen
- [ ] WebSocket für Live-Updates (statt Polling)
- [ ] Test-Coverage auf >80% erhöhen
- [ ] Performance-Panel Pro: History/Statistics, Sparklines

## 📋 ADMIN & DEPLOYMENT
- [ ] Passwortschutz für kritische Funktionen (DB-Editor, Migration, Backup)
- [ ] Docker Health-Checks in docker-compose.yml
- [ ] CI/CD Pipeline (GitHub Actions)

## 🎨 UI/UX
- [ ] Theme-Toggle Persistenz (Local Storage)
- [ ] Mobile-Optimierung verbessern
- [ ] Toast-System konsistent nutzen
- [ ] About-Dialog im User-Menü (Modal statt Alert)

## 🧪 TESTING
- [ ] Test-Coverage für service_routes erhöhen
- [ ] Tests für database_routes Edge Cases (vacuum, backup)
- [ ] Unit-Tests für mqtt_payload_processor
- [ ] Tests für scanner/MQTT/AMS

## 🐛 BUGFIXES
- [ ] 4 fehlgeschlagene Tests fixen (test_ams_sync, test_smoke_crud)
- [ ] FastAPI Deprecation Warnings (on_event → lifespan)
- [ ] datetime.utcnow() → datetime.now(UTC)

## 📚 DOKUMENTATION
- [ ] API-Docs erweitern (über Swagger hinaus)
- [ ] User-Guide vervollständigen
- [ ] Developer-Guide erweitern

---

## ✅ ERLEDIGT (Referenz)
- [x] Auto-Job-Creation aus MQTT
- [x] Bambu Credentials im Manual-Dialog
- [x] Coverage-Tests repariert (conftest.py)
- [x] 270+ Backup/Temp-Dateien gelöscht
- [x] MQTT Runtime (1101 Zeilen)
- [x] JSON Inspector Basis (Collapsible Tree, Auto-Polling)
- [x] Pro-Features Backend (Deep Probe, Fingerprint)
- [x] Scanner (Quick Scan, Network Scan, Detection)
- [x] Log-System (Rotating, Module-specific)
- [x] Docker-Setup (Dockerfile, docker-compose.yml)
- [x] Admin-System (Token-Auth, DB-Editor)

---

**Letzte Aktualisierung:** 2025-12-25
**Coverage:** 31% (Ziel: >80%)
**Tests:** 46 passed, 4 failed
