# Beitrag zu FilamentHub

Vielen Dank, dass du überlegst, zu FilamentHub beizutragen!  
Dieses Projekt lebt davon, dass Nutzer Fehler melden, Ideen teilen und Code beitragen.  
Hier findest du alle Infos, um direkt loslegen zu können.

---

## 🚀 Wie du beitragen kannst

### 1. Fehler melden (Bug Reports)
Wenn etwas nicht funktioniert:

1. Öffne ein neues Issue: **Issues → New Issue**
2. Wähle “Bug Report”
3. Beschreibe:
   - Was ist passiert?
   - Erwartetes Verhalten?
   - Schritte zur Reproduktion
   - Version / OS / Docker / Druckertyp
4. Logs oder Screenshots helfen immer.

Bitte zunächst prüfen, ob der Fehler schon gemeldet wurde.

---

### 2. Feature Requests
Wenn du eine Idee für eine Funktion hast:

1. Öffne ein neues Issue → “Feature Request”
2. Beschreibe klar:
   - Was soll passieren?
   - Welches Problem löst es?
   - Optional: Wie stellst du dir die UI oder API vor?

Große Features werden vorab im Issue diskutiert.

---

### 3. Code beitragen (Pull Requests)

Wenn du selbst programmieren möchtest:

1. Forke das Repo
2. Eigenen Branch erstellen:
   ```bash
   git checkout -b feature/mein-feature

3. Code schreiben

4. Lokal testen:
python run.py

5. Committen:
git add .
git commit -m "Add: Mein Feature"

6. Pushen:
git push origin feature/mein-feature

7. Pull Request erstellen
- Einen PR pro Feature
- Kein gigantischer „Alles-auf-einmal“-PR
- Struktur des Projektes einhalten

Projektstruktur (Kurzüberblick)

FilamentHub/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/
│   └── routes/
├── services/
├── frontend/
├── data/
├── docs/
├── config.yaml
├── Dockerfile
└── run.py

🧹 Code Richtlinien
- Python 3.10+
- Einheitliche Struktur beachten
- Keine toten Dateien, kein Debug-Müll
- Backend folgt FastAPI + SQLModel Best Practices
- Externe Systeme (Bambu, Klipper) immer mocken
- Kommentare bei komplexer Logik
- Neue Modelle → PR muss DB-Änderungen erwähnen

🔍 Tests

Tests sind in diesem Stadium noch minimal.
Wenn du Tests hinzufügst:

pytest verwenden

API-Funktionen isoliert testen

Keine echten Drucker ansprechen

Keine realen MQTT/Cloud-Aufrufe

Bambu und Klipper über Mocks simulieren

📝 Dokumentation

Wenn du neue Funktionen hinzufügst:

API-Endpunkte im PR erwähnen

Kurz beschreiben, wie es benutzt wird

Bei UI-Änderungen → Screenshot einfügen

Bei Strukturänderungen → README anpassen

❤️ Community & Support

Wenn du Fragen hast:

Issue öffnen

Oder im PR kommentieren

Feedback geben ist immer willkommen

Jeder ist willkommen – Anfänger, Fortgeschrittene und Profis.

📜 Lizenz

Durch das Einsenden eines Pull Requests erklärst du dich einverstanden,
dass dein Code unter der MIT-Lizenz veröffentlicht wird.



Danke, dass du FilamentHub unterstützt! 🚀

---

# ✔️ Datei ist fertig!
Wenn du möchtest, packe ich sie dir direkt:

👉 in eine ZIP  
👉 in deine Repo-Struktur  
👉 als GitHub-kompatibel formatierte Datei mit Badge  
👉 möchte ich sie direkt in *deiner* README verlinken?

Sag einfach:

**„Bitte in mein Projekt integrieren“** oder  
**„Mach mir das ZIP fertig“**
