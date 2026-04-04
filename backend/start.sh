#!/usr/bin/env bash
# RoadWatch — backend startup
# Safe for Render & Docker: runs alembic migrations, seeds if needed, then starts uvicorn.
# Does NOT wipe the database — data persists across restarts.
set -euo pipefail

echo "=== RoadWatch Startup ==="
echo "  Working dir : $(pwd)"
echo "  Python      : $(python --version)"

# ── 1. Run database migrations ────────────────────────────────────
echo "=== Running Alembic migrations ==="
python -m alembic -c alembic.ini upgrade head

# ── 2. Seed default accounts (idempotent — safe to re-run) ───────
echo "=== Seeding default accounts ==="
python seed.py

# ── 3. Start the server ───────────────────────────────────────────
echo "=== Starting uvicorn on port ${PORT:-10000} ==="
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-10000}" \
  --workers 1 \
  --log-level info