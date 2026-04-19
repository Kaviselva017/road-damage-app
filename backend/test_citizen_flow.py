import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.models import User

client = TestClient(app)

def main():
    print("=== Testing Citizen End-to-End Flow & Email Notifications ===")
    
    # 1. Clean up existing test user if it exists so we can register fresh
    db = SessionLocal()
    existing = db.query(User).filter(User.email == "studentofficial2002@gmail.com").first()
    if existing:
        from app.models.models import Notification, Complaint
        db.query(Notification).filter(Notification.user_id == existing.id).delete()
        db.query(Complaint).filter(Complaint.user_id == existing.id).delete()
        db.delete(existing)
        db.commit()
    db.close()
    
    # 2. Register New User (triggers Welcome Email)
    print("\n[Step 1] Registering user 'studentofficial2002@gmail.com'...")
    reg_res = client.post("/api/auth/register", json={
        "name": "Student Official",
        "email": "studentofficial2002@gmail.com",
        "phone": "9876543210",
        "password": "securepassword123"
    })
    
    if reg_res.status_code == 201:
        print("  ✅ User registered successfully. Welcome Email dispatched via BackgroundTasks in FastAPI.")
        token = reg_res.json()["access_token"]
    else:
        print(f"  ❌ Registration failed: {reg_res.text}")
        return

    # 3. Submit Complaint (triggers Complaint Submitted Email and Officer Assignment Email)
    print("\n[Step 2] User logging in and submitting a road damage complaint...")
    
    # We need a dummy image to upload
    test_img_path = backend_dir / "bad.jpg"
    
    # If bad.jpg doesn't exist, create a dummy transparent pixel image
    if not test_img_path.exists():
        from PIL import Image
        img = Image.new('RGB', (100, 100), color = 'gray')
        img.save(test_img_path, format="JPEG")
        
    with open(test_img_path, "rb") as f:
        comp_res = client.post(
            "/api/complaints/submit",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "latitude": "11.0180",
                "longitude": "76.9600",
                "address": "Student Area, Testing Road",
                "nearby_sensitive": "College Campus"
            },
            files={"image": ("test_road.jpg", f, "image/jpeg")}
        )
        
    if comp_res.status_code == 200:
        c_data = comp_res.json()
        print(f"  ✅ Complaint Submitted Successfully! ID: {c_data.get('complaint_id', 'DUPLICATE')}")
        print("  ✅ 'Complaint Registered' Email dispatched via BackgroundTasks.")
        if c_data.get('officer_name'):
            print(f"  ✅ 'Officer Assignment' Email dispatched to {c_data.get('officer_name')}")
    else:
        print(f"  ❌ Complaint submission failed: {comp_res.text}")

    print("\n=== End of Test ===")
    print("Please check the inbox for 'studentofficial2002@gmail.com'. You should see:")
    print("1. 'Welcome to RoadWatch!' email")
    print("2. 'Complaint Registered' email")

if __name__ == "__main__":
    main()
