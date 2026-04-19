from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.refresh_token import RefreshToken
from app.services.token_service import (
    issue_token_pair, rotate_refresh_token,
    make_revocation_token,
    hash_token, verify_token_hash,
)
from app.middleware.security import (
    blacklist_jti, is_jti_blacklisted,
    record_auth_failure, is_account_locked,
    AUTH_FAIL_LIMIT,
)

from app.models.models import User

client = TestClient(app)

@pytest.fixture
def test_user_with_phone(db_session):
    user = User(
        google_sub="test_google_sub_phone",
        email="phone@example.com",
        name="Phone User",
        phone_number="+919876543210"
    )
    db_session.add(user)
    db_session.commit()
    return user


# ── hash correctness ──────────────────────────────────────────────────────────

def test_token_hash_not_truncated():
    """Two long tokens with identical first 72 bytes must hash differently."""
    from jose import jwt as _jwt
    import uuid
    padding = "x" * 100
    make = lambda: _jwt.encode(
        {"sub": "1", "padding": padding, "jti": str(uuid.uuid4()), "type": "refresh",
         "exp": datetime.now(timezone.utc) + timedelta(days=7)},
        "secret", algorithm="HS256",
    )
    t1, t2 = make(), make()
    assert t1[:72] == t2[:72], f"Precondition: tokens share first 72 bytes. t1={t1[:72]}, t2={t2[:72]}"
    h = hash_token(t1)
    assert verify_token_hash(t1, h) is True
    assert verify_token_hash(t2, h) is False   # would fail with raw bcrypt


# ── rotation ──────────────────────────────────────────────────────────────────

def test_refresh_rotation_invalidates_old_token(db_session, test_user_with_phone):
    pair1 = issue_token_pair(test_user_with_phone, db_session)
    pair2, _ = rotate_refresh_token(pair1.refresh_token, db_session)

    assert pair2.refresh_token != pair1.refresh_token
    assert pair2.access_token  != pair1.access_token

    # Old token must be rejected
    with pytest.raises(Exception) as exc:
        rotate_refresh_token(pair1.refresh_token, db_session)
    assert "401" in str(exc.value) or "revoked" in str(exc.value).lower()


# ── stolen token detection ────────────────────────────────────────────────────

def test_stolen_token_revokes_entire_family(db_session, test_user_with_phone):
    pair1 = issue_token_pair(test_user_with_phone, db_session)
    pair2, _ = rotate_refresh_token(pair1.refresh_token, db_session)

    # Attacker replays pair1 (already used) — entire family must be nuked
    with pytest.raises(Exception):
        rotate_refresh_token(pair1.refresh_token, db_session)

    # Legitimate user's pair2 must also be dead
    with pytest.raises(Exception):
        rotate_refresh_token(pair2.refresh_token, db_session)

    # Confirm DB: all tokens in family are revoked
    family_tokens = db_session.query(RefreshToken).filter(
        RefreshToken.family_id == pair1.family_id
    ).all()
    assert all(t.revoked for t in family_tokens)


def test_stolen_token_sends_compromise_email(db_session, test_user_with_phone):
    pair1 = issue_token_pair(test_user_with_phone, db_session)
    rotate_refresh_token(pair1.refresh_token, db_session)  # legitimate rotation

    with patch("app.services.token_service._send_compromise_email") as mock_email:
        with pytest.raises(Exception):
            rotate_refresh_token(pair1.refresh_token, db_session)
        mock_email.assert_called_once()


# ── concurrent session limit ──────────────────────────────────────────────────

def test_concurrent_session_limit(db_session, test_user_with_phone):
    from app.services.token_service import MAX_SESSIONS
    pairs = [issue_token_pair(test_user_with_phone, db_session)
             for _ in range(MAX_SESSIONS + 1)]

    active = db_session.query(RefreshToken).filter(
        RefreshToken.user_id == test_user_with_phone.id,
        RefreshToken.revoked == False,
    ).count()
    assert active <= MAX_SESSIONS


# ── JWT blacklist ─────────────────────────────────────────────────────────────

def test_blacklist_after_logout(db_session, test_user_with_phone):
    if not _redis_available():
        pytest.skip("Redis not available")

    pair = issue_token_pair(test_user_with_phone, db_session)

    res = client.post(
        "/api/auth/logout",
        json={"refresh_token": pair.refresh_token},
        headers={"Authorization": f"Bearer {pair.access_token}"},
    )
    assert res.status_code == 200

    # Access token must now be rejected
    res2 = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {pair.access_token}"},
    )
    assert res2.status_code == 401


def test_blacklist_direct(db_session):
    if not _redis_available():
        pytest.skip("Redis not available")

    jti = "test-jti-12345"
    assert is_jti_blacklisted(jti) is False
    blacklist_jti(jti, ttl_seconds=60)
    assert is_jti_blacklisted(jti) is True


# ── account lockout ───────────────────────────────────────────────────────────

def test_account_lockout_after_repeated_failures(db_session):
    if not _redis_available():
        pytest.skip("Redis not available")

    identifier = "test_google_sub_lockout"
    for _ in range(AUTH_FAIL_LIMIT):
        record_auth_failure(identifier)

    assert is_account_locked(identifier) is True


def test_locked_account_returns_423(db_session, test_user_with_phone):
    if not _redis_available():
        pytest.skip("Redis not available")

    from app.middleware.security import lock_account
    lock_account(test_user_with_phone.google_sub)

    pair = issue_token_pair(test_user_with_phone, db_session)
    res  = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {pair.access_token}"},
    )
    assert res.status_code == 423


# ── revoke-all email link ─────────────────────────────────────────────────────

def test_revoke_all_endpoint(db_session, test_user_with_phone):
    # Create 3 sessions
    for _ in range(3):
        issue_token_pair(test_user_with_phone, db_session)

    tok = make_revocation_token(test_user_with_phone.id, db_session)
    res = client.get(f"/api/auth/revoke-all?token={tok}")
    assert res.status_code == 200

    active = db_session.query(RefreshToken).filter(
        RefreshToken.user_id == test_user_with_phone.id,
        RefreshToken.revoked == False,
    ).count()
    assert active == 0


def test_revoke_all_link_single_use(db_session, test_user_with_phone):
    tok = make_revocation_token(test_user_with_phone.id, db_session)
    client.get(f"/api/auth/revoke-all?token={tok}")
    res = client.get(f"/api/auth/revoke-all?token={tok}")
    assert res.status_code == 410


# ── helpers ───────────────────────────────────────────────────────────────────

def _redis_available() -> bool:
    from app.middleware.security import _redis
    return _redis is not None
