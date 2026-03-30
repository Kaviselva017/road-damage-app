"""
RoadWatch Admin API

Every field name returned matches EXACTLY what admin.html reads:

  loadStats()    → stats.total, stats.pending, stats.in_progress,
                   stats.completed, stats.high, stats.medium, stats.low,
                   stats.total_officers, stats.total_citizens,
                   stats.resolution_rate, stats.recent_7days

  loadOfficers() → o.total_complaints, o.completed, o.pending,
                   o.resolution_rate, o.zone, o.is_active

  loadCitizens() → c.total_reports, c.completed, c.fixed, c.high_severity,
                   c.points, c.reward_points, c.is_active

  loadComplaints()→ c.complaint_id, c.damage_type, c.severity, c.status,
                    c.citizen_name, c.officer_name, c.address, c.created_at,
                    c.image_url
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
    all_c    = db.query(Complaint).all()
    total    = len(all_c)
    pending  = sum(1 for c in all_c if c.status == "pending")
    assigned = sum(1 for c in all_c if c.status == "assigned")
    in_prog  = sum(1 for c in all_c if c.status == "in_progress")
    done     = sum(1 for c in all_c if c.status == "completed")
    rejected = sum(1 for c in all_c if c.status == "rejected")
    high     = sum(1 for c in all_c if c.severity == "high")
    medium   = sum(1 for c in all_c if c.severity == "medium")
    low      = sum(1 for c in all_c if c.severity == "low")

    resolution_rate = round(done / total * 100, 1) if total else 0

    # complaints in last 7 days
    week_ago    = datetime.utcnow() - timedelta(days=7)
    recent_7days = sum(1 for c in all_c if c.created_at and c.created_at >= week_ago)

    citizens = db.query(User).count()
    officers = db.query(FieldOfficer).filter(FieldOfficer.is_admin == False).count()

    return {
        # fields admin.html's loadStats() reads directly:
        "total":           total,
        "pending":         pending + assigned,   # pending + assigned shown as "pending"
        "in_progress":     in_prog,
        "completed":       done,
        "high":            high,
        "medium":          medium,
        "low":             low,
        "total_officers":  officers,
        "total_citizens":  citizens,
        "resolution_rate": resolution_rate,
        "recent_7days":    recent_7days,
        # extras for other uses
        "assigned":        assigned,
        "rejected":        rejected,
        "total_complaints": total,
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
            "id":             c.id,
            "complaint_id":   c.complaint_id,
            "description":    c.description or "",
            "address":        c.address or "",
            "latitude":       c.latitude,
            "longitude":      c.longitude,
            "area_type":      c.area_type or "",
            "damage_type":    c.damage_type or "",
            "severity":       c.severity or "medium",
            "status":         c.status or "pending",
            "ai_confidence":  c.ai_confidence or 0,
            "priority_score": c.priority_score or 0,
            "image_url":      c.image_url or "",
            "after_image_url":c.after_image_url or "",
            "officer_notes":  c.officer_notes or "",
            "allocated_fund": c.allocated_fund or 0,
            "is_duplicate":   c.is_duplicate or False,
            "report_count":   c.report_count or 1,
            "created_at":     c.created_at.isoformat() if c.created_at else "",
            "resolved_at":    c.resolved_at.isoformat() if c.resolved_at else None,
            # Fields admin.html renders directly:
            "citizen_name":   user.name if user else "Unknown",
            "citizen_phone":  user.phone if user else "",
            "citizen_id":     c.user_id,
            "officer_name":   officer.name if officer else "Unassigned",
            "officer_id":     c.officer_id,
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
        # try by string complaint_id
        complaint = db.query(Complaint).filter(Complaint.complaint_id == str(complaint_id)).first()
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
        complaints     = db.query(Complaint).filter(Complaint.officer_id == o.id).all()
        total_c        = len(complaints)
        completed_c    = sum(1 for c in complaints if c.status == "completed")
        pending_c      = sum(1 for c in complaints if c.status in ("pending", "assigned"))
        resolution     = round(completed_c / total_c * 100, 1) if total_c else 0
        result.append({
            "id":               o.id,
            "name":             o.name,
            "email":            o.email,
            "phone":            o.phone or "",
            "zone":             o.zone or "",
            "is_active":        o.is_active,
            "last_login":       o.last_login.isoformat() if o.last_login else None,
            "created_at":       o.created_at.isoformat() if o.created_at else "",
            # Fields admin.html renders (filterOfficers, chart, zone cards):
            "total_complaints": total_c,
            "completed":        completed_c,
            "pending":          pending_c,
            "resolution_rate":  resolution,
            "performance":      resolution,   # alias used by officerResolutionRate()
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
        complaints   = db.query(Complaint).filter(Complaint.user_id == u.id).all()
        total        = len(complaints)
        completed    = sum(1 for c in complaints if c.status == "completed")
        high_sev     = sum(1 for c in complaints if c.severity == "high")
        result.append({
            "id":            u.id,
            "name":          u.name,
            "email":         u.email,
            "phone":         u.phone or "",
            "is_active":     u.is_active,
            "created_at":    u.created_at.isoformat() if u.created_at else "",
            # Fields admin.html's filterCitizens() renders:
            "total_reports": total,
            "completed":     completed,
            "fixed":         completed,       # alias: c.fixed||c.completed
            "high_severity": high_sev,
            "points":        u.reward_points or 0,
            "reward_points": u.reward_points or 0,
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
    """Last 7 days complaint counts — renderDailyChart() in admin.html"""
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