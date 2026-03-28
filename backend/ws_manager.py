import json
from typing import List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead_connections.append(connection)
        for connection in dead_connections:
            self.disconnect(connection)

    async def broadcast_new_complaint(self, complaint):
        await self.broadcast(
            {
                "type": "new_complaint",
                "complaint_id": complaint.complaint_id,
                "severity": complaint.severity.value,
                "latitude": complaint.latitude,
                "longitude": complaint.longitude,
                "address": complaint.address,
            }
        )

    async def broadcast_status_update(self, complaint):
        await self.broadcast(
            {
                "type": "status_update",
                "complaint_id": complaint.complaint_id,
                "status": complaint.status.value,
            }
        )


manager = ConnectionManager()
