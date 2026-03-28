#!/usr/bin/env bash
set -e

echo "=== RoadWatch Startup ==="

# 🚨 FORCE DELETE OLD DB (VERY IMPORTANT)
echo "=== Reset Database ==="
rm -f road_damage.db

# Create fresh tables
echo "=== Creating DB ==="
python -c "from app.database import Base, engine; import app.models.models; Base.metadata.create_all(bind=engine)"

# Seed data
echo "=== Seeding DB ==="
python seed.py

# Start server
echo "=== Starting Server ==="
uvicorn app.main:app --host 0.0.0.0 --port 10000