import sqlite3
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
db_path = "road_damage.db"

name = "HIT Maintenance Unit"
email = "720823108017@hit.edu.in"
password = "password123"
zone = "Zone A"

hashed = pwd_ctx.hash(password)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if exists
    cursor.execute("SELECT id FROM field_officers WHERE email = ?", (email,))
    if cursor.fetchone():
        print(f"Officer with email {email} already exists.")
    else:
        cursor.execute("""
            INSERT INTO field_officers (name, email, hashed_password, zone, is_admin, is_active, created_at)
            VALUES (?, ?, ?, ?, 0, 1, CURRENT_TIMESTAMP)
        """, (name, email, hashed, zone))
        conn.commit()
        print(f"Success! Officer {email} created with password: {password}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
