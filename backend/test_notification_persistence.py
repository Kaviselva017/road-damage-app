"""
Focused regression check for citizen in-app notification persistence.
"""
from __future__ import annotations

import os
import tempfile
import time

import requests


BASE = os.getenv("ROADWATCH_BASE", "http://127.0.0.1:8000")
API = f"{BASE}/api"


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def login(email: str, password: str, officer: bool = False) -> str | None:
    path = "/auth/officer/login" if officer else "/auth/login"
    response = requests.post(
        f"{API}{path}",
        json={"email": email, "password": password},
        timeout=8,
    )
    if response.status_code != 200:
        return None
    return response.json().get("access_token")


def write_test_image() -> str:
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    with open("uploads/81da090e1a864842af48e408c043d284.jpg", "rb") as f:
        base_img = f.read()
    with open(path, "wb") as handle:
        handle.write(base_img + os.urandom(10))
    return path


def main() -> int:
    citizen_token = login("citizen@road.com", "citizen123")
    if not citizen_token:
        return fail("Citizen login failed")

    officer_token = login("officer@road.com", "officer123", officer=True)
    if not officer_token:
        return fail("Officer login failed")

    admin_token = login("admin@road.com", "admin123", officer=True)
    if not admin_token:
        return fail("Admin login failed")

    image_path = write_test_image()
    complaint_id = None

    try:
        stamp = time.time()
        latitude = 10.0 + ((stamp % 1000) / 100000)
        longitude = 79.0 + (((stamp * 7) % 1000) / 100000)

        with open(image_path, "rb") as image_handle:
            submit_response = requests.post(
                f"{API}/complaints/submit",
                headers={"Authorization": f"Bearer {citizen_token}"},
                data={
                    "latitude": f"{latitude:.6f}",
                    "longitude": f"{longitude:.6f}",
                    "address": "Notification Test Road",
                },
                files={"image": ("notification_test.jpg", image_handle, "image/jpeg")},
                timeout=12,
            )

        if submit_response.status_code != 200:
            return fail(f"Complaint submit failed with status {submit_response.status_code}")

        submit_payload = submit_response.json()
        complaint_id = submit_payload.get("complaint_id") or submit_payload.get("existing_complaint_id")
        if not complaint_id:
            return fail("Complaint submit response did not include a complaint id")

        notification_response = requests.get(
            f"{API}/complaints/notifications/my",
            headers={"Authorization": f"Bearer {citizen_token}"},
            timeout=8,
        )
        if notification_response.status_code != 200:
            return fail(f"Notification inbox fetch failed with status {notification_response.status_code}")

        notifications = notification_response.json()
        submission_entries = [
            entry for entry in notifications
            if entry.get("complaint_id") == complaint_id and entry.get("type") == "submitted"
        ]
        if not submission_entries:
            return fail("Complaint submission did not create a persisted citizen notification")

        officers_response = requests.get(
            f"{API}/admin/officers",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=8,
        )
        if officers_response.status_code != 200:
            return fail(f"Admin officer list fetch failed with status {officers_response.status_code}")

        officers = officers_response.json()
        officer = next((entry for entry in officers if entry.get("email") == "officer@road.com"), None)
        if not officer:
            return fail("Could not locate the default officer for reassignment")

        reassign_response = requests.patch(
            f"{API}/admin/complaints/{complaint_id}/reassign",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json",
            },
            json={"officer_id": officer["id"]},
            timeout=8,
        )
        if reassign_response.status_code != 200:
            return fail(f"Complaint reassign failed with status {reassign_response.status_code}")

        update_response = requests.patch(
            f"{API}/complaints/{complaint_id}/status",
            headers={
                "Authorization": f"Bearer {officer_token}",
                "Content-Type": "application/json",
            },
            json={"status": "in_progress", "officer_notes": "Notification persistence regression test"},
            timeout=8,
        )
        if update_response.status_code != 200:
            return fail(f"Complaint status update failed with status {update_response.status_code}")

        notification_response = requests.get(
            f"{API}/complaints/notifications/my",
            headers={"Authorization": f"Bearer {citizen_token}"},
            timeout=8,
        )
        if notification_response.status_code != 200:
            return fail(f"Notification inbox refetch failed with status {notification_response.status_code}")

        notifications = notification_response.json()
        status_entries = [
            entry for entry in notifications
            if entry.get("complaint_id") == complaint_id and entry.get("type") == "in_progress"
        ]
        if not status_entries:
            return fail("Complaint status update did not create a persisted citizen notification")

        print("PASS: Citizen notifications are persisted for submission and status updates.")
        return 0
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == "__main__":
    raise SystemExit(main())
