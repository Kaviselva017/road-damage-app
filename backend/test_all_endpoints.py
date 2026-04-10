"""Quick system verification — tests all critical endpoints."""
import requests, json, os

BASE = "http://localhost:8000"
NONE = "NONE"

print("=" * 60)
print("RoadWatch — Full System Verification")
print("=" * 60)

# 1. Health Check
r = requests.get(f"{BASE}/healthz")
print(f"1. Health: {r.json()}")

# 2. Citizen Login
r = requests.post(f"{BASE}/api/auth/login", json={"email":"citizen@road.com","password":"citizen123"})
cdata = r.json()
ct = cdata.get("access_token", "")
tok_short = ct[:20] if ct else NONE
print(f"2. Citizen Login: {r.status_code} token={tok_short}...")

# 3. Officer Login
r = requests.post(f"{BASE}/api/auth/officer/login", json={"email":"officer@road.com","password":"officer123"})
odata = r.json()
ot = odata.get("access_token", "")
tok_short = ot[:20] if ot else NONE
print(f"3. Officer Login: {r.status_code} token={tok_short}...")

# 4. Admin Login
r = requests.post(f"{BASE}/api/auth/officer/login", json={"email":"admin@road.com","password":"admin123"})
adata = r.json()
at = adata.get("access_token", "")
tok_short = at[:20] if at else NONE
print(f"4. Admin Login: {r.status_code} token={tok_short}...")

# 5. Get citizen profile
r = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {ct}"})
print(f"5. Citizen Profile: {r.status_code} {r.json()}")

# 6. My Complaints
r = requests.get(f"{BASE}/api/complaints/my", headers={"Authorization": f"Bearer {ct}"})
print(f"6. My Complaints: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 7. Officer Complaints
r = requests.get(f"{BASE}/api/complaints/", headers={"Authorization": f"Bearer {ot}"})
print(f"7. Officer Complaints: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 8. Notifications
r = requests.get(f"{BASE}/api/complaints/notifications/my", headers={"Authorization": f"Bearer {ct}"})
print(f"8. Notifications: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 9. Priority Ranking
r = requests.get(f"{BASE}/api/complaints/priority/ranking", headers={"Authorization": f"Bearer {ot}"})
print(f"9. Priority Ranking: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 10. Budget Recommendations
r = requests.get(f"{BASE}/api/complaints/budget/recommendations", headers={"Authorization": f"Bearer {ot}"})
print(f"10. Budget Recs: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 11. Admin Stats
r = requests.get(f"{BASE}/api/admin/stats", headers={"Authorization": f"Bearer {at}"})
print(f"11. Admin Stats: {r.status_code} {str(r.json())[:100]}...")

# 12. Admin Complaints
r = requests.get(f"{BASE}/api/admin/complaints", headers={"Authorization": f"Bearer {at}"})
print(f"12. Admin Complaints: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 13. Admin Officers
r = requests.get(f"{BASE}/api/admin/officers", headers={"Authorization": f"Bearer {at}"})
print(f"13. Admin Officers: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 14. Admin Citizens
r = requests.get(f"{BASE}/api/admin/citizens", headers={"Authorization": f"Bearer {at}"})
print(f"14. Admin Citizens: {r.status_code} count={len(r.json() if isinstance(r.json(), list) else [])}")

# 15. Messages API (sender_name now included!)
r = requests.get(f"{BASE}/api/messages/RD-DEMO-000001", headers={"Authorization": f"Bearer {ct}"})
msgs = r.json()
print(f"15. Messages API: {r.status_code} count={len(msgs)}")
if msgs and isinstance(msgs, list):
    print(f"    - First msg has sender_name: {'sender_name' in msgs[0]}")

# 16. Submit complaint
test_img = "bad.jpg"
if os.path.exists(test_img):
    with open(test_img, "rb") as f:
        r = requests.post(f"{BASE}/api/complaints/submit",
            headers={"Authorization": f"Bearer {ct}"},
            data={"latitude":"11.0168","longitude":"76.9558","address":"Test Road, Coimbatore","nearby_sensitive":"hospital zone"},
            files={"image": ("test.jpg", f, "image/jpeg")})
        resp = r.json()
        print(f"16. Submit Complaint: {r.status_code}")
        for k in ["complaint_id", "severity", "priority_score", "damage_type", "area_type", "officer_name"]:
            print(f"    - {k}: {resp.get(k, 'N/A')}")
else:
    print(f"16. Submit: SKIPPED (no test image)")

# 17. Officer PDF Report
r = requests.get(f"{BASE}/api/complaints/report/download", headers={"Authorization": f"Bearer {ot}"})
ct_header = r.headers.get("content-type", "?")
print(f"17. Officer PDF: {r.status_code} type={ct_header} size={len(r.content)} bytes")

# 18. Front page routes
for path in ["/", "/citizen", "/admin", "/dashboard"]:
    r = requests.get(f"{BASE}{path}")
    has_html = "<!DOCTYPE" in r.text[:100]
    print(f"18. Route {path}: {r.status_code} html={has_html}")

# 19. Register new citizen (data persistence test)
r = requests.post(f"{BASE}/api/auth/register", json={
    "name": "Persistence Test", "email": "persist_test@example.com",
    "phone": "1234567890", "password": "test123"
})
print(f"19. Register New Citizen: {r.status_code} {r.json()}")

# 20. Login with new account (verify data stored)
r = requests.post(f"{BASE}/api/auth/login", json={"email":"persist_test@example.com","password":"test123"})
print(f"20. Login New Citizen: {r.status_code} name={r.json().get('name', 'FAIL')}")

print()
print("=" * 60)
print("ALL ENDPOINT TESTS COMPLETED!")
print("=" * 60)
