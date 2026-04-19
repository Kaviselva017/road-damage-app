# backend/tests/test_email.py
"""
AUTH-3 email tests.
SMTP is always mocked — no real connections made.
"""
from unittest.mock import patch

import pytest

from app.services.email_templates import (
    ai_result_email,
    complaint_received_email,
    officer_alert_email,
    status_update_email,
    suspicious_login_email,
    welcome_email,
)


# ── Template unit tests (no I/O) ──────────────────────────────────────────────


def test_welcome_template():
    subj, html = welcome_email("Ravi Kumar", "ravi@gmail.com")
    assert "Ravi" in subj
    assert "Welcome" in subj
    assert "ravi@gmail.com" in html
    assert "Road Damage Reporter" in html


def test_complaint_received_template():
    subj, html = complaint_received_email("Priya Nair", "42", "11.0168, 76.9558")
    assert "#42" in subj
    assert "Priya" in html
    assert "11.0168" in html


def test_ai_result_severity_badge():
    _, html = ai_result_email("Arjun", "7", "pothole", "critical", 0.91)
    assert "CRITICAL" in html
    assert "91.0%" in html
    assert "#7" in html


def test_status_update_timeline():
    _, html = status_update_email(
        "Divya", "15", "received", "repair_scheduled", "Crew assigned"
    )
    assert "Repair Scheduled" in html
    assert "Officer note" in html
    assert "Crew assigned" in html


def test_status_update_no_note():
    _, html = status_update_email("Divya", "15", "received", "in_review", "")
    assert "Officer note" not in html


def test_officer_alert_maps_link():
    _, html = officer_alert_email(
        officer_email="officer@corp.com",
        complaint_id="99",
        severity="high",
        location="11.0168, 76.9558",
        damage_class="alligator_crack",
        lat=11.0168,
        lng=76.9558,
        image_url="https://example.com/img.jpg",
    )
    assert "google.com/maps" in html
    assert "#99" in html
    assert "alligator crack" in html.lower()
    assert "example.com/img.jpg" in html


def test_suspicious_login_template():
    _, html = suspicious_login_email(
        name="Kavi Selva",
        ip="203.0.113.5",
        location="Chennai, India",
        device="Chrome / Windows",
        timestamp="2026-04-20 00:00 UTC",
        revoke_url="https://example.com/revoke",
    )
    assert "203.0.113.5" in html
    assert "Chennai" in html
    assert "Sign out all devices" in html
    assert "example.com/revoke" in html


# ── EmailService unit tests ───────────────────────────────────────────────────


def test_send_skips_when_not_configured(monkeypatch):
    """No sender configured → returns False, no exception."""
    from app.services.email_service import EmailService

    svc = EmailService()
    monkeypatch.setattr(svc, "sender", "")
    monkeypatch.setattr(svc, "password", "")
    result = svc._send_sync("to@example.com", "Hi", "<p>body</p>")
    assert result is False


def test_send_skips_invalid_email(monkeypatch):
    from app.services.email_service import EmailService

    svc = EmailService()
    monkeypatch.setattr(svc, "sender", "sender@gmail.com")
    monkeypatch.setattr(svc, "password", "password")
    result = svc._send_sync("not-an-email", "Hi", "<p>body</p>")
    assert result is False


def test_smtp_failure_returns_false(monkeypatch):
    """Connection error → False, connection reset for next attempt."""
    from app.services.email_service import EmailService

    svc = EmailService()
    monkeypatch.setattr(svc, "sender", "sender@gmail.com")
    monkeypatch.setattr(svc, "password", "password")
    with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("refused")):
        result = svc._send_sync("to@example.com", "Hi", "<p>body</p>")
    assert result is False
    assert svc._conn is None  # connection cleared after failure


# ── Integration: welcome email on new Google user ─────────────────────────────


@pytest.mark.asyncio
async def test_welcome_sent_on_new_google_user(async_client, session):
    sent_args = []

    def fake_send_sync(to, subject, html):
        sent_args.append((to, subject, html))
        return True

    with patch(
        "app.services.email_service.email_service.send_email_sync",
        side_effect=fake_send_sync,
    ), patch("app.api.auth.google_auth_service.verify_id_token") as mock_verify:
        from app.services.google_auth_service import GoogleUser

        mock_verify.return_value = GoogleUser(
            sub="new_sub_welcome",
            email="newwelcome@gmail.com",
            name="Welcome Test",
            picture="",
            email_verified=True,
        )
        res = await async_client.post("/api/auth/google", json={"id_token": "tok"})

    assert res.status_code == 200
    # BackgroundTasks run synchronously in test transport
    assert len(sent_args) == 1
    to, subject, _html = sent_args[0]
    assert to == "newwelcome@gmail.com"
    assert "Welcome" in subject


@pytest.mark.asyncio
async def test_no_welcome_on_returning_user(async_client, session):
    """Existing user (with phone) must NOT get a second welcome email."""
    from app.models.models import User

    user = User(
        name="Old User",
        email="old@gmail.com",
        google_sub="existing_sub_99",
        phone_number="+919876543299",
        is_active=True,
    )
    session.add(user)
    session.commit()

    sent_args = []

    def fake_send_sync(to, subject, html):
        sent_args.append((to, subject, html))
        return True

    with patch(
        "app.services.email_service.email_service.send_email_sync",
        side_effect=fake_send_sync,
    ), patch("app.api.auth.google_auth_service.verify_id_token") as mock_verify:
        from app.services.google_auth_service import GoogleUser

        mock_verify.return_value = GoogleUser(
            sub="existing_sub_99",
            email="old@gmail.com",
            name="Old User",
            picture="",
            email_verified=True,
        )
        res = await async_client.post("/api/auth/google", json={"id_token": "tok"})

    assert res.status_code == 200
    assert len(sent_args) == 0  # no welcome email for returning user


@pytest.mark.asyncio
async def test_smtp_error_does_not_break_login(async_client, session):
    """SMTP failure must never cause /auth/google to return non-200."""
    with patch(
        "app.services.email_service.email_service.send_email_sync",
        side_effect=Exception("SMTP kaboom"),
    ), patch("app.api.auth.google_auth_service.verify_id_token") as mock_verify:
        from app.services.google_auth_service import GoogleUser

        mock_verify.return_value = GoogleUser(
            sub="sub_smtp_resilience",
            email="resilient@gmail.com",
            name="Resilient User",
            picture="",
            email_verified=True,
        )
        res = await async_client.post("/api/auth/google", json={"id_token": "tok"})

    assert res.status_code == 200
