# Schritte: Unraid Image bauen

Diese Anleitung beschreibt, wie du das Docker-Image für FilamentHub unter Unraid selbst baust und startest.

## 1. Voraussetzungen
- Unraid mit Docker-Unterstützung
- Projektordner mit Dockerfile und entrypoint.sh

## 2. Image lokal bauen
Wechsle in das Projektverzeichnis und führe aus:

```bash
docker build -t filamenthub .
```

## 3. Container starten
Starte den Container mit den gewünschten Volumes und Ports:

```bash
docker run -d \
  --name filamenthub \
  -p 8080:8080 \
  -v /mnt/user/appdata/filamenthub/data:/app/data \
  -v /mnt/user/appdata/filamenthub/logs:/app/logs \
  filamenthub
```

## 4. Webinterface öffnen
Rufe im Browser auf: [http://UNRAID-IP:8080](http://UNRAID-IP:8080)

## 5. Hinweise
- Die Volumes `/app/data` und `/app/logs` werden auf Unraid als persistente Ordner gemountet.
- Die Datei `entrypoint.sh` muss im Image vorhanden sein.
- Änderungen am Code erfordern ein erneutes Bauen des Images.

## 6. Optional: Docker Compose
Siehe Hauptanleitung für ein Compose-Beispiel.
