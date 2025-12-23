#!/bin/sh
set -e

# Defaults
export FILAMENTHUB_DB_PATH="${FILAMENTHUB_DB_PATH:-/app/data/filamenthub.db}"
export PYTHONPATH="${PYTHONPATH:-/app}"

echo "[entrypoint] DB_PATH=${FILAMENTHUB_DB_PATH}"

# Ensure directories exist
mkdir -p "$(dirname "$FILAMENTHUB_DB_PATH")" /app/logs /app/app/logging

# Verify Python module structure
echo "[entrypoint] Verifying Python modules..."
python -c "from app.logging.runtime import reconfigure_logging; print('[entrypoint] ✓ app.logging module OK')" || {
  echo "[entrypoint] ERROR: app.logging module not found!"
  echo "[entrypoint] PYTHONPATH=$PYTHONPATH"
  echo "[entrypoint] Directory structure:"
  ls -la /app/app/ || true
  ls -la /app/app/logging/ || true
  exit 1
}

# Run Alembic migrations (if available)
if [ -f /app/alembic.ini ]; then
  echo "[entrypoint] Running Alembic migrations..."
  alembic upgrade head || { echo "[entrypoint] Alembic failed"; exit 1; }
else
  echo "[entrypoint] alembic.ini not found, skipping migrations"
fi

# Start the app
echo "[entrypoint] Starting FilamentHub..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8085 \
  --proxy-headers
