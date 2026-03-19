"""
Seed default admin and test users on startup.
Run from backend/ folder.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, SessionLocal
from app.models.models import User, FieldOfficer
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Seed Admin (officer with zone="All Zones")
    if not db.query(FieldOfficer).filter(FieldOfficer.email == "admin@road.com").first():
        db.add(FieldOfficer(
            name="Admin",
            email="admin@road.com",
            hashed_password=pwd_context.hash("admin123"),
            phone="9999999999",
            zone="All Zones",
            is_active=True
        ))
        print("✅ Admin created: admin@road.com / admin123")

    # Seed test officer
    if not db.query(FieldOfficer).filter(FieldOfficer.email == "officer@road.com").first():
        db.add(FieldOfficer(
            name="Test Officer",
            email="officer@road.com",
            hashed_password=pwd_context.hash("officer123"),
            phone="8888888888",
            zone="Zone A",
            is_active=True
        ))
        print("✅ Officer created: officer@road.com / officer123")

    # Seed test citizen
    if not db.query(User).filter(User.email == "citizen@road.com").first():
        db.add(User(
            name="Test Citizen",
            email="citizen@road.com",
            hashed_password=pwd_context.hash("citizen123"),
            phone="7777777777",
            is_active=True
        ))
        print("✅ Citizen created: citizen@road.com / citizen123")

    db.commit()
    db.close()
    print("✅ Seeding complete!")

if __name__ == "__main__":
    seed()
