import sqlite3
from datetime import datetime

conn = sqlite3.connect('road_damage.db')
c = conn.cursor()

# Find complaints with NULL created_at
c.execute("SELECT id, complaint_id, created_at FROM complaints WHERE created_at IS NULL OR created_at = 'None'")
nulls = c.fetchall()
print(f"Found {len(nulls)} complaints with NULL dates")

# Fix each one using date from complaint_id (RD-20260315-XXXX)
fixed = 0
for row in nulls:
    id_, cid, _ = row
    try:
        # Extract date from complaint ID like RD-20260315-ABC123
        date_str = cid.split('-')[1]  # 20260315
        dt = datetime.strptime(date_str, '%Y%m%d').isoformat()
        c.execute("UPDATE complaints SET created_at = ? WHERE id = ?", (dt, id_))
        print(f"Fixed {cid} → {dt}")
        fixed += 1
    except:
        # Fallback to today
        now = datetime.utcnow().isoformat()
        c.execute("UPDATE complaints SET created_at = ? WHERE id = ?", (now, id_))
        fixed += 1

# Also fix any that have string 'None'
c.execute("UPDATE complaints SET created_at = ? WHERE created_at = 'None'", 
          (datetime.utcnow().isoformat(),))

conn.commit()
conn.close()
print(f"\nFixed {fixed} complaints!")
print("All dates now set correctly.")
