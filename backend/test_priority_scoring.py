"""
Focused regression check for live priority scoring and duplicate report bumping.
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


def login() -> str | None:
    response = requests.post(
        f"{API}/auth/login",
        json={"email": "citizen@road.com", "password": "citizen123"},
        timeout=8,
    )
    if response.status_code != 200:
        return None
    return response.json().get("access_token")


def write_test_image() -> str:
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    with open(path, "wb") as handle:
        handle.write(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.',#\x1c\x1c(7),01444\x1f'9=82<.342\x1e\x1f"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08"
            b"\x09\x0a\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\x0a\xff\xd9"
        )
    return path


def main() -> int:
    token = login()
    if not token:
        return fail("Citizen login failed")

    image_path = write_test_image()
    try:
        stamp = time.time()
        latitude = 12.0 + ((stamp % 1000) / 100000)
        longitude = 80.0 + (((stamp * 5) % 1000) / 100000)
        address = "General Hospital Main Road"

        with open(image_path, "rb") as image_handle:
            first_response = requests.post(
                f"{API}/complaints/submit",
                headers={"Authorization": f"Bearer {token}"},
                data={
                    "latitude": f"{latitude:.6f}",
                    "longitude": f"{longitude:.6f}",
                    "address": address,
                },
                files={"image": ("priority_test.jpg", image_handle, "image/jpeg")},
                timeout=12,
            )

        if first_response.status_code != 200:
            return fail(f"Initial complaint submission failed with status {first_response.status_code}")

        first_payload = first_response.json()
        if first_payload.get("warning") == "duplicate":
            return fail("Initial complaint submission unexpectedly hit duplicate detection")

        complaint_id = first_payload.get("complaint_id")
        if not complaint_id:
            return fail("Initial complaint submission did not return a complaint id")

        if first_payload.get("area_type") != "hospital":
            return fail(f"Expected area_type hospital, got {first_payload.get('area_type')}")

        priority_score = first_payload.get("priority_score")
        if not isinstance(priority_score, (int, float)) or priority_score < 60:
            return fail(f"Expected priority_score >= 60, got {priority_score}")

        if first_payload.get("report_count") != 1:
            return fail(f"Expected initial report_count to be 1, got {first_payload.get('report_count')}")

        detail_response = requests.get(
            f"{API}/complaints/{complaint_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if detail_response.status_code != 200:
            return fail(f"Complaint detail fetch failed with status {detail_response.status_code}")

        detail_payload = detail_response.json()
        if detail_payload.get("area_type") != "hospital":
            return fail(f"Complaint detail area_type mismatch: {detail_payload.get('area_type')}")
        if (detail_payload.get("priority_score") or 0) < priority_score:
            return fail("Complaint detail priority_score was lower than submit response")

        with open(image_path, "rb") as image_handle:
            duplicate_response = requests.post(
                f"{API}/complaints/submit",
                headers={"Authorization": f"Bearer {token}"},
                data={
                    "latitude": f"{latitude:.6f}",
                    "longitude": f"{longitude:.6f}",
                    "address": address,
                },
                files={"image": ("priority_test_duplicate.jpg", image_handle, "image/jpeg")},
                timeout=12,
            )

        if duplicate_response.status_code != 200:
            return fail(f"Duplicate complaint submission failed with status {duplicate_response.status_code}")

        duplicate_payload = duplicate_response.json()
        if duplicate_payload.get("warning") != "duplicate":
            return fail("Expected duplicate complaint submission to return duplicate warning")
        if duplicate_payload.get("existing_complaint_id") != complaint_id:
            return fail("Duplicate complaint submission returned the wrong existing complaint id")
        if (duplicate_payload.get("report_count") or 0) < 2:
            return fail(f"Expected duplicate report_count >= 2, got {duplicate_payload.get('report_count')}")
        if (duplicate_payload.get("priority_score") or 0) < priority_score:
            return fail("Duplicate complaint submission should not reduce priority_score")

        print("PASS: Priority scoring and duplicate report bumping work for new complaints.")
        return 0
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == "__main__":
    raise SystemExit(main())
