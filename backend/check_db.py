import sqlite3
conn = sqlite3.connect('road_damage.db')
c = conn.cursor()
c.execute("SELECT id, complaint_id, image_hash, status, report_count FROM complaints ORDER BY id DESC LIMIT 5")
rows = c.fetchall()
for r in rows:
    print(r)
conn.close()
