"""
RoadWatch — Seed Script
Standalone: creates tables + default accounts.
Safe to run multiple times (idempotent).
Run from: backend/
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force DB tables to exist
from app.database import Base, engine, SessionLocal
Base.metadata.create_all(bind=engine)

from app.models.models import Complaint, FieldOfficer, User
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upsert_officer(db, email, name, password, phone, zone, is_admin):
    o = db.query(FieldOfficer).filter(FieldOfficer.email == email).first()
    if o is None:
        o = FieldOfficer(
            name=name, email=email, phone=phone, zone=zone,
            hashed_password=pwd.hash(password),
            is_admin=is_admin, is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(o)
        print(f"  [seed] Created: {email}")
    else:
        o.name=name; o.phone=phone; o.zone=zone
        o.is_admin=is_admin; o.is_active=True
        o.hashed_password=pwd.hash(password)  # reset password each deploy
        print(f"  [seed] Updated: {email}")
    return o


def upsert_user(db, email, name, password, phone):
    u = db.query(User).filter(User.email == email).first()
    if u is None:
        u = User(
            name=name, email=email, phone=phone,
            hashed_password=pwd.hash(password),
            is_active=True, reward_points=0,
            created_at=datetime.utcnow(),
        )
        db.add(u)
        print(f"  [seed] Created: {email}")
    else:
        u.name=name; u.phone=phone; u.is_active=True
        print(f"  [seed] Updated: {email}")
    return u


def seed():
    print("[seed] Starting...")
    db = SessionLocal()
    try:
        admin   = upsert_officer(db, "admin@road.com",   "Admin",       "admin123",   "9999999999", "All Zones", True)
        officer = upsert_officer(db, "officer@road.com", "Test Officer", "officer123", "8888888888", "Zone A",    False)
        citizen = upsert_user(   db, "citizen@road.com", "Test Citizen", "citizen123", "7777777777")
        db.flush()

        # Demo complaint only if officer has none assigned
        if officer.id and citizen.id:
            existing = db.query(Complaint).filter(Complaint.complaint_id == "RD-DEMO-000001").first()
            if existing is None:
                db.add(Complaint(
                    complaint_id   = "RD-DEMO-000001",
                    user_id        = citizen.id,
                    officer_id     = officer.id,
                    latitude       = 11.0168,
                    longitude      = 76.9558,
                    address        = "Town Hall Road, Coimbatore, Tamil Nadu",
                    area_type      = "market",
                    damage_type    = "pothole",
                    severity       = "medium",
                    ai_confidence  = 0.86,
                    description    = "Demo pothole — medium severity, market zone.",
                    image_url      = "",
                    status         = "assigned",
                    priority_score = 65.0,
                    allocated_fund = 0.0,
                    is_duplicate   = False,
                    created_at     = datetime.utcnow(),
                ))
                print("  [seed] Created demo complaint: RD-DEMO-000001")

        db.commit()
        print("[seed] Done!")
        print("")
        print("  Default accounts:")
        print("  Admin   : admin@road.com   / admin123")
        print("  Officer : officer@road.com / officer123")
        print("  Citizen : citizen@road.com / citizen123")
    except Exception as e:
        db.rollback()
        print(f"[seed] ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()