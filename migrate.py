import sqlite3

conn = sqlite3.connect('road_damage.db')
c = conn.cursor()

new_cols = [
    ("complaints", "area_type", "VARCHAR(50) DEFAULT 'unknown'"),
    ("complaints", "nearby_places", "TEXT"),
    ("complaints", "image_hash", "VARCHAR(64)"),
    ("complaints", "damage_size_score", "REAL DEFAULT 0.0"),
    ("complaints", "traffic_density_score", "REAL DEFAULT 0.0"),
    ("complaints", "accident_risk_score", "REAL DEFAULT 0.0"),
    ("complaints", "area_criticality_score", "REAL DEFAULT 0.0"),
    ("complaints", "rainfall_score", "REAL DEFAULT 0.0"),
    ("complaints", "report_count", "INTEGER DEFAULT 1"),
    ("complaints", "is_verified", "BOOLEAN DEFAULT 0"),
    ("complaints", "fake_report_score", "REAL DEFAULT 0.0"),
    ("login_logs", "logout_at", "DATETIME"),
    ("login_logs", "session_duration_mins", "INTEGER"),
]

for table, col, coltype in new_cols:
    try:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
        print(f"OK: {table}.{col}")
    except Exception as e:
        print(f"Skip: {table}.{col} - {str(e)[:40]}")

# Create notifications table
try:
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        complaint_id VARCHAR(20),
        type VARCHAR(50),
        title VARCHAR(200),
        message TEXT,
        is_read BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    print("OK: notifications table")
except Exception as e:
    print(f"Skip notifications: {e}")

conn.commit()
conn.close()
print("Migration complete!")
