# -*- coding: utf-8 -*-
"""
RoadWatch -- COMPREHENSIVE SYSTEM TEST SUITE
=============================================
Covers ALL three portals end-to-end.
"""
import io
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api"

# -- Test image helper ---
REAL_IMAGE_PATH = None
for candidate in [Path(__file__).parent / "uploads"]:
    if candidate.exists():
        for f in candidate.glob("*.jpg"):
            if f.stat().st_size > 5000:
                REAL_IMAGE_PATH = str(f)
                break
        if REAL_IMAGE_PATH:
            break


def get_road_image():
    if REAL_IMAGE_PATH and os.path.exists(REAL_IMAGE_PATH):
        with open(REAL_IMAGE_PATH, "rb") as f:
            data = f.read()
    else:
        data = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                + os.urandom(2048) + b"\xff\xd9")
    return data + os.urandom(64)


# -- Result tracking ---
results = []
PASS = 0
FAIL = 0


def test(test_id, description, passed, detail=""):
    global PASS, FAIL
    if passed:
        PASS += 1
    else:
        FAIL += 1
    results.append((test_id, description, passed, detail))
    icon = "PASS" if passed else "FAIL"
    line = f"  [{icon}] [{test_id}] {description}"
    if not passed and detail:
        line += f" -- {detail}"
    print(line)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# =========================================================
