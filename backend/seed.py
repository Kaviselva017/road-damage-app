"""
RoadWatch — Seed Script
Idempotent: safe to run on every deploy.
Creates default accounts only if they don't already exist.
Does NOT wipe existing data.

Run from backend/:
    python seed.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, SessionLocal, engine
from app.models.models import Complaint, FieldOfficer, User
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Default seed accounts ─────────────────────────────────────────

OFFICERS = [
    dict(email="admin@road.com",   name="Admin",       password="admin123",   phone="9999999999", zone="All Zones", is_admin=True),
    dict(email="officer@road.com", name="Test Officer", password="officer123", phone="8888888888", zone="Zone A",    is_admin=False),
]

CITIZENS = [
    dict(email="citizen@road.com", name="Test Citizen", password="citizen123", phone="7777777777"),
]


def _ensure_tables():
    """Create tables if they don't exist (idempotent)."""
    Base.metadata.create_all(bind=engine)


def _upsert_officer(db, data: dict) -> FieldOfficer:
    o = db.query(FieldOfficer).filter(FieldOfficer.email == data["email"]).first()
    if o is None:
        o = FieldOfficer(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            zone=data["zone"],
            hashed_password=pwd.hash(data["password"]),
            is_admin=data["is_admin"],
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(o)
        print(f"  [seed] Created officer: {data['email']}")
    else:
        # Always refresh password + admin flag so re-deploys don't lock out
        o.hashed_password = pwd.hash(data["password"])
        o.is_admin        = data["is_admin"]
        o.is_active       = True
        o.name            = data["name"]
        o.zone            = data["zone"]
        print(f"  [seed] Updated officer: {data['email']}")
    return o


def _upsert_citizen(db, data: dict) -> User:
    u = db.query(User).filter(User.email == data["email"]).first()
    if u is None:
        u = User(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            hashed_password=pwd.hash(data["password"]),
            is_active=True,
            reward_points=0,
            created_at=datetime.now(timezone.utc),
        )
        db.add(u)
        print(f"  [seed] Created citizen: {data['email']}")
    else:
        u.name    = data["name"]
        u.phone   = data["phone"]
        u.is_active = True
        print(f"  [seed] Updated citizen: {data['email']}")
    return u


def _seed_demo_complaint(db, citizen: User, officer: FieldOfficer):
    """Add one demo complaint only if it doesn't already exist."""
    if db.query(Complaint).filter(Complaint.complaint_id == "RD-DEMO-000001").first():
        return
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
        report_count   = 1,
        created_at     = datetime.now(timezone.utc),
    ))
    print("  [seed] Created demo complaint: RD-DEMO-000001")


def seed():
    print("[seed] Starting (idempotent)...")
    _ensure_tables()

    db = SessionLocal()
    try:
        officers  = {d["email"]: _upsert_officer(db, d) for d in OFFICERS}
        citizens  = {d["email"]: _upsert_citizen(db, d) for d in CITIZENS}
        db.flush()

        _seed_demo_complaint(
            db,
            citizen=citizens["citizen@road.com"],
            officer=officers["officer@road.com"],
        )

        db.commit()
        print("[seed] Done!")
        print()
        print("  Default accounts:")
        print("  Admin   : admin@road.com   / admin123")
        print("  Officer : officer@road.com / officer123")
        print("  Citizen : citizen@road.com / citizen123")
    except Exception as exc:
        db.rollback()
        print(f"[seed] ERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()