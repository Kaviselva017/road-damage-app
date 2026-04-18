import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # complaint_id -> list of connected WebSockets
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, complaint_id: str, websocket: WebSocket):
        await websocket.accept()
        if complaint_id not in self.active_connections:
            self.active_connections[complaint_id] = []
        self.active_connections[complaint_id].append(websocket)

        from app.utils import metrics

        metrics.ACTIVE_WEBSOCKET_CONNECTIONS.inc()

        logger.info(f"WebSocket connected for {complaint_id}. Total: {len(self.active_connections[complaint_id])}")

    def disconnect(self, complaint_id: str, websocket: WebSocket):
        try:
            if complaint_id in self.active_connections:
                try:
                    self.active_connections[complaint_id].remove(websocket)
                except ValueError:
                    pass
                if not self.active_connections[complaint_id]:
                    del self.active_connections[complaint_id]

                from app.utils import metrics

                metrics.ACTIVE_WEBSOCKET_CONNECTIONS.dec()
        except Exception as e:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
            logger.error(f"Error during WebSocket disconnect: {e}")

    async def broadcast_status(self, complaint_id: str, status: str, extra_data: dict = None):
        if extra_data is None:
            extra_data = {}
        if complaint_id in self.active_connections:
            from datetime import datetime, timezone

            payload = {"complaint_id": complaint_id, "status": status, "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), **extra_data}
            message = json.dumps(payload)
            for connection in list(self.active_connections[complaint_id]):
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.warning(f"Error sending ws message to {complaint_id}: {e}")
                    self.disconnect(complaint_id, connection)


complaint_ws_manager = ConnectionManager()
