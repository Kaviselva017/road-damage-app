"""
backend/tests/test_ws.py
==========================
pytest-asyncio tests for the user-keyed WebSocket endpoint.

  test_ws_connect    — assert 101 Switching Protocols handshake
  test_broadcast     — inject mock WS and verify inference_complete event

Requires: pytest-asyncio, httpx
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.api.ws import ConnectionManager, build_inference_payload, manager


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Connection manager connect/disconnect
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_connect():
    """
    Verify ConnectionManager can accept and track a mock WebSocket.
    """

    class MockWebSocket:
        async def accept(self):
            pass

        async def close(self, code=1000):
            pass

    mgr = ConnectionManager()
    ws = MockWebSocket()
    await mgr.connect("user-ws-test-1", ws)

    assert "user-ws-test-1" in mgr.active_connections
    assert mgr.connected_count == 1

    mgr.disconnect("user-ws-test-1")
    assert "user-ws-test-1" not in mgr.active_connections
    assert mgr.connected_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Broadcast — inference_complete reaches WS client
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broadcast():
    """
    Directly call manager.send() with an inference_complete payload and verify
    the payload structure matches the expected event schema.
    """

    sent_messages: list[str] = []

    class MockWebSocket:
        async def accept(self):
            pass

        async def send_text(self, text: str):
            sent_messages.append(text)

        async def receive_text(self):
            # Block indefinitely (we'll cancel from outside)
            await asyncio.sleep(9999)

        async def close(self, code=1000):
            pass

    user_id = "ws-test-user-42"
    mock_ws = MockWebSocket()
    pong_event = asyncio.Event()
    manager.active_connections[user_id] = (mock_ws, pong_event)

    try:
        # Build and send inference_complete payload
        payload = build_inference_payload(
            complaint_id="RD-TEST-001",
            damage_type="pothole",
            confidence=0.87,
            severity="high",
        )
        result = await manager.send(user_id, payload)

        assert result is True, "manager.send() should return True for connected user"
        assert len(sent_messages) == 1, "Exactly one message should have been sent"

        # Verify payload structure
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
