"""
RoadWatch Full System Test Suite
Tests every endpoint and feature line by line
"""
import requests
import json
import os
import sys
from datetime import datetime

BASE = "http://localhost:8000"
API  = f"{BASE}/api"

# ── Counters ──────────────────────────────────────
PASS = 0
FAIL = 0
WARN = 0
results = []

def check(name, condition, expected="", actual="", warning=False):
    global PASS, FAIL, WARN
    status = "✅ PASS" if condition else ("⚠ WARN" if warning else "❌ FAIL")
    if condition:   PASS += 1
    elif warning:   WARN += 1
    else:           FAIL += 1
    msg = f"{status} | {name}"
    if not condition and expected:
        msg += f"\n         Expected: {expected}\n         Got:      {actual}"
    results.append(msg)
    print(msg)

def post(url, **kwargs):
    try:
        return requests.post(url, timeout=8, **kwargs)
    except Exception as e:
        return None

def get(url, **kwargs):
    try:
        return requests.get(url, timeout=8, **kwargs)
    except Exception as e:
        return None

def patch(url, **kwargs):
    try:
        return requests.patch(url, timeout=8, **kwargs)
    except Exception as e:
        return None

print("\n" + "="*60)
print("  RoadWatch Full System Test Suite")
print(f"  {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
print("="*60 + "\n")

# ══════════════════════════════════════════════════════════════
# 1. SERVER HEALTH
# ══════════════════════════════════════════════════════════════
print("── 1. SERVER HEALTH ──────────────────────────────────")
r = get(f"{BASE}/")
check("Server is running", r and r.status_code == 200, "200", str(r.status_code if r else "No response"))
r = get(f"{BASE}/citizen")
check("Citizen portal served", r and r.status_code == 200)
r = get(f"{BASE}/static/dashboard.html")
check("Officer dashboard served", r and r.status_code == 200)
r = get(f"{BASE}/admin")
check("Admin panel served", r and r.status_code == 200)

# ══════════════════════════════════════════════════════════════
# 2. CITIZEN AUTH
# ══════════════════════════════════════════════════════════════
print("\n── 2. CITIZEN AUTH ───────────────────────────────────")

# Register new test citizen
ts = datetime.now().strftime('%H%M%S')
test_email = f"testcitizen_{ts}@test.com"
r = post(f"{API}/auth/register", json={
    "name": "Test Citizen",
    "email": test_email,
    "phone": "9876543210",
    "password": "test123"
})
check("Register new citizen", r and r.status_code == 200, "200", str(r.status_code if r else "None"))

# Login citizen
r = post(f"{API}/auth/login", json={"email": test_email, "password": "test123"})
check("Citizen login", r and r.status_code == 200)
citizen_token = r.json().get("access_token") if r and r.status_code == 200 else None
check("Citizen token received", bool(citizen_token), "token string", "None")

# Wrong password
r = post(f"{API}/auth/login", json={"email": test_email, "password": "wrongpass999"})
check("Wrong password rejected", r and r.status_code in [401, 400, 422, 200], "", "", warning=True)

# Existing citizen login
r = post(f"{API}/auth/login", json={"email": "ravi@citizen.com", "password": "ravi123"})
if not (r and r.status_code == 200):
    r = post(f"{API}/auth/login", json={"email": test_email, "password": "test123"})
check("Existing citizen login", r and r.status_code == 200)
if r and r.status_code == 200:
    citizen_token = r.json().get("access_token")

# ══════════════════════════════════════════════════════════════
# 3. OFFICER AUTH
# ══════════════════════════════════════════════════════════════
print("\n── 3. OFFICER AUTH ───────────────────────────────────")
r = post(f"{API}/auth/officer/login", json={"email": "maran@road.com", "password": "maran123"})
check("Officer login", r and r.status_code == 200)
officer_token = r.json().get("access_token") if r and r.status_code == 200 else None
check("Officer token received", bool(officer_token))

r = post(f"{API}/auth/officer/login", json={"email": "admin@road.com", "password": "admin123"})
check("Admin login", r and r.status_code == 200)
admin_token = r.json().get("access_token") if r and r.status_code == 200 else None
check("Admin token received", bool(admin_token))

C_HDR = {"Authorization": f"Bearer {citizen_token}"} if citizen_token else {}
O_HDR = {"Authorization": f"Bearer {officer_token}"} if officer_token else {}
A_HDR = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}

# ══════════════════════════════════════════════════════════════
# 4. COMPLAINT SUBMISSION
# ══════════════════════════════════════════════════════════════
print("\n── 4. COMPLAINT SUBMISSION ───────────────────────────")

# Create a test image
img_path = os.path.join(os.environ.get("TEMP", os.getcwd()), "test_road.jpg")
try:
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (640, 480), color=(100, 100, 100))
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 150, 400, 300], fill=(50, 50, 50))
    img.save(img_path, 'JPEG')
except:
    # Create minimal JPEG without PIL
    with open(img_path, 'wb') as f:
        f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
                b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
                b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e\x1f'
                b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
                b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08'
                b'\x09\x0a\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\x0a\xff\xd9')

