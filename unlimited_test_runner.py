import requests
import random
import os
import time
import hashlib
from typing import Dict, List

API_BASE = "http://localhost:8000/api"

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
    from PIL import Image
    import io
    img = Image.new('RGB', (100, 100), color=color)
    # Add some noise to make it look unique (prevents duplicate hash)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.point((random.randint(0,99), random.randint(0,99)), fill=(255,255,255))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()

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

    for i in range(count):
        lat, lon, addr = random.choice(LOCATIONS)
        lat += random.uniform(-0.005, 0.005)
        lon += random.uniform(-0.005, 0.005)
        
        # Randomly decide if we send an existing image to test duplicate detection
        is_duplicate = random.random() < 0.2
        img_bytes = b"fake-repeat" if is_duplicate else create_fake_image((random.randint(0,255), 0, 0))
        
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
        requests.get("http://localhost:8000/healthz", timeout=2)
        run_unlimited_tests(20)
    except Exception:
        print("❌ Server is NOT running at http://localhost:8000. Please start it first.")
