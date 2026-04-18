from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Complaint, FieldOfficer
from app.services.auth_service import get_current_officer, hash_password
from app.services.cache_service import cache

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(officer: FieldOfficer = Depends(get_current_officer)):
    if not officer.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return officer


class OfficerCreate(BaseModel):
    name: str
    email: str
    password: str
    zone: str


class OfficerUpdate(BaseModel):
    name: str | None = None
    zone: str | None = None
    is_active: bool | None = None


@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    total = len(db.execute(select(Complaint)).scalars().all())
    open_c = len(db.execute(select(Complaint).filter(Complaint.status.in_(["pending", "assigned", "in_progress"]))).scalars().all())
    completed = len(db.execute(select(Complaint).filter(Complaint.status == "completed")).scalars().all())
    high_sev = len(db.execute(select(Complaint).filter(Complaint.severity == "high")).scalars().all())

    total_off = len(db.execute(select(FieldOfficer)).scalars().all())
    active_off = len(db.execute(select(FieldOfficer).filter(FieldOfficer.is_active.is_(True))).scalars().all())

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    comps_today = len(db.execute(select(Complaint).filter(Complaint.created_at >= today_start)).scalars().all())

    avg_ps = select(func.avg(Complaint.priority_score)).scalar() or 0.0

    area_rows = db.execute(select(Complaint.area_type, func.count(Complaint.id)).group_by(Complaint.area_type)).scalars().all()
    by_area = [{"area": r[0] or "Unknown", "count": r[1]} for r in area_rows]

    status_rows = db.execute(select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)).scalars().all()
    by_status = [{"status": r[0] or "pending", "count": r[1]} for r in status_rows]

    return {"total_complaints": total, "open": open_c, "completed": completed, "high_severity": high_sev, "total_officers": total_off, "active_officers": active_off, "complaints_today": comps_today, "avg_priority_score": round(float(avg_ps), 1), "by_area": by_area, "by_status": by_status}


@router.get("/officers")
def get_all_officers(db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    officers = db.execute(select(FieldOfficer)).scalars().all()
    res = []
    for o in officers:
        comps = db.execute(select(Complaint).filter(Complaint.officer_id == o.id)).scalars().all()
        comp_done = sum(1 for c in comps if c.status == "completed")
        comp_prog = sum(1 for c in comps if c.status == "in_progress")

        resolved = [c for c in comps if c.status == "completed" and c.resolved_at and c.created_at]
        avg_res = None
        if resolved:
            hours = [(c.resolved_at.replace(tzinfo=timezone.utc) - c.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600 for c in resolved]
            avg_res = round(sum(hours) / len(hours), 1)

        res.append({"id": o.id, "name": o.name, "email": o.email, "zone": o.zone, "is_active": o.is_active, "is_admin": o.is_admin, "complaints_assigned": len(comps), "complaints_completed": comp_done, "complaints_in_progress": comp_prog, "avg_resolution_hours": avg_res})
    return res


@router.post("/officers")
def create_officer(data: OfficerCreate, db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    dup = db.execute(select(FieldOfficer).filter(FieldOfficer.email == data.email)).scalars().first()
    if dup:
        raise HTTPException(400, "Email already taken")

    new_o = FieldOfficer(name=data.name, email=data.email, hashed_password=hash_password(data.password), zone=data.zone, is_active=True, is_admin=False)
    db.add(new_o)
    db.commit()
    db.refresh(new_o)
    return {"id": new_o.id, "name": new_o.name, "email": new_o.email, "zone": new_o.zone, "is_active": new_o.is_active, "is_admin": new_o.is_admin}


@router.patch("/officers/{officer_id}")
def update_officer(officer_id: int, data: OfficerUpdate, db: Session = Depends(get_db), current_officer: FieldOfficer = Depends(require_admin)):
    o = db.execute(select(FieldOfficer).filter(FieldOfficer.id == officer_id)).scalars().first()
    if not o:
        raise HTTPException(404, "Not found")
    if data.is_active is False and officer_id == current_officer.id:
        raise HTTPException(400, "Cannot deactivate yourself")

    if data.name is not None:
        o.name = data.name
    if data.zone is not None:
        o.zone = data.zone
    if data.is_active is not None:
        o.is_active = data.is_active
    db.commit()
    db.refresh(o)
    return {"id": o.id, "name": o.name, "email": o.email, "zone": o.zone, "is_active": o.is_active, "is_admin": o.is_admin}


@router.delete("/officers/{officer_id}")
def delete_officer(officer_id: int, db: Session = Depends(get_db), current_officer: FieldOfficer = Depends(require_admin)):
    if officer_id == current_officer.id:
        raise HTTPException(400, "Cannot delete yourself")
    o = db.execute(select(FieldOfficer).filter(FieldOfficer.id == officer_id)).scalars().first()
    if not o:
        raise HTTPException(404, "Not found")
    o.is_active = False
    db.commit()
    return {"status": "deactivated", "id": officer_id}


@router.get("/officers/{officer_id}/stats")
def officer_stats(officer_id: int, db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    comps = db.execute(select(Complaint).filter(Complaint.officer_id == officer_id).order_by(Complaint.created_at.desc())).scalars().all()
    completed = sum(1 for c in comps if c.status == "completed")
    in_prog = sum(1 for c in comps if c.status == "in_progress")
    pending = sum(1 for c in comps if c.status in ("pending", "assigned"))

    resolved = [c for c in comps if c.status == "completed" and c.resolved_at and c.created_at]
    avg_res = None
    if resolved:
        hours = [(c.resolved_at.replace(tzinfo=timezone.utc) - c.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600 for c in resolved]
        avg_res = round(sum(hours) / len(hours), 1)

    def _mini(c):
        return {"complaint_id": c.complaint_id or f"RD-{c.id:06d}", "damage_type": c.damage_type, "status": c.status, "created_at": c.created_at.isoformat() if c.created_at else None}

    return {"total_assigned": len(comps), "completed": completed, "in_progress": in_prog, "pending": pending, "avg_resolution_hours": avg_res, "recent_complaints": [_mini(c) for c in comps[:5]]}


@router.get("/officers/locations")
async def get_officer_locations(_: FieldOfficer = Depends(require_admin)):
    data = await cache.list("officer:location:")
    valid = []
    now = datetime.now(timezone.utc)
    for entry in data:
        try:
            up = datetime.fromisoformat(entry.get("updated_at"))
            if (now - up).total_seconds() <= 300:
                valid.append(entry)
        except (ValueError, TypeError):
            pass
    return valid