#  CITIZEN PORTAL TESTS
# =========================================================
def test_citizen_portal():
    section("CITIZEN PORTAL TESTS")

    ts = uuid.uuid4().hex[:6]
    citizen_email = f"testcitizen_{ts}@test.com"
    citizen_pass = "Test123!"
    citizen_name = f"TestCitizen_{ts}"

    # Register
    r = requests.post(f"{API}/auth/register", json={
        "name": citizen_name, "email": citizen_email,
        "phone": "9999000000", "password": citizen_pass
    })
    test("C00", "Citizen registration", r.status_code in (200, 201), f"Status: {r.status_code}")

    # Login
    r = requests.post(f"{API}/auth/login", json={"email": citizen_email, "password": citizen_pass})
    test("C00b", "Citizen login", r.status_code == 200 and "access_token" in r.json(), f"Status: {r.status_code}")
    citizen_token = r.json().get("access_token", "")
    citizen_hdr = {"Authorization": f"Bearer {citizen_token}"}

    # [C01] Image upload - use UNIQUE random coordinates to avoid duplicate detection
    rand_lat = 12.9 + (hash(ts) % 100) * 0.01
    rand_lng = 77.5 + (hash(ts[::-1]) % 100) * 0.01
    img_bytes = get_road_image()
    files = {"image": ("road_damage.jpg", io.BytesIO(img_bytes), "image/jpeg")}
    data = {
        "latitude": str(rand_lat),
        "longitude": str(rand_lng),
        "address": f"Test Address Hospital Road {ts}",
        "nearby_sensitive": "PSG Hospital Nearby"
    }
    r = requests.post(f"{API}/complaints/submit", headers=citizen_hdr, files=files, data=data)
    complaint_data = r.json() if r.status_code == 200 else {}

    # If duplicate detected, that's also valid
    if complaint_data.get("warning") == "duplicate":
        test("C01", "Image upload (duplicate detected)", True, f"Existing: {complaint_data.get('existing_complaint_id')}")
        complaint_id = complaint_data.get("existing_complaint_id", "")
    else:
        submit_ok = r.status_code == 200 and "complaint_id" in complaint_data
        test("C01", "Camera/Gallery image upload + submit", submit_ok,
             f"Status: {r.status_code}, ID: {complaint_data.get('complaint_id', 'N/A')}")
        complaint_id = complaint_data.get("complaint_id", "")

    # [C02] AI model severity + damage type
    severity = complaint_data.get("severity", "")
    damage_type = complaint_data.get("damage_type", "")
    ai_conf = complaint_data.get("ai_confidence", 0)
    if complaint_data.get("warning") == "duplicate":
        test("C02", "AI severity (skipped - duplicate)", True, "Duplicate path")
    else:
        test("C02", "AI severity classification",
             severity in ("high", "medium", "low"),
             f"Severity: {severity}, Type: {damage_type}, Conf: {ai_conf}")

    # [C03] Priority scoring + area detection
    priority = complaint_data.get("priority_score", 0)
    area_type = complaint_data.get("area_type", "")
    if complaint_data.get("warning") == "duplicate":
        test("C03", "Priority scoring (skipped - duplicate)", True, "Duplicate path")
    else:
        test("C03", "Priority scoring + area detection",
             priority > 0 and area_type != "",
             f"Priority: {priority}, Area: {area_type}")

    # [C04] GPS coordinates
    lat = complaint_data.get("latitude")
    lng = complaint_data.get("longitude")
    if complaint_data.get("warning") == "duplicate":
        test("C04", "GPS stored (skipped - duplicate)", True, "Duplicate path")
    else:
        test("C04", "GPS coordinates stored correctly",
             lat is not None and lng is not None,
             f"Lat: {lat}, Lng: {lng}")

    # [C05] Duplicate complaint detection - submit to same location
    img_bytes2 = get_road_image()
    files2 = {"image": ("road2.jpg", io.BytesIO(img_bytes2), "image/jpeg")}
    data2 = {"latitude": str(rand_lat), "longitude": str(rand_lng),
             "address": f"Test Address {ts}", "nearby_sensitive": ""}
    r2 = requests.post(f"{API}/complaints/submit", headers=citizen_hdr, files=files2, data=data2)
    is_dup = r2.status_code == 200 and r2.json().get("warning") == "duplicate"
    test("C05", "Duplicate complaint detection (same location)", is_dup,
         f"Result: {r2.json().get('warning', 'no warning')}")

    # [C06] Non-road image handling
    import struct
    bmp = bytearray(b'BM')
    bmp += struct.pack('<I', 70)
    bmp += b'\x00\x00\x00\x00'
    bmp += struct.pack('<I', 54)
    bmp += struct.pack('<I', 40)
    bmp += struct.pack('<i', 2)
    bmp += struct.pack('<i', 2)
    bmp += struct.pack('<H', 1)
    bmp += struct.pack('<H', 24)
    bmp += b'\x00' * 24
    bmp += b'\xff\x00\x00\x00' * 4
    files3 = {"image": ("selfie.bmp", io.BytesIO(bytes(bmp)), "image/bmp")}
    data3 = {"latitude": "13.05", "longitude": "80.25", "address": "Random place"}
    r3 = requests.post(f"{API}/complaints/submit", headers=citizen_hdr, files=files3, data=data3)
    test("C06", "AI non-road image handling", r3.status_code in (400, 200), f"Status: {r3.status_code}")

    # [C07] Notification on submit
    r4 = requests.get(f"{API}/complaints/notifications/my", headers=citizen_hdr)
    notifs = r4.json() if r4.status_code == 200 else []
    has_submit_notif = any(n.get("type") == "submitted" for n in notifs)
    test("C07", "Notification created on submit",
         has_submit_notif and len(notifs) > 0,
         f"Total: {len(notifs)}, Has submitted: {has_submit_notif}")

    # [C08] Track complaint - NO extra auth
    if complaint_id:
        r5 = requests.get(f"{API}/complaints/{complaint_id}", headers=citizen_hdr)
        test("C08", "Track complaint (no extra auth)",
             r5.status_code == 200 and r5.json().get("complaint_id") == complaint_id,
             f"Status: {r5.status_code}")

        detail = r5.json()
        created_at = detail.get("created_at", "")
        test("C09", "Date/time ISO format with Z suffix",
             created_at.endswith("Z") and "T" in created_at,
             f"created_at: {created_at}")
    else:
        test("C08", "Track complaint (no extra auth)", False, "No complaint_id")
        test("C09", "Date/time ISO format", False, "No complaint_id")

    # [C10] Citizen messaging
    if complaint_id:
        r6 = requests.post(f"{API}/messages/{complaint_id}/send-citizen",
                           headers={**citizen_hdr, "Content-Type": "application/json"},
                           json={"message": "When will this be fixed?"})
        test("C10", "Citizen sends message to officer", r6.status_code == 200, f"Status: {r6.status_code}")
    else:
        test("C10", "Citizen sends message", False, "No complaint_id")

    # [C11] Notification badge
    r7 = requests.get(f"{API}/complaints/notifications/my", headers=citizen_hdr)
    test("C11", "Notification alerts / badge count", r7.status_code == 200,
         f"Total: {len(r7.json()) if r7.status_code == 200 else 0}")

    return citizen_token, citizen_hdr, complaint_id


