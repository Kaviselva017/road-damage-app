import os
import sys
import shutil

# Ensure we are in the backend directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 1. Clear existing DB
if os.path.exists("road_damage.db"):
    # Clear WAL files too
    for f in ["road_damage.db", "road_damage.db-wal", "road_damage.db-shm"]:
        if os.path.exists(f): os.remove(f)
    print("🧹 Database cleared.")

# 2. Re-create all tables with correct metadata
from app.database import Base, engine
from app.models.models import User, FieldOfficer, Complaint, Notification, Message, LoginLog, ComplaintOfficer
Base.metadata.create_all(bind=engine)
print("✅ Database schema re-created with ALL columns (phone, reward_points).")

# 3. Seed everything
import seed
seed.seed()
print("🏆 Core accounts seeded.")

# 4. Check results
import sqlite3
conn = sqlite3.connect("road_damage.db")
cursor = conn.execute("PRAGMA table_info(users)")
cols = [row[1] for row in cursor]
print(f"📊 Verified columns in 'users': {cols}")
if "phone" not in cols or "reward_points" not in cols:
    print("❌ ERROR: Missing columns!")
    sys.exit(1)

# 5. Run test runner
print("🚀 Launching AI Stress Test Suite...")
os.chdir("..")
# Note: we use python instead of npx/npm for the test runner
os.system("python unlimited_test_runner.py --iterations 3 --headless")
