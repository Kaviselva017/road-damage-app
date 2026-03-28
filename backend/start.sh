#!/bin/bash
set -e

cd /opt/render/project/src/backend

echo "=== RoadWatch Startup ==="

echo "[0/3] Clearing stale database..."
# Delete ALL .db files so schema is always recreated fresh
find /opt/render -name "*.db" -delete 2>/dev/null && echo "[init] Deleted stale .db files" || echo "[init] No .db files found"
rm -f road_damage.db ./road_damage.db 2>/dev/null || true

echo "[1/3] Running Alembic migrations..."
alembic upgrade head || alembic upgrade heads

echo "[2/3] Seeding default accounts..."
python seed.py

echo "[3/3] Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"