"""
Focused regression check for rejecting non-road complaint images.
"""
from __future__ import annotations

import os
import tempfile

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


def write_non_road_image() -> str:
    from PIL import Image, ImageDraw

    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)

    image = Image.new("RGB", (640, 480), color=(120, 200, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 260, 640, 480], fill=(60, 180, 75))
    draw.ellipse([460, 40, 560, 140], fill=(255, 230, 80))
    image.save(path, "JPEG")
    return path


def main() -> int:
    token = login()
    if not token:
        return fail("Citizen login failed")

    headers = {"Authorization": f"Bearer {token}"}
    before_response = requests.get(f"{API}/complaints/my", headers=headers, timeout=8)
    if before_response.status_code != 200:
        return fail(f"Could not fetch existing complaints: {before_response.status_code}")
    before_ids = {entry.get("complaint_id") for entry in before_response.json()}

    image_path = write_non_road_image()
    try:
        with open(image_path, "rb") as image_handle:
            submit_response = requests.post(
                f"{API}/complaints/submit",
                headers=headers,
                data={
                    "latitude": "11.123456",
                    "longitude": "79.123456",
                    "address": "City Park Entrance",
                },
                files={"image": ("non_road.jpg", image_handle, "image/jpeg")},
                timeout=12,
            )

        if submit_response.status_code != 400:
            return fail(f"Expected non-road image rejection with 400, got {submit_response.status_code}")

        detail = submit_response.json().get("detail", "")
        if "road" not in detail.lower():
            return fail(f"Expected road-surface rejection detail, got: {detail}")

        after_response = requests.get(f"{API}/complaints/my", headers=headers, timeout=8)
        if after_response.status_code != 200:
            return fail(f"Could not refetch complaints after rejection: {after_response.status_code}")
        after_ids = {entry.get("complaint_id") for entry in after_response.json()}

        if before_ids != after_ids:
            return fail("Non-road rejection should not create a complaint record")

        print("PASS: Non-road images are rejected and do not create complaints.")
        return 0
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == "__main__":
    raise SystemExit(main())
