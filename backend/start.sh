#!/bin/bash
set -e

cd /opt/render/project/src/backend

echo "=== RoadWatch Startup ==="

echo "[1/3] Running Alembic migrations..."
alembic upgrade head || alembic upgrade heads

echo "[1.5/3] Patching missing columns..."
python - <<'PYEOF'
import sqlite3, os, glob

# Find the actual DB file anywhere under /opt/render
candidates = glob.glob("/opt/render/**/*.db", recursive=True)
print(f"[patch] Found DB files: {candidates}")

# Also try the direct path
direct = "/opt/render/project/src/backend/road_damage.db"
if os.path.exists(direct):
    candidates = [direct] + [c for c in candidates if c != direct]

if not candidates:
    print("[patch] No .db file found, will be created fresh — skipping patch")
else:
    db_path = candidates[0]
    print(f"[patch] Using: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(field_officers)")
    cols = [row[1] for row in cur.fetchall()]
    print(f"[patch] field_officers columns: {cols}")

    if "last_login" not in cols:
        cur.execute("ALTER TABLE field_officers ADD COLUMN last_login DATETIME")
        conn.commit()
        print("[patch] Added last_login")
    else:
        print("[patch] last_login already exists")

    cur.execute("PRAGMA table_info(users)")
    ucols = [row[1] for row in cur.fetchall()]
    print(f"[patch] users columns: {ucols}")

    if "reward_points" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN reward_points INTEGER DEFAULT 0")
        conn.commit()
        print("[patch] Added reward_points")
    else:
        print("[patch] reward_points already exists")

    conn.close()
    print("[patch] Done")

PYEOF

echo "[2/3] Seeding default accounts..."
python seed.py

echo "[3/3] Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"