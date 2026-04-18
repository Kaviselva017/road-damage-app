import logging
from datetime import datetime, timedelta, timezone

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_officer
from app.models.models import Complaint, FieldOfficer
from app.schemas.heatmap import ClusterPoint, Hotspot
from app.services import clustering_service
from app.services.cache_service import cache
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/map", tags=["map"])


@router.get("/heatmap", response_model=list[ClusterPoint])
@limiter.limit(os.getenv("RATE_LIMIT_HEATMAP", "60/minute"))
async def get_heatmap(request: Request, grid: int = Query(500, ge=100, le=2000), db: Session = Depends(get_db)):
    cache_key = f"map:heatmap:{grid}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        data = clustering_service.cluster_complaints(db, grid_size_meters=grid)
        # Convert Pydantic to dict for caching
        await cache.set(cache_key, [d.dict() for d in data], ttl_seconds=300)
        return data
    except Exception as e:
        logger.error(f"Heatmap generation failed: {e}")
        raise HTTPException(500, "Internal Server Error") from e


@router.get("/hotspots", response_model=list[Hotspot])
async def get_hotspots(
    min_count: int = Query(3, ge=1, le=20),
    db: Session = Depends(get_db),
    # Requires officer/admin
    officer: FieldOfficer = Depends(get_current_officer),
):
    cache_key = f"map:hotspots:{min_count}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    data = clustering_service.get_hotspots(db, min_count=min_count)
    await cache.set(cache_key, [d.dict() for d in data], ttl_seconds=120)
    return data


@router.get("/timeline")
async def get_map_timeline(days: int = Query(30), db: Session = Depends(get_db)):
    if days not in [7, 30, 90]:
        raise HTTPException(400, "Days must be 7, 30, or 90")

    cache_key = f"map:timeline:{days}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Group by date
    # SQLite/Postgres compatible date truncation
    results = (
        db.execute(select(func.date(Complaint.created_at).label("date"), func.count(Complaint.id).label("total"), func.sum(func.case((Complaint.severity == "high", 1), else_=0)).label("high_sev")).filter(Complaint.created_at >= start_date).group_by(func.date(Complaint.created_at)).order_by("date")).scalars().all()
    )

    data = [{"date": str(r.date), "count": r.total, "high_severity": int(r.high_sev or 0)} for r in results]
    await cache.set(cache_key, data, ttl_seconds=600)
    return data
