"""
Geo Service
Handles spatial mapping and query optimizations.
Since we use PostGIS in production and SQLite locally for dev, we gracefully
fallback to Haversine calculations when PostGIS operations fail or the dialect isn't postgresql.
"""

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import func

from app.models.models import Complaint


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance in meters between two points on the earth."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r


def find_nearby_complaints(lat, lng, db, radius_meters=500):
    """Find complaints within a radius."""
    if db.bind.dialect.name == "postgresql":
        point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
        return db.query(Complaint).filter(func.ST_DWithin(Complaint.location, point, radius_meters), Complaint.status != "rejected").all()
    else:
        lat_delta = radius_meters / 111320.0
        lng_delta = radius_meters / (111320.0 * cos(radians(lat)))
        comps = db.query(Complaint).filter(Complaint.latitude.between(lat - lat_delta, lat + lat_delta), Complaint.longitude.between(lng - lng_delta, lng + lng_delta), Complaint.status != "rejected").all()
        return [c for c in comps if haversine_distance(lng, lat, c.longitude, c.latitude) <= radius_meters]


def find_duplicate_complaint(lat, lng, damage_type, db, hours=24) -> bool:
    """Return True if a similar damage was reported recently nearby."""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Very tight radius for duplicate detections
    nearby = find_nearby_complaints(lat, lng, db, radius_meters=50)
    for c in nearby:
        created = c.created_at.replace(tzinfo=timezone.utc) if c.created_at.tzinfo is None else c.created_at
        if created >= time_threshold:
            current_dam = c.detected_damage_type or c.damage_type
            if current_dam == damage_type or not damage_type or current_dam == "multiple":
                return True
    return False
