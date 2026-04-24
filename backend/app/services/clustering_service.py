import logging
import math

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.models import Complaint
from app.schemas.heatmap import ClusterPoint, Hotspot

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {"critical": 5.0, "high": 3.0, "medium": 2.0, "low": 1.0}

REPAIR_COSTS = {"pothole": 50000.0, "crack": 20000.0, "subsidence": 200000.0, "flooding": 150000.0, "debris": 10000.0}


def _get_severity_multiplier(severity: str) -> float:
    return SEVERITY_WEIGHTS.get(severity.lower(), 1.0)


def cluster_complaints(db: Session, grid_size_meters: int = 500) -> list[ClusterPoint]:
    """
    Cluster complaints into grid cells using PostGIS (prod) or Python (local).
    """
    is_postgres = db.bind.dialect.name == "postgresql"

    if is_postgres:
        # 1 deg ~ 111,000 meters at equator
        grid_deg = grid_size_meters / 111000.0

        # Raw PostGIS query for performance
        # We use ST_SnapToGrid on the geometry representation of our Geography column
        sql = text("""
            SELECT
                ST_Y(ST_SnapToGrid(location::geometry, :size)) as lat,
                ST_X(ST_SnapToGrid(location::geometry, :size)) as lng,
                COUNT(*) as count,
                AVG(ai_confidence) as avg_conf,
                (SELECT damage_type FROM complaints c2
                 WHERE ST_SnapToGrid(c2.location::geometry, :size) = ST_SnapToGrid(c1.location::geometry, :size)
                 GROUP BY damage_type ORDER BY COUNT(*) DESC LIMIT 1) as dominant_type,
                CASE
                    WHEN 'critical' = ANY(ARRAY_AGG(severity)) THEN 'critical'
                    WHEN 'high' = ANY(ARRAY_AGG(severity)) THEN 'high'
                    WHEN 'medium' = ANY(ARRAY_AGG(severity)) THEN 'medium'
                    ELSE 'low'
                END as max_sev,
                SUM(CASE
                    WHEN severity = 'critical' THEN 5
                    WHEN severity = 'high' THEN 3
                    WHEN severity = 'medium' THEN 2
                    ELSE 1
                END) as total_weight
            FROM complaints c1
            WHERE status != 'completed'
            GROUP BY ST_SnapToGrid(location::geometry, :size)
        """)

        results = db.execute(sql, {"size": grid_deg}).fetchall()
        return [ClusterPoint(lat=r.lat, lng=r.lng, count=r.count, weight=float(r.total_weight), dominant_damage_type=r.dominant_type or "pothole", max_severity=r.max_sev) for r in results]
    else:
        # Fallback for SQLite/Local Dev
        complaints = db.execute(
            select(
                Complaint.latitude,
                Complaint.longitude,
                Complaint.damage_type,
                Complaint.severity,
            ).filter(Complaint.status != "completed")
        ).all()
        clusters = {}  # (snap_lat, snap_lng) -> data

        grid_deg = grid_size_meters / 111000.0

        for c in complaints:
            if not c.latitude or not c.longitude:
                continue

            # Snap to grid
            snap_lat = round(c.latitude / grid_deg) * grid_deg
            # Adjust lng grid for latitude
            lng_deg = grid_deg / math.cos(math.radians(c.latitude))
            snap_lng = round(c.longitude / lng_deg) * lng_deg

            key = (round(snap_lat, 6), round(snap_lng, 6))
            if key not in clusters:
                clusters[key] = {"count": 0, "types": {}, "severities": [], "total_weight": 0.0, "lat": key[0], "lng": key[1]}

            node = clusters[key]
            node["count"] += 1
            node["types"][c.damage_type] = node["types"].get(c.damage_type, 0) + 1
            node["severities"].append(c.severity.lower() if c.severity else "low")
            node["total_weight"] += SEVERITY_WEIGHTS.get(c.severity.lower() if c.severity else "low", 1.0)

        final = []
        for _key, data in clusters.items():
            dominant = max(data["types"], key=data["types"].get) if data["types"] else "pothole"
            max_s = "low"
            for s in ["critical", "high", "medium", "low"]:
                if s in data["severities"]:
                    max_s = s
                    break

            final.append(ClusterPoint(lat=data["lat"], lng=data["lng"], count=data["count"], weight=data["total_weight"], dominant_damage_type=dominant, max_severity=max_s))
        return final


def get_hotspots(db: Session, min_count: int = 3) -> list[Hotspot]:
    """
    Returns clusters with high density + repair cost estimates.
    """
    clusters = cluster_complaints(db, grid_size_meters=500)
    hotspots = []

    for c in clusters:
        if c.count < min_count:
            continue

        # Find complaints in this grid cell for IDs
        # (Simplified: query DB for complaints near this cluster center)
        # In a real grid, we'd use the snap logic, but for hotspots we just query
        # the surrounding 250m radius.
        bbox_size = 0.005  # ~500m
        nearby = db.execute(
            select(
                Complaint.complaint_id,
                Complaint.damage_type,
            ).filter(
                Complaint.latitude.between(c.lat - bbox_size, c.lat + bbox_size),
                Complaint.longitude.between(c.lng - bbox_size, c.lng + bbox_size),
                Complaint.status != "completed",
            )
        ).all()

        ids = [comp.complaint_id for comp in nearby]

        # Group damage types for cost estimation
        type_counts = {}
        for comp in nearby:
            dtype = (comp.damage_type or "pothole").lower()
            type_counts[dtype] = type_counts.get(dtype, 0) + 1

        cost = sum(count * REPAIR_COSTS.get(dtype, 50000.0) for dtype, count in type_counts.items())

        hotspots.append(Hotspot(**c.dict(), estimated_repair_cost=cost, complaint_ids=ids))

    return sorted(hotspots, key=lambda x: x.weight, reverse=True)
