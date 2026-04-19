import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend directory to sys.path so we can import 'app'
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from passlib.context import CryptContext

from app.database import SessionLocal
from app.models.models import FieldOfficer
from app.services.notification_service import notify_officer_assignment

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _now():
    return datetime.now(timezone.utc)

def main():
    print("=== Creating Zone Officers & Testing Notification ===")
    db = SessionLocal()
    
    officers_data = [
        {"name": "Officer Zone A", "email": "720823108017@hit.edu.in", "zone": "Zone A"},
        {"name": "Officer Zone B", "email": "720823108003@hit.edu.in", "zone": "Zone B"},
        {"name": "Officer Zone C", "email": "720823108009@hit.edu.in", "zone": "Zone C"},
        {"name": "Officer Zone D", "email": "720823108025@hit.edu.in", "zone": "Zone D"},
    ]
    
    officers = []
    
    try:
        for data in officers_data:
            officer = db.query(FieldOfficer).filter(FieldOfficer.email == data["email"]).first()
            if not officer:
                print(f"Creating new officer: {data['email']} for {data['zone']}")
                officer = FieldOfficer(
                    name=data["name"],
                    email=data["email"],
                    hashed_password=pwd_ctx.hash("officer123"),
                    phone="1234567890",
                    zone=data["zone"],
                    is_admin=False,
                    is_active=True,
                )
                db.add(officer)
            else:
                print(f"Updating existing officer: {data['email']} for {data['zone']}")
                officer.name = data["name"]
                officer.zone = data["zone"]
                officer.is_active = True
                officer.hashed_password = pwd_ctx.hash("officer123")
                
            db.commit()
            db.refresh(officer)
            officers.append(officer)
            
        print("\n=== All 4 Officers provisioned in Database! ===")
        print("Now triggering test notification emails...\n")
        
        success_count = 0
        for off in officers:
            print(f"Sending test email assignment to {off.email}...")
            # Trigger real email notification test
            result = notify_officer_assignment(
                to_email=off.email,
                officer_name=off.name,
                complaint_id=f"TEST-RD-{off.zone[-1]}",
                damage_type="severe_pothole",
                severity="high",
                priority_score=95.0,
                area_type="residential",
                location=f"Demo Location {off.zone}",
                coords="11.0168, 76.9558",
                image_url="https://res.cloudinary.com/demo/image/upload/road_pothole.jpg.jpg",
                notes=f"This is a LIVE EMAIL VERIFICATION TEST for {off.zone}",
                nearby_places="Nearby Test School, Local Test Clinic"
            )
            
            if result:
                print(f"  [SUCCESS] Email sent successfully to {off.email}")
                success_count += 1
            else:
                print(f"  [FAILED] Failed to send email to {off.email}. Check SMTP credentials.")
                
        print(f"\nTest Summary: {success_count}/4 emails sent successfully to the provided addresses.")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