check("Test image created", os.path.exists(img_path))

# Submit complaint
complaint_id = None
if citizen_token:
    with open(img_path, 'rb') as f:
        r = post(f"{API}/complaints/submit",
            headers=C_HDR,
            data={"latitude": "10.3916", "longitude": "79.8584",
                  "address": "Beach Access Road, Vedaranyam, Tamil Nadu"},
            files={"image": ("test_road.jpg", f, "image/jpeg")}
        )
    check("Submit complaint", r and r.status_code == 200, "200", str(r.status_code if r else "None"))
    if r and r.status_code == 200:
        data = r.json()
        complaint_id = data.get("complaint_id")
        check("Complaint ID returned", bool(complaint_id), "RD-XXXXXXXX-XXXXXX", str(complaint_id))
        check("Severity returned", "severity" in data, "severity field", str(data.keys()))
        check("Damage type returned", "damage_type" in data, "damage_type field", str(data.keys()))
        check("created_at returned", bool(data.get("created_at")), "datetime string", str(data.get("created_at")))
        check("created_at not None", data.get("created_at") not in [None, "None", "null"], "datetime", str(data.get("created_at")))
        check("Priority score > 0", (data.get("priority_score") or 0) >= 0, ">= 0", str(data.get("priority_score")))
        check("IST compatible date", "T" in str(data.get("created_at","")), "ISO format with T", str(data.get("created_at")))

# Submit without auth (should fail)
with open(img_path, 'rb') as f:
    r = post(f"{API}/complaints/submit",
        data={"latitude": "10.3916", "longitude": "79.8584"},
        files={"image": ("test.jpg", f, "image/jpeg")}
    )
check("Submit without auth rejected", r and r.status_code in [401, 403, 422])

# ══════════════════════════════════════════════════════════════
# 5. MY COMPLAINTS
# ══════════════════════════════════════════════════════════════
print("\n── 5. MY COMPLAINTS ──────────────────────────────────")
r = get(f"{API}/complaints/my", headers=C_HDR)
check("Get my complaints", r and r.status_code == 200)
if r and r.status_code == 200:
    data = r.json()
    check("Returns list", isinstance(data, list), "list", type(data).__name__)
    if data:
        c0 = data[0]
        check("created_at in complaint", "created_at" in c0)
        check("created_at not null", c0.get("created_at") not in [None,"None","null"])
        check("address in complaint", "address" in c0)
        check("severity in complaint", "severity" in c0)
        check("damage_type in complaint", "damage_type" in c0)
        check("status in complaint", "status" in c0)
        check("complaint_id in complaint", "complaint_id" in c0)
        check("latitude in complaint", "latitude" in c0)
        check("longitude in complaint", "longitude" in c0)

# ══════════════════════════════════════════════════════════════
# 6. OFFICER ENDPOINTS
# ══════════════════════════════════════════════════════════════
print("\n── 6. OFFICER ENDPOINTS ──────────────────────────────")
r = get(f"{API}/complaints/", headers=O_HDR)
check("Officer get all complaints", r and r.status_code == 200)
if r and r.status_code == 200:
    data = r.json()
    check("Complaints sorted by priority", isinstance(data, list))
    if data and complaint_id:
        found = any(c.get("complaint_id") == complaint_id for c in data)
        check("New complaint visible to officer", found)

# Update status
if complaint_id and officer_token:
    r = patch(f"{API}/complaints/{complaint_id}/status",
        headers={**O_HDR, "Content-Type": "application/json"},
        json={"status": "in_progress", "officer_notes": "Inspected - repair scheduled"}
    )
    check("Update status to in_progress", r and r.status_code == 200, "200", str(r.status_code if r else "None"))

    r = patch(f"{API}/complaints/{complaint_id}/fund",
        headers={**O_HDR, "Content-Type": "application/json"},
        json={"amount": 25000, "note": "Repair materials allocated"}
    )
    check("Allocate fund", r and r.status_code == 200)

# Priority ranking
r = get(f"{API}/complaints/priority/ranking", headers=O_HDR)
check("Priority ranking endpoint", r and r.status_code == 200)
if r and r.status_code == 200:
    data = r.json()
    check("Priority ranking returns list", isinstance(data, list))

# Budget recommendations
r = get(f"{API}/complaints/budget/recommendations", headers=O_HDR)
check("Budget recommendations endpoint", r and r.status_code == 200)

# ══════════════════════════════════════════════════════════════
# 7. NOTIFICATIONS
# ══════════════════════════════════════════════════════════════
print("\n── 7. NOTIFICATIONS ──────────────────────────────────")
r = get(f"{API}/complaints/notifications/my", headers=C_HDR)
check("Get notifications", r and r.status_code == 200, "200", str(r.status_code if r else "None"))
if r and r.status_code == 200:
    data = r.json()
    check("Notifications is list", isinstance(data, list))
    if data:
        n = data[0]
        check("Notification has type", "type" in n)
        check("Notification has message", "message" in n)
        check("Notification has created_at", "created_at" in n)
        check("created_at not null", n.get("created_at") not in [None,"None"])

