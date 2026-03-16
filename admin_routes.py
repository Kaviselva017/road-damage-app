from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.models import Complaint, User, FieldOfficer, ComplaintStatus, SeverityLevel
from app.services.auth_service import get_current_officer
from pydantic import BaseModel

router = APIRouter()

# ── Admin auth check ──────────────────────────────────
def require_admin(current_officer: FieldOfficer = Depends(get_current_officer)):
    if not getattr(current_officer, 'is_admin', False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_officer

# ── Overview Stats ────────────────────────────────────
@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _=Depends(get_current_officer)):
    total = db.query(Complaint).count()
    pending = db.query(Complaint).filter(Complaint.status.in_([ComplaintStatus.PENDING, ComplaintStatus.ASSIGNED])).count()
    in_progress = db.query(Complaint).filter(Complaint.status == ComplaintStatus.IN_PROGRESS).count()
    completed = db.query(Complaint).filter(Complaint.status == ComplaintStatus.COMPLETED).count()
    high = db.query(Complaint).filter(Complaint.severity == SeverityLevel.HIGH).count()
    medium = db.query(Complaint).filter(Complaint.severity == SeverityLevel.MEDIUM).count()
    low = db.query(Complaint).filter(Complaint.severity == SeverityLevel.LOW).count()
    total_citizens = db.query(User).count()
    total_officers = db.query(FieldOfficer).count()
    resolution_rate = round((completed / total * 100), 1) if total > 0 else 0

    # Last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent = db.query(Complaint).filter(Complaint.created_at >= seven_days_ago).count()

    return {
        "total": total, "pending": pending, "in_progress": in_progress,
        "completed": completed, "high": high, "medium": medium, "low": low,
        "total_citizens": total_citizens, "total_officers": total_officers,
        "resolution_rate": resolution_rate, "recent_7days": recent
    }

# ── All Complaints ────────────────────────────────────
@router.get("/complaints")
def get_all_complaints(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0, limit: int = 200,
    db: Session = Depends(get_db),
    _=Depends(get_current_officer)
):
    query = db.query(Complaint)
    if status: query = query.filter(Complaint.status == status)
    if severity: query = query.filter(Complaint.severity == severity)
    complaints = query.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()
    return [_complaint_to_dict(c, db) for c in complaints]

def _complaint_to_dict(c, db):
    user = db.query(User).filter(User.id == c.user_id).first()
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first() if c.officer_id else None
    return {
        "complaint_id": c.complaint_id,
        "damage_type": c.damage_type.value if hasattr(c.damage_type, 'value') else c.damage_type,
        "severity": c.severity.value if hasattr(c.severity, 'value') else c.severity,
        "status": c.status.value if hasattr(c.status, 'value') else c.status,
        "latitude": c.latitude, "longitude": c.longitude,
        "address": c.address, "description": c.description,
        "ai_confidence": c.ai_confidence,
        "image_url": c.image_url,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        "citizen_name": user.name if user else "Unknown",
        "citizen_email": user.email if user else "",
        "citizen_phone": user.phone if user else "",
        "officer_name": officer.name if officer else "Unassigned",
        "officer_notes": c.officer_notes,
    }

# ── All Officers ──────────────────────────────────────
@router.get("/officers")
def get_all_officers(db: Session = Depends(get_db), _=Depends(get_current_officer)):
    officers = db.query(FieldOfficer).all()
    result = []
    for o in officers:
        total = db.query(Complaint).filter(Complaint.officer_id == o.id).count()
        completed = db.query(Complaint).filter(Complaint.officer_id == o.id, Complaint.status == ComplaintStatus.COMPLETED).count()
        pending = db.query(Complaint).filter(Complaint.officer_id == o.id, Complaint.status.in_([ComplaintStatus.PENDING, ComplaintStatus.ASSIGNED])).count()
        result.append({
            "id": o.id, "name": o.name, "email": o.email,
            "phone": getattr(o, 'phone', '—'), "zone": getattr(o, 'zone', '—'),
            "is_active": o.is_active,
            "total_complaints": total, "completed": completed, "pending": pending,
            "resolution_rate": round(completed/total*100,1) if total > 0 else 0
        })
    return result