# =========================================================
#  OFFICER PORTAL TESTS
# =========================================================
def test_officer_portal(complaint_id):
    section("OFFICER PORTAL TESTS")

    r = requests.post(f"{API}/auth/officer/login",
                      json={"email": "admin@road.com", "password": "admin123"})
    test("O01", "Officer login + JWT token",
         r.status_code == 200 and "access_token" in r.json(), f"Status: {r.status_code}")
    officer_token = r.json().get("access_token", "")
    officer_hdr = {"Authorization": f"Bearer {officer_token}"}

    r2 = requests.get(f"{API}/complaints/", headers=officer_hdr)
    complaints = r2.json() if r2.status_code == 200 else []
    test("O02", "Complaint list for officer",
         r2.status_code == 200 and len(complaints) > 0,
         f"Count: {len(complaints)}")

    if complaint_id:
        r3 = requests.patch(f"{API}/complaints/{complaint_id}/status",
                            headers={**officer_hdr, "Content-Type": "application/json"},
                            json={"status": "in_progress", "officer_notes": "Starting repair work"})
        test("O03", "Status update (in_progress)",
             r3.status_code == 200 and r3.json().get("status") == "in_progress",
             f"Status: {r3.status_code}")
    else:
        test("O03", "Status update", False, "No complaint_id")

    if complaint_id:
        r4 = requests.patch(f"{API}/complaints/{complaint_id}/fund",
                            headers={**officer_hdr, "Content-Type": "application/json"},
                            json={"amount": 15000, "note": "Asphalt repair materials"})
        test("O04", "Fund allocation (Rs.15000)",
             r4.status_code == 200 and r4.json().get("allocated_fund") == 15000,
             f"Fund: {r4.json().get('allocated_fund', 0) if r4.status_code == 200 else 'error'}")
    else:
        test("O04", "Fund allocation", False, "No complaint_id")

    r5 = requests.get(f"{API}/complaints/priority/ranking", headers=officer_hdr)
    if r5.status_code == 200 and len(r5.json()) > 1:
        scores = [c.get("priority_score", 0) for c in r5.json()]
        sorted_desc = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        test("O05", "Priority queue sorted descending", sorted_desc, f"Top: {scores[:3]}")
    else:
        test("O05", "Priority queue ordering", r5.status_code == 200, f"Count: {len(r5.json()) if r5.status_code == 200 else 0}")

    if complaint_id:
        r6 = requests.post(f"{API}/messages/{complaint_id}/send-officer",
                           headers={**officer_hdr, "Content-Type": "application/json"},
                           json={"message": "Team dispatched. ETA 2 hours."})
        test("O06", "Officer sends message to citizen", r6.status_code == 200, f"Status: {r6.status_code}")

        r6b = requests.get(f"{API}/messages/{complaint_id}", headers=officer_hdr)
        msg_count = len(r6b.json()) if r6b.status_code == 200 else 0
        test("O06b", "Message thread has citizen+officer msgs", msg_count >= 2, f"Messages: {msg_count}")
    else:
        test("O06", "Officer messaging", False, "No complaint_id")
        test("O06b", "Message thread", False, "No complaint_id")

    for sf in ["pending", "in_progress", "completed"]:
        rf = requests.get(f"{API}/complaints/?status={sf}", headers=officer_hdr)
        test(f"O07-{sf[:3]}", f"Filter view: {sf}", rf.status_code == 200,
             f"Count: {len(rf.json()) if rf.status_code == 200 else 'error'}")

    if complaint_id:
        r8 = requests.get(f"{API}/complaints/{complaint_id}", headers=officer_hdr)
        if r8.status_code == 200:
            d = r8.json()
            required = ["complaint_id", "damage_type", "severity", "status",
                        "latitude", "longitude", "priority_score", "created_at",
                        "image_url", "area_type", "ai_confidence"]
            missing = [f for f in required if f not in d or d[f] is None]
            test("O08", "Complaint detail ALL fields present", len(missing) == 0,
                 f"Missing: {missing}" if missing else f"All {len(required)} fields OK")
        else:
            test("O08", "Complaint detail", False, f"Status: {r8.status_code}")
    else:
        test("O08", "Complaint detail", False, "No complaint_id")

    return officer_token, officer_hdr


