import sqlite3
conn = sqlite3.connect('road_damage.db')
c = conn.cursor()
c.execute("DELETE FROM complaints WHERE complaint_id LIKE 'RD-20260405%'")
print(f"Deleted {c.rowcount} complaints from today.")
conn.commit()
conn.close()
