#!/usr/bin/env bash
set -e

echo "=== RoadWatch Startup ==="

echo "=== Creating DB ==="
python -c "from app.database import Base, engine; import app.models.models; Base.metadata.create_all(bind=engine)"

echo "=== Seeding DB ==="
python seed.py

echo "=== Starting Server ==="
uvicorn app.main:app --host 0.0.0.0 --port 10000