from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import FieldOfficer, Complaint
from app.services.auth_service import get_current_officer, hash_password

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
    name: Optional[str] = None
    zone: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    total = db.query(Complaint).count()
    open_c = db.query(Complaint).filter(Complaint.status.in_(["pending", "assigned", "in_progress"])).count()
    completed = db.query(Complaint).filter(Complaint.status == "completed").count()
    high_sev = db.query(Complaint).filter(Complaint.severity == "high").count()
    
    total_off = db.query(FieldOfficer).count()
    active_off = db.query(FieldOfficer).filter(FieldOfficer.is_active == True).count()
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    comps_today = db.query(Complaint).filter(Complaint.created_at >= today_start).count()
    
    avg_ps = db.query(func.avg(Complaint.priority_score)).scalar() or 0.0
    
    area_rows = db.query(Complaint.area_type, func.count(Complaint.id)).group_by(Complaint.area_type).all()
    by_area = [{"area": r[0] or "Unknown", "count": r[1]} for r in area_rows]
    
    status_rows = db.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()
    by_status = [{"status": r[0] or "pending", "count": r[1]} for r in status_rows]
    
    return {
        "total_complaints": total,
        "open": open_c,
        "completed": completed,
        "high_severity": high_sev,
        "total_officers": total_off,
        "active_officers": active_off,
        "complaints_today": comps_today,
        "avg_priority_score": round(float(avg_ps), 1),
        "by_area": by_area,
        "by_status": by_status
    }

@router.get("/officers")
def get_all_officers(db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    officers = db.query(FieldOfficer).all()
    res = []
    for o in officers:
        comps = db.query(Complaint).filter(Complaint.officer_id == o.id).all()
        comp_done = sum(1 for c in comps if c.status == "completed")
        comp_prog = sum(1 for c in comps if c.status == "in_progress")
        
        resolved = [c for c in comps if c.status == "completed" and c.resolved_at and c.created_at]
        avg_res = None
        if resolved:
            hours = [(c.resolved_at.replace(tzinfo=timezone.utc) - c.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600 for c in resolved]
            avg_res = round(sum(hours) / len(hours), 1)
            
        res.append({
            "id": o.id,
            "name": o.name,
            "email": o.email,
            "zone": o.zone,
            "is_active": o.is_active,
            "is_admin": o.is_admin,
            "complaints_assigned": len(comps),
            "complaints_completed": comp_done,
            "complaints_in_progress": comp_prog,
            "avg_resolution_hours": avg_res
        })
    return res

@router.post("/officers")
def create_officer(data: OfficerCreate, db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    dup = db.query(FieldOfficer).filter(FieldOfficer.email == data.email).first()
    if dup:
        raise HTTPException(400, "Email already taken")
        
    new_o = FieldOfficer(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        zone=data.zone,
        is_active=True,
        is_admin=False
    )
    db.add(new_o)
    db.commit()
    db.refresh(new_o)
    return {
        "id": new_o.id,
        "name": new_o.name,
        "email": new_o.email,
        "zone": new_o.zone,
        "is_active": new_o.is_active,
        "is_admin": new_o.is_admin
    }

@router.patch("/officers/{officer_id}")
def update_officer(officer_id: int, data: OfficerUpdate, db: Session = Depends(get_db), current_officer: FieldOfficer = Depends(require_admin)):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(404, "Not found")
    if data.is_active is False and officer_id == current_officer.id:
        raise HTTPException(400, "Cannot deactivate yourself")

    if data.name is not None: o.name = data.name
    if data.zone is not None: o.zone = data.zone
    if data.is_active is not None: o.is_active = data.is_active
    db.commit()
    db.refresh(o)
    return {
        "id": o.id,
        "name": o.name,
        "email": o.email,
        "zone": o.zone,
        "is_active": o.is_active,
        "is_admin": o.is_admin
    }

@router.delete("/officers/{officer_id}")
def delete_officer(officer_id: int, db: Session = Depends(get_db), current_officer: FieldOfficer = Depends(require_admin)):
    if officer_id == current_officer.id:
        raise HTTPException(400, "Cannot delete yourself")
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(404, "Not found")
    o.is_active = False
    db.commit()
    return {"status": "deactivated", "id": officer_id}

@router.get("/officers/{officer_id}/stats")
def officer_stats(officer_id: int, db: Session = Depends(get_db), _: FieldOfficer = Depends(require_admin)):
    comps = db.query(Complaint).filter(Complaint.officer_id == officer_id).order_by(Complaint.created_at.desc()).all()
    completed = sum(1 for c in comps if c.status == "completed")
    in_prog = sum(1 for c in comps if c.status == "in_progress")
    pending = sum(1 for c in comps if c.status in ("pending", "assigned"))
    
    resolved = [c for c in comps if c.status == "completed" and c.resolved_at and c.created_at]
    avg_res = None
    if resolved:
        hours = [(c.resolved_at.replace(tzinfo=timezone.utc) - c.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600 for c in resolved]
        avg_res = round(sum(hours) / len(hours), 1)

    def _mini(c):
        return {
            "complaint_id": c.complaint_id or f"RD-{c.id:06d}",
            "damage_type": c.damage_type,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }

    return {
        "total_assigned": len(comps),
        "completed": completed,
        "in_progress": in_prog,
        "pending": pending,
        "avg_resolution_hours": avg_res,
        "recent_complaints": [_mini(c) for c in comps[:5]]
    }