#!/bin/bash
# FilamentHub - Vollständiger Rebuild (ohne Datenbank-Reset)
# Löscht altes Image und baut komplett neu

set -e

echo "========================================="
echo "FilamentHub - Complete Rebuild"
echo "========================================="
echo ""

echo "1. Stoppe Container..."
docker-compose down

echo "2. Lösche altes Image..."
docker rmi filamenthub:latest 2>/dev/null || echo "   Kein altes Image gefunden"

echo "3. Baue neues Image (ohne Cache)..."
docker build --no-cache -t filamenthub .

echo "4. Starte Container..."
docker-compose up -d

echo ""
echo "========================================="
echo "Rebuild abgeschlossen!"
echo "========================================="
echo ""
echo "Container läuft jetzt mit neuem Image."
echo ""
echo "Nützliche Befehle:"
echo "  docker-compose logs -f       # Logs anzeigen"
echo "  docker-compose ps            # Status prüfen"
echo "  curl http://localhost:8085/health  # Health Check"
echo ""
echo "App öffnen: http://localhost:8085"
echo ""
