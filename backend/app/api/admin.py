"""
RoadWatch Admin API — field names match EXACTLY what admin.html reads.

Verified from admin.html source:
  loadStats()    → stats.total, .pending, .in_progress, .completed,
                   .high, .medium, .low, .total_officers, .total_citizens,
                   .resolution_rate, .recent_7days
  loadOfficers() → o.total_complaints, .completed, .pending, .resolution_rate,
                   .performance, .zone, .is_active, .name, .email, .phone
  loadCitizens() → c.total_reports, .completed, .fixed, .high_severity,
                   .points, .is_active
  loadComplaints()→ c.complaint_id, .damage_type, .severity, .status,
                    .citizen_name, .citizen_phone, .officer_name, .address,
                    .created_at, .image_url
  chart/daily    → [{date, count}]
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
    high     = sum(1 for c in all_c if c.severity == "high")
    medium   = sum(1 for c in all_c if c.severity == "medium")
    low      = sum(1 for c in all_c if c.severity == "low")
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent   = sum(1 for c in all_c if c.created_at and c.created_at >= week_ago)
    rate     = round(done / total * 100, 1) if total else 0

    return {
        # exact field names admin.html uses:
        "total":           total,
        "pending":         pending + assigned,
        "in_progress":     in_prog,
        "completed":       done,
        "high":            high,
        "medium":          medium,
        "low":             low,
        "total_officers":  db.query(FieldOfficer).filter(FieldOfficer.is_admin == False).count(),
        "total_citizens":  db.query(User).count(),
        "resolution_rate": rate,
        "recent_7days":    recent,
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
            "id":              c.id,
            "complaint_id":    c.complaint_id or f"RD-{c.id:06d}",
            "description":     c.description or "",
            "address":         c.address or "",
            "latitude":        c.latitude,
            "longitude":       c.longitude,
            "area_type":       c.area_type or "",
            "damage_type":     c.damage_type or "pothole",
            "severity":        c.severity or "medium",
            "status":          c.status or "pending",
            "ai_confidence":   c.ai_confidence or 0,
            "priority_score":  c.priority_score or 0,
            "image_url":       c.image_url or "",
            "after_image_url": c.after_image_url or "",
            "officer_notes":   c.officer_notes or "",
            "allocated_fund":  c.allocated_fund or 0,
            "is_duplicate":    c.is_duplicate or False,
            "report_count":    c.report_count or 1,
            "created_at":      c.created_at.isoformat() if c.created_at else "",
            "resolved_at":     c.resolved_at.isoformat() if c.resolved_at else None,
            # exact names admin.html renders:
            "citizen_name":    user.name if user else "Unknown",
            "citizen_phone":   user.phone if user else "",
            "citizen_id":      c.user_id,
            "officer_name":    officer.name if officer else "Unassigned",
            "officer_id":      c.officer_id,
        })
    return result


@router.patch("/complaints/{complaint_id}/reassign")
def reassign_complaint(
    complaint_id: int,
    payload: ReassignPayload,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    complaint = (
        db.query(Complaint).filter(Complaint.id == complaint_id).first() or
        db.query(Complaint).filter(Complaint.complaint_id == str(complaint_id)).first()
    )
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
        c_all  = db.query(Complaint).filter(Complaint.officer_id == o.id).all()
        total  = len(c_all)
        done   = sum(1 for c in c_all if c.status == "completed")
        pend   = sum(1 for c in c_all if c.status in ("pending", "assigned"))
        rate   = round(done / total * 100, 1) if total else 0
        result.append({
            "id":               o.id,
            "name":             o.name,
            "email":            o.email,
            "phone":            o.phone or "",
            "zone":             o.zone or "",
            "is_active":        o.is_active,
            "last_login":       o.last_login.isoformat() if o.last_login else None,
            "created_at":       o.created_at.isoformat() if o.created_at else "",
            # exact names admin.html uses:
            "total_complaints": total,
            "completed":        done,
            "pending":          pend,
            "resolution_rate":  rate,
            "performance":      rate,
        })
    return result


@router.patch("/officers/{officer_id}")
def edit_officer(
    officer_id: int,
    payload: OfficerEdit,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    if payload.name     is not None: o.name             = payload.name
    if payload.phone    is not None: o.phone            = payload.phone
    if payload.zone     is not None: o.zone             = payload.zone
    if payload.password is not None: o.hashed_password  = pwd_ctx.hash(payload.password)
    db.commit()
    return {"message": "Officer updated"}


@router.delete("/officers/{officer_id}")
def delete_officer(
    officer_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    if o.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin")
    db.delete(o)
    db.commit()
    return {"message": "Officer deleted"}


@router.patch("/officers/{officer_id}/toggle")
def toggle_officer(
    officer_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    o.is_active = not o.is_active
    db.commit()
    return {"message": "Toggled", "is_active": o.is_active}


# ── Citizens ──────────────────────────────────────────────────────────────────

@router.get("/citizens")
def list_citizens(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    users = db.query(User).all()
    result = []
    for u in users:
        c_all  = db.query(Complaint).filter(Complaint.user_id == u.id).all()
        total  = len(c_all)
        done   = sum(1 for c in c_all if c.status == "completed")
        hi_sev = sum(1 for c in c_all if c.severity == "high")
        result.append({
            "id":            u.id,
            "name":          u.name,
            "email":         u.email,
            "phone":         u.phone or "",
            "is_active":     u.is_active,
            "created_at":    u.created_at.isoformat() if u.created_at else "",
            # exact names admin.html renders:
            "total_reports": total,
            "completed":     done,
            "fixed":         done,
            "high_severity": hi_sev,
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
    u = db.query(User).filter(User.id == citizen_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Citizen not found")
    db.delete(u)
    db.commit()
    return {"message": "Deleted"}


@router.patch("/citizens/{citizen_id}/toggle")
def toggle_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    u = db.query(User).filter(User.id == citizen_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Citizen not found")
    u.is_active = not u.is_active
    db.commit()
    return {"message": "Toggled", "is_active": u.is_active}


@router.post("/citizens/{citizen_id}/block")
def block_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    u = db.query(User).filter(User.id == citizen_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Citizen not found")
    u.is_active = False
    db.commit()
    return {"message": "Blocked"}


# ── Chart ─────────────────────────────────────────────────────────────────────

@router.get("/chart/daily")
def chart_daily(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
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