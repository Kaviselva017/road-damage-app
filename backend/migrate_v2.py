"""
Migration v2 — adds new columns safely without losing data
Run from: D:\python\road-damage-app\backend\
python ..\migrate_v2.py
"""
import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "road_damage.db")
if not os.path.exists(DB_PATH):
    DB_PATH = "road_damage.db"
if not os.path.exists(DB_PATH):
    print(f"ERROR: Cannot find road_damage.db. Run from D:\\python\\road-damage-app\\backend\\")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

migrations = [
    # Complaint table additions
    ("complaints", "area_type", "TEXT DEFAULT 'residential'"),
    ("complaints", "image_hash", "TEXT"),
    ("complaints", "report_count", "INTEGER DEFAULT 1"),
    ("complaints", "priority_score", "REAL DEFAULT 0.0"),
    ("complaints", "allocated_fund", "REAL DEFAULT 0.0"),
    ("complaints", "fund_note", "TEXT"),
    ("complaints", "fund_allocated_at", "DATETIME"),
    ("complaints", "is_duplicate", "BOOLEAN DEFAULT 0"),
    ("complaints", "duplicate_of", "TEXT"),
    ("complaints", "rainfall_mm", "REAL"),
    ("complaints", "traffic_volume", "TEXT"),
    ("complaints", "road_age_years", "INTEGER"),
    ("complaints", "weather_condition", "TEXT"),
    ("complaints", "resolved_at", "DATETIME"),
    # Officer additions
    ("field_officers", "last_login", "DATETIME"),
    # LoginLog additions
    ("login_logs", "logged_out_at", "DATETIME"),
    ("login_logs", "session_minutes", "INTEGER"),
]

# Get existing columns
def get_columns(table):
    try:
        cur.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cur.fetchall()]
    except:
        return []

added = 0
for table, col, col_def in migrations:
    existing = get_columns(table)
    if col not in existing:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            print(f"  ✅ Added {table}.{col}")
            added += 1
        except Exception as e:
            print(f"  ⚠️  {table}.{col}: {e}")
    else:
        print(f"  ✓  {table}.{col} already exists")

# Create notifications table
cur.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    complaint_id TEXT,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    is_read BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")
print("  ✅ notifications table ready")

# Recalculate priority scores for existing complaints
print("\nRecalculating priority scores for existing complaints...")
cur.execute("SELECT id, severity, damage_type, address FROM complaints WHERE priority_score IS NULL OR priority_score = 0")
rows = cur.fetchall()

def area_type_from_addr(addr):
    if not addr: return "residential"
    a = addr.lower()
    if any(w in a for w in ["hospital","clinic","medical","health"]): return "hospital"
    if any(w in a for w in ["school","college","university","academy"]): return "school"
    if any(w in a for w in ["highway","nh-","sh-","expressway"]): return "highway"
    if any(w in a for w in ["mall","market","shopping","commercial"]): return "market"
    return "residential"

def calc_priority(sev, dmg, area):
    ds = {"high":35,"medium":20,"low":10}.get(str(sev).split(".")[-1].lower(),10)
    tm = {"pothole":5,"multiple":8,"crack":3,"surface_damage":2}.get(str(dmg).split(".")[-1].lower(),0)
    ar = {"hospital":30,"school":25,"highway":25,"market":20,"residential":10}.get(area,10)
    tr = {"hospital":20,"school":18,"market":18,"highway":16,"residential":8}.get(area,8)
    rk = {"pothole":15,"multiple":14,"crack":8,"surface_damage":6}.get(str(dmg).split(".")[-1].lower(),6)
    return min(ds+tm+ar+tr+rk, 100)

for row_id, sev, dmg, addr in rows:
    area = area_type_from_addr(addr)
    score = calc_priority(sev, dmg, area)
    cur.execute("UPDATE complaints SET priority_score=?, area_type=?, report_count=1 WHERE id=?", (score, area, row_id))

print(f"  Updated {len(rows)} complaints with priority scores")

conn.commit()
conn.close()
print(f"\n✅ Migration complete! Added {added} new columns.")
print("Now restart: uvicorn app.main:app --reload")
