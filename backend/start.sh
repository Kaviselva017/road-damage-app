#!/bin/bash
set -e

cd /opt/render/project/src/backend

echo "=== RoadWatch Startup ==="

echo "[1/3] Running Alembic migrations..."
alembic upgrade head || alembic upgrade heads

echo "[1.5/3] Patching missing columns..."
python - <<'PYEOF'
import sqlite3, os

db_path = os.getenv("DATABASE_URL", "sqlite:///./road_damage.db")
db_path = db_path.replace("sqlite:///./", "").replace("sqlite:///", "").replace("sqlite://", "")
if not os.path.isabs(db_path):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)

print(f"[patch] DB path: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(field_officers)")
    cols = [row[1] for row in cur.fetchall()]
    print(f"[patch] Existing columns: {cols}")

    if "last_login" not in cols:
        cur.execute("ALTER TABLE field_officers ADD COLUMN last_login DATETIME")
        conn.commit()
        print("[patch] Added last_login column")
    else:
        print("[patch] last_login already exists")

    conn.close()
except Exception as e:
    print(f"[patch] ERROR: {e}")

PYEOF

echo "[2/3] Seeding default accounts..."
python seed.py

echo "[3/3] Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"