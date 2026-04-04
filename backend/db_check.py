import os
from sqlalchemy import text
from app.database import SessionLocal, engine, Base

print("Checking DATABASE_URL...")
print(f"URL: {os.getenv('DATABASE_URL')}")

try:
    print("Testing connection...")
    with engine.connect() as conn:
        print("Connected!")
        res = conn.execute(text("SELECT 1"))
        print(f"Result: {res.fetchone()}")
except Exception as e:
    print(f"Connection failed: {e}")

try:
    print("Testing SessionLocal...")
    db = SessionLocal()
    db.execute(text("SELECT 1"))
    print("Session OK!")
    db.close()
except Exception as e:
    print(f"Session failed: {e}")
