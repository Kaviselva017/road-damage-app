import requests
import random
import os
import time
import hashlib
from typing import Dict, List

API_BASE = "http://127.0.0.1:8000/api"

# Test data generators
LOCATIONS = [
    (11.0168, 76.9558, "Town Hall, Coimbatore"),
    (13.0827, 80.2707, "Central Station, Chennai"),
    (12.9716, 77.5946, "MG Road, Bangalore"),
    (19.0760, 72.8777, "Gateway, Mumbai"),
]

DAMAGES = ["pothole", "crack", "surface_damage", "multiple"]
SENSITIVE = ["Hospital Area", "School Zone", "College Campus", "Main Highway", "Market Street", ""]

def create_fake_image(color=(255, 0, 0)):
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "uploads", "81da090e1a864842af48e408c043d284.jpg")
    with open(path, "rb") as f:
        return f.read() + os.urandom(10)

def run_unlimited_tests(count=20):
    print(f"🚀 Code Rabbit starting {count} unlimited test cases...")
    
    # 1. Register/Login as Citizen
    email = f"rabbit_{random.randint(1000, 9999)}@test.com"
    reg = requests.post(f"{API_BASE}/auth/register", json={
        "name": "Rabbit Bot", "email": email, "password": "password123"
    })
    if not reg.ok:
        print(f"❌ Failed to register: {reg.text}")
        return
    token = reg.json()['access_token']
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✅ Registered {email}")

    success_count = 0
    dups_count = 0
    errors = []

    latest_img = None
    for i in range(count):
        lat, lon, addr = random.choice(LOCATIONS)
        lat += random.uniform(-0.005, 0.005)
        lon += random.uniform(-0.005, 0.005)
        
        # Randomly decide if we send an existing image to test duplicate detection
        is_duplicate = random.random() < 0.2
        if is_duplicate and latest_img:
            img_bytes = latest_img
        else:
            img_bytes = create_fake_image()
            latest_img = img_bytes
        
        files = {"image": ("test.jpg", img_bytes, "image/jpeg")}
        data = {
            "latitude": str(lat),
            "longitude": str(lon),
            "address": addr,
            "nearby_sensitive": random.choice(SENSITIVE) if random.random() > 0.3 else ""
        }
        
        print(f"[{i+1}/{count}] Submitting report at {addr} ({data['nearby_sensitive'] or 'Regular'})...", end="")
        try:
            start = time.time()
            res = requests.post(f"{API_BASE}/complaints/submit", headers=headers, data=data, files=files, timeout=10)
            elapsed = time.time() - start
            
            if res.ok:
                d = res.json()
                if d.get("warning") == "duplicate":
                    print(f" (DUPLICATE) in {elapsed:.2f}s")
                    dups_count += 1
                else:
                    print(f" (SUCCESS: {d['complaint_id']} P{d['priority_score']}) in {elapsed:.2f}s")
                    success_count += 1
            else:
                print(f" (FAILED: {res.status_code})")
                errors.append(f"Case {i}: {res.status_code} - {res.text}")
        except Exception as e:
            print(f" (ERROR: {e})")
            errors.append(str(e))

    print("\n" + "="*40)
    print(f"📊 SUMMARY:")
    print(f"✅ Successes: {success_count}")
    print(f"♻️ Duplicates: {dups_count}")
    print(f"🔥 Failures:  {len(errors)}")
    
    if errors:
        print("\nTOP ERRORS:")
        for e in errors[:3]: print(f" - {e}")
    else:
        print("\n💎 ALL CODE RABBIT TESTS PASSED WITH 100% STABILITY")
    print("="*40)

if __name__ == "__main__":
    # Ensure server is running or at least attempt health check
    try:
        requests.get("http://127.0.0.1:8000/healthz", timeout=2)
        run_unlimited_tests(20)
    except Exception:
        print("❌ Server is NOT running at http://127.0.0.1:8000. Please start it first.")
