import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class AdminConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Admin WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event: str, data: dict):
        if not self.active_connections:
            return
        message = json.dumps({"event": event, "data": data})
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Error sending to admin ws: {e}")
                self.disconnect(connection)


admin_ws_manager = AdminConnectionManager()
