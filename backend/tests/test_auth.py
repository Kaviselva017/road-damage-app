# backend/tests/test_auth.py
from unittest.mock import patch

import pytest



MOCK_GOOGLE_USER = {
    "sub": "google_123",
    "email": "test@gmail.com",
    "name": "Test User",
    "picture": "https://pic.url",
    "email_verified": True,
}


def _mock_verify(token):
    from app.services.google_auth_service import GoogleUser

    return GoogleUser(**MOCK_GOOGLE_USER)


@pytest.mark.asyncio
async def test_google_token_valid(async_client):
    with patch(
        "app.api.auth.google_auth_service.verify_id_token", side_effect=_mock_verify
    ), patch(
        "app.services.email_service.email_service.send_email_sync", return_value=True
    ):
        res = await async_client.post(
            "/api/auth/google", json={"id_token": "valid_token"}
        )
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body or body.get("requires_phone") is True


@pytest.mark.asyncio
async def test_google_token_invalid(async_client):
    with patch(
        "app.api.auth.google_auth_service.verify_id_token",
        side_effect=__import__("fastapi").HTTPException(status_code=401),
    ):
        res = await async_client.post(
            "/api/auth/google", json={"id_token": "bad_token"}
        )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation(async_client, session):
    # Create user with phone so we get full tokens
    from app.models.models import User

    user = User(
        name="Refresh User",
        email="refresh@test.com",
        google_sub="google_refresh_1",
        phone_number="+919999900000",
        is_active=True,
    )
    session.add(user)
    session.commit()

    with patch("app.api.auth.google_auth_service.verify_id_token") as mock:
        from app.services.google_auth_service import GoogleUser

        mock.return_value = GoogleUser(
            sub="google_refresh_1",
            email="refresh@test.com",
            name="Refresh User",
            picture="",
            email_verified=True,
        )
        login = (
            await async_client.post("/api/auth/google", json={"id_token": "t"})
        ).json()

    assert "refresh_token" in login, f"Expected full tokens, got: {login}"
    old_refresh = login["refresh_token"]

    res = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert res.status_code == 200
    new_tokens = res.json()
    assert new_tokens["refresh_token"] != old_refresh

    # Old token must now be rejected
    res2 = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert res2.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalidates_refresh(async_client, session):
    from app.models.models import User

    user = User(
        name="Logout User",
        email="logout@test.com",
        google_sub="google_logout_1",
        phone_number="+919999900001",
        is_active=True,
    )
    session.add(user)
    session.commit()

    with patch("app.api.auth.google_auth_service.verify_id_token") as mock:
        from app.services.google_auth_service import GoogleUser

        mock.return_value = GoogleUser(
            sub="google_logout_1",
            email="logout@test.com",
            name="Logout User",
            picture="",
            email_verified=True,
        )
        login = (
            await async_client.post("/api/auth/google", json={"id_token": "t"})
        ).json()

    await async_client.post(
        "/api/auth/logout",
        json={"refresh_token": login["refresh_token"]},
        headers={"Authorization": f"Bearer {login.get('access_token', '')}"},
    )
    res = await async_client.post(
        "/api/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_unverified_email(async_client):
    def _unverified(_):
        from app.services.google_auth_service import GoogleUser

        return GoogleUser(
            sub="x", email="x@x.com", name="X", picture="", email_verified=False
        )

    with patch(
        "app.api.auth.google_auth_service.verify_id_token", side_effect=_unverified
    ):
        res = await async_client.post("/api/auth/google", json={"id_token": "t"})
    assert res.status_code == 403