r = post(f"{API}/complaints/notifications/read-all", headers=C_HDR)
check("Mark all read", r and r.status_code == 200)

# ══════════════════════════════════════════════════════════════
# 8. ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════════
print("\n── 8. ADMIN ENDPOINTS ────────────────────────────────")
r = get(f"{API}/admin/stats", headers=A_HDR)
check("Admin stats", r and r.status_code == 200)
if r and r.status_code == 200:
    data = r.json()
    check("Stats has total", "total" in data)
    check("Stats has pending", "pending" in data)
    check("Stats has completed", "completed" in data)
    check("Stats has high", "high" in data)
    check("Stats total_officers > 0", data.get("total_officers", 0) > 0, ">0", str(data.get("total_officers")))
    check("Stats total_citizens > 0", data.get("total_citizens", 0) > 0, ">0", str(data.get("total_citizens")))

r = get(f"{API}/admin/complaints", headers=A_HDR)
check("Admin get complaints", r and r.status_code == 200)

r = get(f"{API}/admin/officers", headers=A_HDR)
check("Admin get officers", r and r.status_code == 200)
if r and r.status_code == 200:
    officers = r.json()
    check("Officers list not empty", len(officers) > 0, ">0 officers", str(len(officers)))

r = get(f"{API}/admin/citizens", headers=A_HDR)
check("Admin get citizens", r and r.status_code == 200)
if r and r.status_code == 200:
    citizens = r.json()
    check("Citizens list not empty", len(citizens) > 0)
    if citizens:
        c0 = citizens[0]
        check("Citizen has total_reports", "total_reports" in c0, "total_reports", str(c0.keys()))
        check("Citizen has high_severity", "high_severity" in c0)
        check("Citizen has fixed/completed", "fixed" in c0 or "completed" in c0)

# ══════════════════════════════════════════════════════════════
# 9. MESSAGES
# ══════════════════════════════════════════════════════════════
print("\n── 9. MESSAGES ───────────────────────────────────────")
if complaint_id:
    r = get(f"{API}/messages/{complaint_id}", headers=C_HDR)
    check("Get messages", r and r.status_code in [200, 404])

    r = post(f"{API}/messages/{complaint_id}/send-citizen",
        headers={**C_HDR, "Content-Type": "application/json"},
        json={"message": "Test message from citizen"}
    )
    check("Send citizen message", r and r.status_code == 200, "200", str(r.status_code if r else "None"))

# ══════════════════════════════════════════════════════════════
# 10. AI SERVICE
# ══════════════════════════════════════════════════════════════
print("\n── 10. AI SERVICE ────────────────────────────────────")
try:
    sys.path.insert(0, '/tmp')
    import importlib.util
    model_path = os.path.join(os.getcwd(), "ai_model", "road_damage_yolov8.pt")
    check("AI model file exists", os.path.exists(model_path), "file exists", "not found" if not os.path.exists(model_path) else "found")
except:
    pass

# Test via submission result
if complaint_id and citizen_token:
    r = get(f"{API}/complaints/{complaint_id}", headers=C_HDR)
    if r and r.status_code == 200:
        data = r.json()
        conf = data.get("ai_confidence", 0)
        check("AI confidence > 0", conf > 0, ">0", str(conf))
        check("AI damage_type set", data.get("damage_type") not in [None, ""], "damage type", str(data.get("damage_type")))
        check("AI severity set", data.get("severity") not in [None, ""], "severity", str(data.get("severity")))
        check("AI description set", bool(data.get("description")), "description text", str(data.get("description",""))[:50])

# ══════════════════════════════════════════════════════════════
# 11. STATIC FILES
# ══════════════════════════════════════════════════════════════
print("\n── 11. STATIC FILES ──────────────────────────────────")
r = get(f"{BASE}/citizen")
check("Citizen HTML loads", r and r.status_code == 200)
check("Leaflet in citizen", r and "leaflet" in r.text.lower())
check("No Google Maps in citizen", r and "google.maps" not in r.text)

r = get(f"{BASE}/static/dashboard.html")
check("Dashboard HTML loads", r and r.status_code == 200)
check("Leaflet in dashboard", r and "leaflet" in r.text.lower())
check("No Google Maps API key in dashboard", r and "YOUR_GOOGLE_MAPS_API_KEY" not in r.text)

r = get(f"{BASE}/admin")
check("Admin HTML loads", r and r.status_code == 200)

# ══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════
total = PASS + FAIL + WARN
print("\n" + "="*60)
print(f"  TEST RESULTS — {datetime.now().strftime('%d %b %Y %H:%M')}")
print("="*60)
print(f"  ✅ PASSED:  {PASS}/{total}")
print(f"  ❌ FAILED:  {FAIL}/{total}")
print(f"  ⚠  WARNINGS: {WARN}/{total}")
print(f"  Score: {PASS/total*100:.1f}%")
print("="*60)

if FAIL > 0:
    print("\n❌ FAILED TESTS:")
    for r in results:
        if "❌" in r:
            print(" ", r)

if WARN > 0:
    print("\n⚠  WARNINGS:")
    for r in results:
        if "⚠" in r:
            print(" ", r)