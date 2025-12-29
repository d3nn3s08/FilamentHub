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
  -p 8085:8085 \
  -v /mnt/user/appdata/filamenthub/data:/app/data \
  -v /mnt/user/appdata/filamenthub/logs:/app/logs \
  filamenthub
```

## 4. Webinterface öffnen
Rufe im Browser auf: [http://UNRAID-IP:8085](http://UNRAID-IP:8085)

## 5. Hinweise
- Die Volumes `/app/data` und `/app/logs` werden auf Unraid als persistente Ordner gemountet.
- Die Datei `entrypoint.sh` muss im Image vorhanden sein.
- Änderungen am Code erfordern ein erneutes Bauen des Images.

## 6. Optional: Docker Compose
Siehe Hauptanleitung für ein Compose-Beispiel.

## 7. Vorgehen für ein sauberes Rebuild (Compose)
Wenn du den Container immer neu und ohne Cache bauen willst:

```bash
# 1. Container stoppen
docker-compose down

# 2. Altes Image loeschen
docker rmi filamenthub:latest

# 3. Neues Image bauen (ohne Cache)
docker build --no-cache -t filamenthub .

# 4. Container starten
docker-compose up -d

# 5. Logs checken
docker-compose logs -f
```

