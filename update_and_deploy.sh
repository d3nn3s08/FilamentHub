#!/bin/bash
# FilamentHub - Update und Neu-Deployment
# Behält die Datenbank bei, updated nur den Code

set -e

echo "========================================="
echo "FilamentHub - Code Update & Deploy"
echo "========================================="
echo ""
echo "Dieses Script updated den FilamentHub Code"
echo "Die Datenbank bleibt erhalten."
echo ""

echo "1. Stoppe Container..."
docker-compose down

echo "2. Lösche altes Docker Image..."
docker rmi filamenthub:latest 2>/dev/null || echo "   Kein altes Image gefunden"

echo "3. Baue neues Image (ohne Cache)..."
docker build --no-cache -t filamenthub .

echo "4. Starte Container..."
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
echo ""