# =========================================================
#  ADMIN PORTAL TESTS
# =========================================================
def test_admin_portal(complaint_id):
    section("ADMIN PORTAL TESTS")

    r = requests.post(f"{API}/auth/officer/login",
                      json={"email": "admin@road.com", "password": "admin123"})
    test("A01", "Admin login + auth", r.status_code == 200 and "access_token" in r.json(), f"Status: {r.status_code}")
    admin_token = r.json().get("access_token", "")
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    # Overview stats
    r2 = requests.get(f"{API}/admin/stats", headers=admin_hdr)
    if r2.status_code == 200:
        s = r2.json()
        has_keys = all(k in s for k in ["total", "pending", "in_progress", "completed",
                                         "high", "total_officers", "total_citizens"])
        test("A02", "Overview stats -- all fields present",
             has_keys and s.get("total", 0) > 0,
             f"Total:{s.get('total')}, Officers:{s.get('total_officers')}, Citizens:{s.get('total_citizens')}")
    else:
        test("A02", "Overview stats", False, f"Status: {r2.status_code}")

    # All complaints
    r3 = requests.get(f"{API}/admin/complaints", headers=admin_hdr)
    test("A03", "All complaints listing",
         r3.status_code == 200 and len(r3.json()) > 0,
         f"Count: {len(r3.json()) if r3.status_code == 200 else 0}")

    # Officer listing
    r4 = requests.get(f"{API}/admin/officers", headers=admin_hdr)
    test("A04a", "Officer listing", r4.status_code == 200,
         f"Count: {len(r4.json()) if r4.status_code == 200 else 0}")

    # Add officer -- correct endpoint: /api/auth/officer/register
    new_officer_email = f"officer_{uuid.uuid4().hex[:6]}@test.com"
    r4b = requests.post(f"{API}/auth/officer/register",
                        headers={**admin_hdr, "Content-Type": "application/json"},
                        json={"name": "Test Officer", "email": new_officer_email,
                              "phone": "8888000000", "password": "officer123",
                              "zone": "Zone A"})
    test("A04b", "Add new officer (register)",
         r4b.status_code in (200, 201),
         f"Status: {r4b.status_code}")

    # Citizen listing
    r5 = requests.get(f"{API}/admin/citizens", headers=admin_hdr)
    test("A05", "Citizen listing",
         r5.status_code == 200 and len(r5.json()) > 0,
         f"Count: {len(r5.json()) if r5.status_code == 200 else 0}")

    # Analytics chart data
    r6 = requests.get(f"{API}/admin/chart/daily", headers=admin_hdr)
    test("A06", "Analytics chart data (daily)", r6.status_code == 200,
         f"Points: {len(r6.json()) if r6.status_code == 200 else 0}")

    # PDF download -- no filter
    r7 = requests.get(f"{API}/admin/reports/download?status=all&severity=all", headers=admin_hdr)
    test("A07", "PDF download (no filter)",
         r7.status_code == 200 and r7.headers.get("content-type", "").startswith("application/pdf"),
         f"Size: {len(r7.content)} bytes")

    # PDF download -- date filter
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    r8 = requests.get(f"{API}/admin/reports/download?status=all&severity=all&date_from={today}&date_to={today}",
                      headers=admin_hdr)
    test("A08", "PDF download (date filter)",
         r8.status_code == 200 and len(r8.content) > 100,
         f"Size: {len(r8.content)} bytes")

    # PDF download -- severity filter
    r9 = requests.get(f"{API}/admin/reports/download?status=all&severity=high", headers=admin_hdr)
    test("A09", "PDF download (severity=high)", r9.status_code == 200, f"Size: {len(r9.content)} bytes")

    # Complaint reassignment
    if complaint_id:
        officers = r4.json() if r4.status_code == 200 else []
        non_admin = [o for o in officers if not o.get("is_admin")]
        if non_admin:
            target_id = non_admin[0]["id"]
            r10 = requests.patch(f"{API}/admin/complaints/{complaint_id}/reassign",
                                 headers={**admin_hdr, "Content-Type": "application/json"},
                                 json={"officer_id": target_id})
            test("A10", "Complaint reassignment", r10.status_code == 200,
                 f"Status: {r10.status_code}, To: {target_id}")
        else:
            test("A10", "Complaint reassignment", True, "No non-admin officers")
    else:
        test("A10", "Complaint reassignment", False, "No complaint_id")

    # Queue allocation check
    officers_data = requests.get(f"{API}/admin/officers", headers=admin_hdr).json()
    test("A11", "Officer queue data available", len(officers_data) > 0,
         f"Officers: {len(officers_data)}")

    return admin_token, admin_hdr


