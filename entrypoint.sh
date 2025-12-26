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

# Run Alembic migrations with smart detection (if available)
if [ -f /app/alembic.ini ]; then
  echo "[entrypoint] Checking database state..."

  # Check if database has tables but no alembic_version
  python -c "
import os
from sqlalchemy import create_engine, text

db_path = os.environ.get('FILAMENTHUB_DB_PATH', '/app/data/filamenthub.db')
engine = create_engine(f'sqlite:///{db_path}')

with engine.begin() as conn:
    has_version = bool(conn.exec_driver_sql(
        \"SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'\"
    ).fetchone())
    has_material = bool(conn.exec_driver_sql(
        \"SELECT name FROM sqlite_master WHERE type='table' AND name='material'\"
    ).fetchone())

if not has_version and has_material:
    print('[entrypoint] Existing tables without alembic_version detected, stamping as head')
    exit(2)  # Signal to stamp
elif has_version:
    print('[entrypoint] alembic_version found, running upgrade')
    exit(0)  # Signal to upgrade
else:
    print('[entrypoint] Empty database, running upgrade')
    exit(0)  # Signal to upgrade
"

  DB_STATE=$?

  if [ $DB_STATE -eq 2 ]; then
    echo "[entrypoint] Stamping database as head..."
    alembic stamp head || { echo "[entrypoint] Alembic stamp failed"; exit 1; }
  else
    echo "[entrypoint] Running Alembic upgrade..."
    alembic upgrade head || { echo "[entrypoint] Alembic upgrade failed"; exit 1; }
  fi
else
  echo "[entrypoint] alembic.ini not found, skipping migrations"
fi

# Start the app
echo "[entrypoint] Starting FilamentHub..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8085 \
  --proxy-headers
