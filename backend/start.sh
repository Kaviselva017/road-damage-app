#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8000}"

echo "==> Running Alembic migrations..."
python -m alembic -c alembic.ini upgrade head
echo "==> Migrations complete"

echo "==> Running seed..."
python seed.py || echo "Seed skipped"

echo "==> Starting server on port $PORT..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"