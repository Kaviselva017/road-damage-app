"""
RoadWatch Admin API — all endpoints match exactly what admin.html calls.
Citizen records include computed fields (total_reports, high_severity, etc.)
that admin.html's filterCitizens() renders.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from passlib.context import CryptContext
from datetime import datetime, timedelta

from app.database import get_db
from app.models.models import User, FieldOfficer, Complaint
from app.dependencies import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ───────────────────────────────────────────────────────────────────

class OfficerEdit(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    zone: Optional[str] = None
    password: Optional[str] = None


class ReassignPayload(BaseModel):
    officer_id: int


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    total    = db.query(Complaint).count()
    pending  = db.query(Complaint).filter(Complaint.status == "pending").count()
    done     = db.query(Complaint).filter(Complaint.status == "completed").count()
    in_prog  = db.query(Complaint).filter(Complaint.status == "in_progress").count()
    assigned = db.query(Complaint).filter(Complaint.status == "assigned").count()
    citizens = db.query(User).count()
    officers = db.query(FieldOfficer).filter(FieldOfficer.is_admin == False).count()

    # Completion rate %
    rate = round((done / total * 100), 1) if total else 0

    return {
        "total_complaints": total,
        "pending_complaints": pending,
        "resolved_complaints": done,
        "completed": done,
        "in_progress_complaints": in_prog,
        "assigned_complaints": assigned,
        "total_citizens": citizens,
        "total_officers": officers,
        "completion_rate": rate,
    }


# ── Complaints ────────────────────────────────────────────────────────────────

@router.get("/complaints")
def list_complaints(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    rows = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    result = []
    for c in rows:
        user    = db.query(User).filter(User.id == c.user_id).first()
        officer = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first() if c.officer_id else None
        result.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "description": c.description,
            "address": c.address or "",
            "latitude": c.latitude,
            "longitude": c.longitude,
            "area_type": c.area_type,
            "damage_type": c.damage_type,
            "severity": c.severity,
            "status": c.status,
            "ai_confidence": c.ai_confidence,
            "priority_score": c.priority_score,
            "image_url": c.image_url,
            "after_image_url": c.after_image_url,
            "officer_notes": c.officer_notes,
            "allocated_fund": c.allocated_fund,
            "is_duplicate": c.is_duplicate,
            "report_count": c.report_count,
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
            "citizen_name": user.name if user else "Unknown",
            "citizen_id": c.user_id,
            "officer_name": officer.name if officer else "Unassigned",
            "officer_id": c.officer_id,
        })
    return result


@router.patch("/complaints/{complaint_id}/reassign")
def reassign_complaint(
    complaint_id: int,
    payload: ReassignPayload,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == payload.officer_id).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    complaint.officer_id = payload.officer_id
    complaint.status = "assigned"
    db.commit()
    return {"message": "Reassigned", "officer_name": officer.name}


# ── Officers ──────────────────────────────────────────────────────────────────

@router.get("/officers")
def list_officers(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    officers = db.query(FieldOfficer).filter(FieldOfficer.is_admin == False).all()
    result = []
    for o in officers:
        # Compute stats admin.html renders
        total_assigned = db.query(Complaint).filter(Complaint.officer_id == o.id).count()
        completed      = db.query(Complaint).filter(
            Complaint.officer_id == o.id, Complaint.status == "completed"
        ).count()
        result.append({
            "id": o.id,
            "name": o.name,
            "email": o.email,
            "phone": o.phone,
            "zone": o.zone,
            "is_active": o.is_active,
            "last_login": o.last_login.isoformat() if o.last_login else None,
            "created_at": o.created_at.isoformat() if o.created_at else "",
            "total_assigned": total_assigned,
            "completed": completed,
        })
    return result


@router.patch("/officers/{officer_id}")
def edit_officer(
    officer_id: int,
    payload: OfficerEdit,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    if payload.name     is not None: officer.name  = payload.name
    if payload.phone    is not None: officer.phone = payload.phone
    if payload.zone     is not None: officer.zone  = payload.zone
    if payload.password is not None: officer.hashed_password = pwd_ctx.hash(payload.password)
    db.commit()
    return {"message": "Officer updated"}


@router.delete("/officers/{officer_id}")
def delete_officer(
    officer_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    if officer.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin account")
    db.delete(officer)
    db.commit()
    return {"message": "Officer deleted"}


@router.patch("/officers/{officer_id}/toggle")
def toggle_officer(
    officer_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    officer.is_active = not officer.is_active
    db.commit()
    return {"message": "Toggled", "is_active": officer.is_active}


# ── Citizens ──────────────────────────────────────────────────────────────────

@router.get("/citizens")
def list_citizens(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    users = db.query(User).all()
    result = []
    for u in users:
        # Compute stats that admin.html's filterCitizens() renders:
        # c.total_reports, c.fixed||c.completed, c.high_severity, c.points
        all_complaints   = db.query(Complaint).filter(Complaint.user_id == u.id).all()
        total_reports    = len(all_complaints)
        completed        = sum(1 for c in all_complaints if c.status == "completed")
        high_severity    = sum(1 for c in all_complaints if c.severity == "high")
        result.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "phone": u.phone or "",
            "reward_points": u.reward_points or 0,
            "points": u.reward_points or 0,          # alias admin.html uses
            "is_active": u.is_active,
            "total_reports": total_reports,
            "completed": completed,
            "fixed": completed,                       # alias admin.html uses
            "high_severity": high_severity,
            "created_at": u.created_at.isoformat() if u.created_at else "",
        })
    return result


@router.delete("/citizens/{citizen_id}")
def delete_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == citizen_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Citizen not found")
    db.delete(user)
    db.commit()
    return {"message": "Citizen deleted"}


@router.patch("/citizens/{citizen_id}/toggle")
def toggle_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == citizen_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Citizen not found")
    user.is_active = not user.is_active
    db.commit()
    return {"message": "Toggled", "is_active": user.is_active}


@router.post("/citizens/{citizen_id}/block")
def block_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == citizen_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Citizen not found")
    user.is_active = False
    db.commit()
    return {"message": "Citizen blocked"}


# ── Chart ─────────────────────────────────────────────────────────────────────

@router.get("/chart/daily")
def chart_daily(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    """Last 7 days complaint counts — admin.html renderDailyChart()"""
    result = []
    today = datetime.utcnow().date()
    for i in range(6, -1, -1):
        day   = today - timedelta(days=i)
        start = datetime(day.year, day.month, day.day)
        end   = start + timedelta(days=1)
        count = db.query(Complaint).filter(
            Complaint.created_at >= start,
            Complaint.created_at < end,
        ).count()
        result.append({"date": day.strftime("%b %d"), "count": count})
    return result