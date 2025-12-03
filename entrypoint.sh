#!/bin/sh
set -e

# Defaults
export FILAMENTHUB_DB_PATH="${FILAMENTHUB_DB_PATH:-/app/data/filamenthub.db}"
export PYTHONPATH="${PYTHONPATH:-/app}"

echo "[entrypoint] DB_PATH=${FILAMENTHUB_DB_PATH}"

# Ensure directories exist
mkdir -p "$(dirname "$FILAMENTHUB_DB_PATH")" /app/logs

# Run Alembic migrations (if available)
if [ -f /app/alembic.ini ]; then
  echo "[entrypoint] Running Alembic migrations..."
  alembic upgrade head || { echo "[entrypoint] Alembic failed"; exit 1; }
else
  echo "[entrypoint] alembic.ini not found, skipping migrations"
fi

# Start the app
exec python run.py
