# backend/tests/test_phone.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _make_temp_token(user_id: int) -> str:
    from app.api.auth import _make_temp_token
    return _make_temp_token(user_id)

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_phone_accepted(db_session, test_user):
    token = _make_temp_token(test_user.id)
    res = client.post("/api/auth/phone",
        json={"phone_number": "+919876543210"},
        headers=_headers(token))

    if res.status_code != 200:
        print(f"Failed response: {res.json()}")

    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["phone"] == "+919876543210"


def test_phone_duplicate(db_session, test_user, second_user):
    # Give first user the number
    token1 = _make_temp_token(test_user.id)
    client.post("/api/auth/phone",
        json={"phone_number": "+919876543210"},
        headers=_headers(token1))

    # Second user tries same number
    token2 = _make_temp_token(second_user.id)
    res = client.post("/api/auth/phone",
        json={"phone_number": "+919876543210"},
        headers=_headers(token2))
    assert res.status_code == 409
    assert res.json()["detail"]["error"] == "phone_already_registered"


def test_phone_invalid_format(db_session, test_user):
    token = _make_temp_token(test_user.id)
    res = client.post("/api/auth/phone",
        json={"phone_number": "9876543210"},   # missing + and country code
        headers=_headers(token))
    assert res.status_code == 422


def test_phone_too_short(db_session, test_user):
    token = _make_temp_token(test_user.id)
    res = client.post("/api/auth/phone",
        json={"phone_number": "+91123"},
        headers=_headers(token))
    assert res.status_code == 422


def test_complaint_blocked_without_phone(db_session, test_user_no_phone, auth_headers):
    # ensure no phone_number is present
    test_user_no_phone.phone_number = None
    db_session.commit()
    res = client.post("/api/complaints/submit",
        data={"description": "pothole", "latitude": "11.0", "longitude": "77.0"},
        files={"image": ("test.jpg", b"fakejpeg", "image/jpeg")},
        headers=auth_headers(test_user_no_phone))
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "phone_required"


def test_temp_token_expires(db_session, test_user):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    import os
    expired = jwt.encode(
        {"sub": str(test_user.id), "type": "temp",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        os.getenv("JWT_SECRET_KEY", "changeme"), algorithm="HS256"
    )
    res = client.post("/api/auth/phone",
        json={"phone_number": "+919999999999"},
        headers=_headers(expired))
    assert res.status_code == 401