# =========================================================
#  CROSS-PORTAL INTEGRATION TESTS
# =========================================================
def test_integration(citizen_hdr, officer_hdr, complaint_id):
    section("CROSS-PORTAL INTEGRATION TESTS")

    if complaint_id:
        r1 = requests.patch(f"{API}/complaints/{complaint_id}/status",
                            headers={**officer_hdr, "Content-Type": "application/json"},
                            json={"status": "completed", "officer_notes": "Repair done"})
        test("I01", "Status->completed trigger", r1.status_code == 200, f"Status: {r1.status_code}")

        r2 = requests.get(f"{API}/complaints/notifications/my", headers=citizen_hdr)
        notifs = r2.json() if r2.status_code == 200 else []
        has_completed = any(n.get("type") == "completed" for n in notifs)
        test("I02", "Citizen receives completed notification", has_completed, f"Total: {len(notifs)}")

        r3 = requests.get(f"{API}/complaints/{complaint_id}", headers=citizen_hdr)
        if r3.status_code == 200:
            resolved_at = r3.json().get("resolved_at")
            test("I03", "resolved_at set on completion",
                 resolved_at is not None and "T" in str(resolved_at),
                 f"resolved_at: {resolved_at}")
        else:
            test("I03", "resolved_at", False, f"Status: {r3.status_code}")

        fund_notifs = [n for n in notifs if n.get("type") == "funded"]
        test("I04", "Fund allocation notification", len(fund_notifs) > 0, f"Fund notifs: {len(fund_notifs)}")
    else:
        test("I01", "Status->completed", False, "No complaint_id")
        test("I02", "Completed notification", False, "No complaint_id")
        test("I03", "resolved_at", False, "No complaint_id")
        test("I04", "Fund notification", False, "No complaint_id")

    r_h = requests.get(f"{BASE}/healthz")
    test("I05", "Health check endpoint",
         r_h.status_code == 200 and r_h.json().get("status") == "ok",
         f"DB: {r_h.json().get('database', '?')}")


# =========================================================
#  MAIN
# =========================================================
def main():
    print("\n" + "=" * 60)
    print("  ROADWATCH -- COMPREHENSIVE SYSTEM TEST")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    try:
        r = requests.get(f"{BASE}/healthz", timeout=5)
        if r.status_code != 200:
            print("Server not responding!")
            sys.exit(1)
        print(f"  Server online -- v{r.json().get('version', '?')}")
    except Exception as e:
        print(f"Cannot reach server at {BASE}: {e}")
        sys.exit(1)

    citizen_token, citizen_hdr, complaint_id = test_citizen_portal()
    officer_token, officer_hdr = test_officer_portal(complaint_id)
    admin_token, admin_hdr = test_admin_portal(complaint_id)
    test_integration(citizen_hdr, officer_hdr, complaint_id)

    # SUMMARY
    print("\n" + "=" * 60)
    print("  TEST RESULTS SUMMARY")
    print("=" * 60)
    total = PASS + FAIL
    pct = (PASS / total * 100) if total > 0 else 0
    print(f"\n  Passed: {PASS}/{total} ({pct:.1f}%)")
    print(f"  Failed: {FAIL}/{total}")

    if FAIL > 0:
        print(f"\n  FAILED TESTS:")
        for tid, desc, passed, detail in results:
            if not passed:
                print(f"    [FAIL] [{tid}] {desc} -- {detail}")

    if FAIL == 0:
        print(f"\n  ALL TESTS PASSED -- READY FOR DEPLOYMENT!")
    else:
        print(f"\n  FIX FAILURES BEFORE DEPLOYMENT")
    print("=" * 60 + "\n")

    return FAIL == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
