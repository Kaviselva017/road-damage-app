import json
from typing import List
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, msg: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_new_complaint(self, c):
        await self.broadcast({
            "type": "new_complaint",
            "complaint_id": c.complaint_id,
            "severity":     c.severity,
            "latitude":     c.latitude,
            "longitude":    c.longitude,
            "address":      c.address,
        })

    async def broadcast_status_update(self, c):
        await self.broadcast({
            "type":         "status_update",
            "complaint_id": c.complaint_id,
            "status":       c.status,
        })


manager = ConnectionManager()