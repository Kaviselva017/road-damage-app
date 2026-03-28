#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8000}"

echo "=== RoadWatch Startup ==="
echo "[1/3] Running Alembic migrations..."
python -m alembic -c alembic.ini upgrade head || echo "[WARN] Alembic failed — tables will be created by SQLAlchemy"

echo "[2/3] Seeding default accounts..."
python seed.py

echo "[3/3] Starting server on port $PORT..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"