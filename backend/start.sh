#!/bin/bash
set -e

cd /opt/render/project/src/backend

echo "[start] Setting up database..."

# Remove stale SQLite DB so models are recreated fresh (fixes missing column errors)
if [ -f "road_damage.db" ]; then
    echo "[start] Removing stale road_damage.db to apply schema changes..."
    rm -f road_damage.db
fi

echo "[start] Running Alembic migrations..."
alembic upgrade head

echo "[start] Seeding database..."
python seed.py

echo "[start] Starting server..."
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"