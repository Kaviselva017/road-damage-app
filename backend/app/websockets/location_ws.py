import json
from datetime import datetime, timezone

from fastapi import WebSocket

from app.services.cache_service import cache


class LocationManager:
    def __init__(self):
        self.officer_connections: dict[int, WebSocket] = {}
        self.admin_connections: list[WebSocket] = []

    async def connect_officer(self, officer_id: int, ws: WebSocket):
        await ws.accept()
        self.officer_connections[officer_id] = ws

    async def connect_admin(self, ws: WebSocket):
        await ws.accept()
        self.admin_connections.append(ws)

    def disconnect_officer(self, officer_id: int):
        self.officer_connections.pop(officer_id, None)

    def disconnect_admin(self, ws: WebSocket):
        if ws in self.admin_connections:
            self.admin_connections.remove(ws)

    async def update_location(self, officer_id: int, name: str, zone: str, lat: float, lng: float):
        payload = {
            "officer_id": officer_id,
            "name": name,
            "zone": zone,
            "lat": lat,
            "lng": lng,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        # Cache for 5 minutes
        await cache.set(f"officer:location:{officer_id}", payload, ttl=300)

        # Broadcast to all admins
        event = json.dumps({"event": "officer_location", "data": payload})
        dead = []
        for ws in self.admin_connections:
            try:
                await ws.send_text(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.admin_connections.remove(ws)

    async def broadcast_to_admins(self, event_type: str, data: dict):
        event = json.dumps({"event": event_type, "data": data})
        dead = []
        for ws in self.admin_connections:
            try:
                await ws.send_text(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.admin_connections.remove(ws)


location_manager = LocationManager()
