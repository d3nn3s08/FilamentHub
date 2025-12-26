#!/bin/bash
# FilamentHub Database Migration Fix Script
# This script fixes the "table already exists" error by stamping the existing database

set -e

echo "========================================="
echo "FilamentHub Database Migration Fix"
echo "========================================="

# Stop container
echo "1. Stopping FilamentHub container..."
docker-compose down

# Check if database exists
DB_PATH="/mnt/user/appdata/filamenthub/data/filamenthub.db"
if [ ! -f "$DB_PATH" ]; then
    echo "Database not found at $DB_PATH"
    echo "Starting fresh installation..."
    docker-compose up -d
    exit 0
fi

echo "2. Database found at $DB_PATH"

# Create temporary container to run alembic stamp
echo "3. Creating temporary container to stamp database..."
docker-compose run --rm --entrypoint /bin/sh filamenthub -c "
echo 'Checking database state...'
python -c \"
import os
from sqlalchemy import create_engine

db_path = '/app/data/filamenthub.db'
engine = create_engine(f'sqlite:///{db_path}')

with engine.begin() as conn:
    has_version = bool(conn.exec_driver_sql(
        \\\"SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'\\\"
    ).fetchone())
    has_material = bool(conn.exec_driver_sql(
        \\\"SELECT name FROM sqlite_master WHERE type='table' AND name='material'\\\"
    ).fetchone())

    print(f'Has alembic_version: {has_version}')
    print(f'Has material table: {has_material}')

    if not has_version and has_material:
        print('Need to stamp database')
        exit(2)
    elif has_version:
        print('Database already has version tracking')
        exit(0)
    else:
        print('Empty database')
        exit(0)
\"

DB_STATE=\$?

if [ \$DB_STATE -eq 2 ]; then
    echo 'Stamping database as head...'
    alembic stamp head
    echo 'Database stamped successfully!'
else
    echo 'Database state is OK, no stamping needed'
fi
"

echo "4. Starting FilamentHub..."
docker-compose up -d

echo "========================================="
echo "Fix complete! Checking logs..."
echo "========================================="
sleep 3
docker-compose logs --tail=50

echo ""
echo "If you see errors, run: docker-compose logs -f"
