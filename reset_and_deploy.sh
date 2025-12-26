#!/bin/bash
# FilamentHub - Reset Database und Neu-Deployment
# WARNUNG: Löscht alle Daten in der Datenbank!

set -e

echo "========================================="
echo "FilamentHub - Database Reset & Deploy"
echo "========================================="
echo ""
echo "WARNUNG: Dieses Script löscht die bestehende Datenbank!"
echo "Alle Drucker, Spulen, Jobs werden gelöscht."
echo ""
read -p "Fortfahren? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Abgebrochen."
    exit 1
fi

echo ""
echo "1. Stoppe Container..."
docker-compose down

echo "2. Backup der alten Datenbank erstellen..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_PATH="/mnt/user/appdata/filamenthub/data/filamenthub.db"

if [ -f "$DB_PATH" ]; then
    BACKUP_PATH="/mnt/user/appdata/filamenthub/data/filamenthub_backup_${TIMESTAMP}.db"
    cp "$DB_PATH" "$BACKUP_PATH"
    echo "   Backup erstellt: $BACKUP_PATH"

    echo "3. Lösche alte Datenbank..."
    rm "$DB_PATH"
    echo "   Datenbank gelöscht"
else
    echo "   Keine Datenbank gefunden (erste Installation)"
fi

echo "4. Lösche altes Docker Image..."
docker rmi filamenthub 2>/dev/null || echo "   Kein altes Image gefunden"

echo "5. Baue neues Image (ohne Cache)..."
docker-compose build --no-cache

echo "6. Starte Container..."
docker-compose up -d

echo ""
echo "========================================="
echo "Deployment abgeschlossen!"
echo "========================================="
echo ""
echo "Logs anzeigen mit: docker-compose logs -f"
echo "Status prüfen mit: docker-compose ps"
echo "Health Check mit: curl http://localhost:8085/health"
echo ""
echo "Admin Login:"
echo "  URL: http://$(hostname -I | awk '{print $1}'):8085/admin"
echo "  Passwort: Lucy22032021"
echo ""
