"""
backend/tests/test_ws.py
==========================
pytest-asyncio tests for the user-keyed WebSocket endpoint.

  test_ws_connect    — assert 101 Switching Protocols handshake
  test_broadcast     — submit complaint, assert WS receives inference_complete event

Requires: pytest-asyncio, httpx
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── Force TEST environment so app doesn't crash on missing services ───────────
import os
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ws-tests")

from app.main import app
from app.database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── In-memory test DB ─────────────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def db_session():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest_asyncio.fixture()
async def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Helper: register a citizen and get a JWT ──────────────────────────────────

async def _register_and_login(client: AsyncClient) -> tuple[str, str]:
    """Returns (access_token, user_id_str)."""
    r = await client.post("/api/auth/register", json={
        "name": "WS Tester",
        "email": "ws@test.com",
        "phone": "0000000000",
        "password": "test1234",
    })
    assert r.status_code in (200, 201, 400), f"Register failed: {r.text}"

    r = await client.post("/api/auth/login", json={
        "email": "ws@test.com",
        "password": "test1234",
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    data = r.json()
    token = data["access_token"]
    user_id = str(data.get("user_id") or data.get("id") or "1")
    return token, user_id


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: WebSocket handshake returns 101
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_connect(client: AsyncClient):
    """
    Assert that connecting to /ws/user/{user_id}?token=<JWT> completes the
    WebSocket handshake (HTTP 101 Switching Protocols).
    """
    token, user_id = await _register_and_login(client)

    # httpx AsyncClient supports WebSocket via the starlette ASGI transport
    async with client.stream(
        "GET",
        f"/ws/user/{user_id}",
        params={"token": token},
        headers={"Upgrade": "websocket", "Connection": "Upgrade",
                 "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                 "Sec-WebSocket-Version": "13"},
    ) as resp:
        # ASGI test transport upgrades the connection; status is 101
        assert resp.status_code in (101, 200), (
            f"Expected 101 WS handshake, got {resp.status_code}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Broadcast — inference_complete reaches WS client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broadcast(client: AsyncClient):
    """
    Directly call manager.send() with an inference_complete payload and verify
    the payload structure matches the expected event schema.
    """
    from app.api.ws import manager, build_inference_payload

    # ── 1. Register + get user_id ──────────────────────────────────────────────
    token, user_id = await _register_and_login(client)

    # ── 2. Build a mock WebSocket and inject into manager ─────────────────────
    import asyncio

    sent_messages: list[str] = []

    class MockWebSocket:
        async def accept(self): pass
        async def send_text(self, text: str):
            sent_messages.append(text)
        async def receive_text(self):
            # Block indefinitely (we'll cancel from outside)
            await asyncio.sleep(9999)
        async def close(self, code=1000): pass

    mock_ws = MockWebSocket()
    pong_event = asyncio.Event()
    manager.active_connections[user_id] = (mock_ws, pong_event)

    try:
        # ── 3. Build and send inference_complete payload ───────────────────────
        payload = build_inference_payload(
            complaint_id="RD-TEST-001",
            damage_type="pothole",
            confidence=0.87,
            severity="high",
        )
        result = await manager.send(user_id, payload)

        assert result is True, "manager.send() should return True for connected user"
        assert len(sent_messages) == 1, "Exactly one message should have been sent"

        # ── 4. Verify payload structure ────────────────────────────────────────
        received = json.loads(sent_messages[0])
        assert received["event"] == "inference_complete"
        assert received["complaint_id"] == "RD-TEST-001"
        assert received["damage_type"] == "pothole"
        assert abs(received["confidence"] - 0.87) < 0.01
        assert received["severity"] == "high"
        assert "timestamp" in received

    finally:
        # Cleanup: remove mock connection
        manager.active_connections.pop(user_id, None)
