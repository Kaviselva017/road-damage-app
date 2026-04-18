"""
RoadWatch — WebSocket Connection Manager

Single shared instance used by both main.py (startup) and the complaints
router.  Import `manager` from here everywhere — never instantiate a second
ConnectionManager.
"""

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.debug("[WS] client connected  total=%d", len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)
        logger.debug("[WS] client disconnected total=%d", len(self.active))

    async def broadcast(self, msg: dict) -> None:
        dead: list[WebSocket] = []
        payload = json.dumps(msg)
        for ws in list(self.active):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    # ── Convenience broadcast helpers ────────────────────────────

    async def broadcast_new_complaint(self, c) -> None:
        await self.broadcast(
            {
                "type": "new_complaint",
                "complaint_id": c.complaint_id,
                "severity": c.severity.value if hasattr(c.severity, "value") else str(c.severity),
                "latitude": c.latitude,
                "longitude": c.longitude,
                "address": c.address,
            }
        )

    async def broadcast_status_update(self, c) -> None:
        await self.broadcast(
            {
                "type": "status_update",
                "complaint_id": c.complaint_id,
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
            }
        )

    async def broadcast_fund_allocated(self, c) -> None:
        await self.broadcast(
            {
                "type": "fund_allocated",
                "complaint_id": c.complaint_id,
                "allocated_fund": getattr(c, "allocated_fund", 0) or 0,
            }
        )


# Single shared instance — import this everywhere
manager = ConnectionManager()
