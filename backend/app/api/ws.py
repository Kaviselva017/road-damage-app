"""
backend/app/api/ws.py
======================
User-keyed WebSocket connection manager for RoadWatch.

Endpoint: /ws/complaints/{user_id}?token=<JWT>

Features:
- Auth via JWT query param (works for both citizens and officers)
- Keyed by user_id so status events reach the right client
- 30-second server heartbeat: {"event":"ping"} — client must pong or disconnected
- Structured event payload: {"event":"status_update","complaint_id":...}
- Clean WebSocketDisconnect handling
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30  # seconds
PONG_TIMEOUT = 10        # seconds after ping to wait for pong before closing


# ── Connection Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    """
    Manages one WebSocket per user_id.

    Each entry in active_connections is a (WebSocket, asyncio.Event) pair —
    the Event is set when the client sends a "pong" message.
    """

    def __init__(self) -> None:
        # user_id -> (websocket, pong_event)
        self.active_connections: dict[str, tuple[WebSocket, asyncio.Event]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        if user_id in self.active_connections:
            # Close the stale connection first
            old_ws, _ = self.active_connections[user_id]
            try:
                await old_ws.close(code=4000)
            except Exception:
                pass

        await websocket.accept()
        self.active_connections[user_id] = (websocket, asyncio.Event())
        logger.info("WS connected: user_id=%s  total=%d", user_id, len(self.active_connections))

    def disconnect(self, user_id: str) -> None:
        self.active_connections.pop(user_id, None)
        logger.info("WS disconnected: user_id=%s  remaining=%d", user_id, len(self.active_connections))

    async def send(self, user_id: str, payload: dict[str, Any]) -> bool:
        """Send a structured message to a single user. Returns False if not connected."""
        entry = self.active_connections.get(user_id)
        if not entry:
            return False
        ws, _ = entry
        try:
            await ws.send_text(json.dumps(payload))
            return True
        except Exception as exc:
            logger.warning("WS send failed for user_id=%s: %s", user_id, exc)
            self.disconnect(user_id)
            return False

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send a message to ALL connected users."""
        dead: list[str] = []
        for user_id, (ws, _) in list(self.active_connections.items()):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(user_id)
        for uid in dead:
            self.disconnect(uid)

    def notify_pong(self, user_id: str) -> None:
        entry = self.active_connections.get(user_id)
        if entry:
            _, pong_event = entry
            pong_event.set()

    def set_pong_event(self, user_id: str) -> asyncio.Event | None:
        entry = self.active_connections.get(user_id)
        return entry[1] if entry else None

    @property
    def connected_count(self) -> int:
        return len(self.active_connections)


# ── Module-level singleton ────────────────────────────────────────────────────

manager = ConnectionManager()


# ── Heartbeat coroutine ───────────────────────────────────────────────────────

async def _run_heartbeat(user_id: str, ws: WebSocket) -> None:
    """
    Ping the client every HEARTBEAT_INTERVAL seconds.
    If the client doesn't pong within PONG_TIMEOUT, close the connection.
    """
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)

        if user_id not in manager.active_connections:
            return

        pong_event = manager.set_pong_event(user_id)
        if pong_event is None:
            return

        pong_event.clear()

        try:
            await ws.send_text(json.dumps({"event": "ping"}))
        except Exception:
            manager.disconnect(user_id)
            return

        try:
            await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("WS pong timeout for user_id=%s — closing.", user_id)
            try:
                await ws.close(code=4008)
            except Exception:
                pass
            manager.disconnect(user_id)
            return


# ── WebSocket endpoint ────────────────────────────────────────────────────────

async def websocket_complaints(websocket: WebSocket, user_id: str, token: str | None = None):
    """
    /ws/complaints/{user_id}?token=<JWT>

    Validates JWT, maintains heartbeat, routes pong messages back through
    the manager, and handles clean disconnect.

    This function is registered as the WS route in main.py or a router.
    """
    from app.services.auth_service import decode_token  # local import avoids circular

    # ── Authenticate ──────────────────────────────────────────────────────────
    if not token:
        await websocket.close(code=4001)
        return

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001)
        return

    token_user_id = str(payload.get("sub") or "")
    # Citizen tokens use numeric sub; officers can also subscribe for own updates
    if token_user_id != user_id and payload.get("role") not in ("officer", "admin"):
        await websocket.close(code=4003)
        return

    # ── Connect ───────────────────────────────────────────────────────────────
    await manager.connect(user_id, websocket)

    heartbeat_task = asyncio.create_task(_run_heartbeat(user_id, websocket))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("event") == "pong":
                    manager.notify_pong(user_id)
            except (json.JSONDecodeError, AttributeError):
                pass  # ignore malformed messages

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS error for user_id=%s: %s", user_id, exc)
    finally:
        heartbeat_task.cancel()
        manager.disconnect(user_id)


# ── Payload builders (used by complaints.py) ─────────────────────────────────

def build_status_update_payload(
    complaint_id: str,
    status: str,
    severity: str,
    damage_type: str | None = None,
    confidence: float | None = None,
) -> dict:
    return {
        "event": "status_update",
        "complaint_id": complaint_id,
        "status": status,
        "severity": severity,
        "damage_type": damage_type,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def build_inference_payload(
    complaint_id: str,
    damage_type: str,
    confidence: float,
    severity: str,
) -> dict:
    return {
        "event": "inference_complete",
        "complaint_id": complaint_id,
        "damage_type": damage_type,
        "confidence": confidence,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
