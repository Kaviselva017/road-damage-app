#!/usr/bin/env bash
set -e

echo "=== RoadWatch Startup ==="

echo "=== Reset Database ==="
rm -f road_damage.db

echo "=== Creating DB ==="
python -c "from app.database import Base, engine; import app.models.models; Base.metadata.create_all(bind=engine)"

echo "=== Seeding DB ==="
python seed.py

echo "=== Starting Server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
