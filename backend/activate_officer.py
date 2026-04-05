import sqlite3
conn = sqlite3.connect('road_damage.db')
c = conn.cursor()
c.execute("UPDATE field_officers SET is_active=0 WHERE email NOT IN ('720823108017@hit.edu.in', 'admin@road.com')")
print(f"Deactivated {c.rowcount} officers.")
conn.commit()
conn.close()
