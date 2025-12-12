#!/usr/bin/env bash
set -euo pipefail

# Zentrales Setup-Skript für Linux/Pi
# - venv erstellen/aktivieren
# - requirements installieren
# - Ordner data, logs, data/backups anlegen
# - Alembic Migrationen ausführen

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

echo "== FilamentHub Setup (Linux/Pi) =="
echo "Projektpfad: $PROJECT_ROOT"

mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/logs" "$PROJECT_ROOT/data/backups"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo ".venv nicht gefunden – erstelle virtuelles Environment..."
  python3 -m venv "$VENV_DIR"
fi

echo "Installiere requirements.txt..."
"$PYTHON_BIN" -m pip install --upgrade pip >/dev/null
"$PYTHON_BIN" -m pip install -r "$PROJECT_ROOT/requirements.txt"

echo "Führe alembic upgrade head aus..."
FILAMENTHUB_DB_PATH="$PROJECT_ROOT/data/filamenthub.db" \
  "$PYTHON_BIN" -m alembic upgrade head

echo "Setup fertig. DB-Pfad: $PROJECT_ROOT/data/filamenthub.db"
