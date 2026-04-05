import sqlite3
conn = sqlite3.connect('road_damage.db')
c = conn.cursor()
c.execute("UPDATE field_officers SET is_active=1")
print(f"Re-activated {c.rowcount} officers.")
conn.commit()
conn.close()