# ── All Citizens ──────────────────────────────────────
@router.get("/citizens")
def get_all_citizens(db: Session = Depends(get_db), _=Depends(get_current_officer)):
    users = db.query(User).all()
    result = []
    for u in users:
        total = db.query(Complaint).filter(Complaint.user_id == u.id).count()
        completed = db.query(Complaint).filter(Complaint.user_id == u.id, Complaint.status == ComplaintStatus.COMPLETED).count()
        high = db.query(Complaint).filter(Complaint.user_id == u.id, Complaint.severity == SeverityLevel.HIGH).count()
        result.append({
            "id": u.id, "name": u.name, "email": u.email,
            "phone": getattr(u, 'phone', '—'),
            "points": getattr(u, 'points', 0),
            "is_active": getattr(u, 'is_active', True),
            "total_complaints": total, "completed": completed, "high_severity": high,
            "created_at": u.created_at.isoformat() if hasattr(u, 'created_at') and u.created_at else None
        })
    return result

# ── Reassign Complaint ────────────────────────────────
class ReassignRequest(BaseModel):
    officer_id: int

@router.patch("/complaints/{complaint_id}/reassign")
def reassign_complaint(
    complaint_id: str,
    req: ReassignRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_officer)
):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c: raise HTTPException(status_code=404, detail="Not found")
    c.officer_id = req.officer_id
    db.commit()
    return {"success": True}

# ── Toggle Officer Active ─────────────────────────────
@router.patch("/officers/{officer_id}/toggle")
def toggle_officer(officer_id: int, db: Session = Depends(get_db), _=Depends(get_current_officer)):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o: raise HTTPException(status_code=404, detail="Not found")
    o.is_active = not o.is_active
    db.commit()
    return {"is_active": o.is_active}

# ── Add Officer ───────────────────────────────────────
class OfficerCreate(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    zone: Optional[str] = None

@router.post("/officers")
def add_officer(req: OfficerCreate, db: Session = Depends(get_db), _=Depends(get_current_officer)):
    from app.services.auth_service import pwd_context
    existing = db.query(FieldOfficer).filter(FieldOfficer.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    officer = FieldOfficer(
        name=req.name,
        email=req.email,
        hashed_password=pwd_context.hash(req.password),
        phone=req.phone,
        zone=req.zone,
        is_active=True
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    return {"id": officer.id, "name": officer.name, "email": officer.email}

# ── Edit Officer ──────────────────────────────────────
class OfficerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    zone: Optional[str] = None
    password: Optional[str] = None

@router.patch("/officers/{officer_id}")
def update_officer(officer_id: int, req: OfficerUpdate, db: Session = Depends(get_db), _=Depends(get_current_officer)):
    from app.services.auth_service import pwd_context
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o: raise HTTPException(status_code=404, detail="Not found")
    if req.name: o.name = req.name
    if req.phone: o.phone = req.phone
    if req.zone: o.zone = req.zone
    if req.password: o.hashed_password = pwd_context.hash(req.password)
    db.commit()
    return {"success": True}

# ── Delete Officer ────────────────────────────────────
@router.delete("/officers/{officer_id}")
def delete_officer(officer_id: int, db: Session = Depends(get_db), _=Depends(get_current_officer)):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o: raise HTTPException(status_code=404, detail="Not found")
    # Unassign complaints
    db.query(Complaint).filter(Complaint.officer_id == officer_id).update({"officer_id": None, "status": ComplaintStatus.PENDING})
    db.delete(o)
    db.commit()
    return {"success": True}

# ── Toggle Citizen Active ─────────────────────────────
@router.patch("/citizens/{user_id}/toggle")
def toggle_citizen(user_id: int, db: Session = Depends(get_db), _=Depends(get_current_officer)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(status_code=404, detail="Not found")
    u.is_active = not getattr(u, 'is_active', True)
    db.commit()
    return {"is_active": u.is_active}

# ── Daily chart data ──────────────────────────────────
@router.get("/chart/daily")
def get_daily_chart(db: Session = Depends(get_db), _=Depends(get_current_officer)):
    result = []
    for i in range(7, 0, -1):
        day_start = datetime.utcnow().replace(hour=0,minute=0,second=0) - timedelta(days=i-1)
        day_end = day_start + timedelta(days=1)
        count = db.query(Complaint).filter(Complaint.created_at >= day_start, Complaint.created_at < day_end).count()
        result.append({"date": day_start.strftime("%d %b"), "count": count})
    return result
