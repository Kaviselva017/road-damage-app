"""
Seed default admin and test users on startup.
Run from backend/ folder.
"""
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from passlib.context import CryptContext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.models import Complaint, ComplaintStatus, DamageType, FieldOfficer, SeverityLevel, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
BASE_DIR = Path(__file__).resolve().parent


def seed():
    alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    db = SessionLocal()

    admin = db.query(FieldOfficer).filter(FieldOfficer.email == "admin@road.com").first()
    if admin is None:
        admin = FieldOfficer(
            name="Admin",
            email="admin@road.com",
            hashed_password=pwd_context.hash("admin123"),
            phone="9999999999",
            zone="All Zones",
            is_admin=True,
            is_active=True,
        )
        db.add(admin)
        print("Admin created: admin@road.com / admin123")
    else:
        admin.name = "Admin"
        admin.phone = "9999999999"
        admin.zone = "All Zones"
        admin.is_admin = True
        admin.is_active = True

    officer = db.query(FieldOfficer).filter(FieldOfficer.email == "officer@road.com").first()
    if officer is None:
        officer = FieldOfficer(
            name="Test Officer",
            email="officer@road.com",
            hashed_password=pwd_context.hash("officer123"),
            phone="8888888888",
            zone="Zone A",
            is_admin=False,
            is_active=True,
        )
        db.add(officer)
        print("Officer created: officer@road.com / officer123")
    else:
        officer.name = "Test Officer"
        officer.phone = "8888888888"
        officer.zone = "Zone A"
        officer.is_admin = False
        officer.is_active = True

    if not db.query(User).filter(User.email == "citizen@road.com").first():
        db.add(User(
            name="Test Citizen",
            email="citizen@road.com",
            hashed_password=pwd_context.hash("citizen123"),
            phone="7777777777",
            is_active=True
        ))
        print("Citizen created: citizen@road.com / citizen123")

    citizen = db.query(User).filter(User.email == "citizen@road.com").first()
    if citizen is not None:
        citizen.name = "Test Citizen"
        citizen.phone = "7777777777"
        citizen.is_active = True

    db.flush()

    officer_assigned_count = 0
    if officer.id is not None:
        officer_assigned_count = db.query(Complaint).filter(Complaint.officer_id == officer.id).count()

    if citizen is not None and officer_assigned_count == 0:
        demo_complaint = db.query(Complaint).filter(Complaint.complaint_id == "RD-DEMO-000001").first()
        if demo_complaint is None:
            demo_complaint = Complaint(
                complaint_id="RD-DEMO-000001",
                user_id=citizen.id,
                officer_id=officer.id,
                latitude=11.0168,
                longitude=76.9558,
                address="Town Hall Road, Coimbatore, Tamil Nadu",
                area_type="market",
                damage_type=DamageType.POTHOLE,
                severity=SeverityLevel.MEDIUM,
                ai_confidence=0.86,
                description="Demo pothole complaint for the default officer dashboard.",
                image_url="",
                status=ComplaintStatus.ASSIGNED,
                priority_score=6.5,
                allocated_fund=0.0,
                is_duplicate=False,
            )
            db.add(demo_complaint)
            print("Demo complaint created for officer@road.com")
        else:
            demo_complaint.user_id = citizen.id
            demo_complaint.officer_id = officer.id
            demo_complaint.address = "Town Hall Road, Coimbatore, Tamil Nadu"
            demo_complaint.latitude = 11.0168
            demo_complaint.longitude = 76.9558
            demo_complaint.area_type = "market"
            demo_complaint.damage_type = DamageType.POTHOLE
            demo_complaint.severity = SeverityLevel.MEDIUM
            demo_complaint.ai_confidence = 0.86
            demo_complaint.description = "Demo pothole complaint for the default officer dashboard."
            demo_complaint.image_url = ""
            demo_complaint.status = ComplaintStatus.ASSIGNED
            demo_complaint.priority_score = 6.5
            demo_complaint.allocated_fund = 0.0
            demo_complaint.is_duplicate = False

    db.commit()
    db.close()
    print("Seeding complete!")


if __name__ == "__main__":
    seed()
