"""
Focused regression check for the officer directory endpoint.
"""
import os
import sys

import requests


BASE = os.getenv("ROADWATCH_BASE", "http://127.0.0.1:8000")
API = f"{BASE}/api"


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        public_response = requests.get(f"{API}/officers", timeout=8)
    except Exception as exc:
        return fail(f"Public directory request failed: {exc}")

    if public_response.status_code not in (401, 403):
        return fail(
            f"Expected public officer directory request to be rejected with 401/403, "
            f"got {public_response.status_code}"
        )

    try:
        login_response = requests.post(
            f"{API}/auth/officer/login",
            json={"email": "officer@road.com", "password": "officer123"},
            timeout=8,
        )
    except Exception as exc:
        return fail(f"Officer login request failed: {exc}")

    if login_response.status_code != 200:
        return fail(f"Officer login failed with status {login_response.status_code}")

    token = login_response.json().get("access_token")
    if not token:
        return fail("Officer login response did not include an access token")

    try:
        authed_response = requests.get(
            f"{API}/officers",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
    except Exception as exc:
        return fail(f"Authenticated directory request failed: {exc}")

    if authed_response.status_code != 200:
        return fail(f"Authenticated officer directory request failed with status {authed_response.status_code}")

    payload = authed_response.json()
    if not isinstance(payload, list):
        return fail(f"Expected officer directory payload to be a list, got {type(payload).__name__}")

    for entry in payload:
        if "email" in entry:
            return fail("Officer directory payload exposed an email field")
        if "phone" in entry:
            return fail("Officer directory payload exposed a phone field")
        if "id" not in entry or "name" not in entry or "zone" not in entry:
            return fail(f"Officer directory payload missing expected fields: {entry}")

    print("PASS: Officer directory requires auth and omits contact fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
