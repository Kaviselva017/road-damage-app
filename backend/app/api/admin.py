from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.models import Complaint, User, FieldOfficer, ComplaintStatus, SeverityLevel
from app.services.auth_service import get_current_officer

router = APIRouter()

def get_admin(db: Session = Depends(get_db), current_officer: FieldOfficer = Depends(get_current_officer)):
    """Any logged-in officer can access admin."""
    return current_officer


# ── Stats ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
def get_stats(db: Session = Depends(get_db), admin=Depends(get_admin)):
    total     = db.query(Complaint).count()
    pending   = db.query(Complaint).filter(Complaint.status == ComplaintStatus.PENDING).count()
    in_prog   = db.query(Complaint).filter(Complaint.status == ComplaintStatus.IN_PROGRESS).count()
    completed = db.query(Complaint).filter(Complaint.status == ComplaintStatus.COMPLETED).count()
    assigned  = db.query(Complaint).filter(Complaint.status == ComplaintStatus.ASSIGNED).count()
    high      = db.query(Complaint).filter(Complaint.severity == SeverityLevel.HIGH).count()
    medium    = db.query(Complaint).filter(Complaint.severity == SeverityLevel.MEDIUM).count()
    low       = db.query(Complaint).filter(Complaint.severity == SeverityLevel.LOW).count()
    citizens  = db.query(User).count()
    officers  = db.query(FieldOfficer).filter(FieldOfficer.is_active == True).count()

    # Recent 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_7days = db.query(Complaint).filter(Complaint.created_at >= seven_days_ago).count()

    # Avg resolution time
    resolved = db.query(Complaint).filter(
        Complaint.resolved_at != None,
        Complaint.created_at  != None
    ).all()
    avg_resolution = 0
    if resolved:
        times = []
        for c in resolved:
            try:
                if c.resolved_at and c.created_at:
                    times.append((c.resolved_at - c.created_at).total_seconds() / 3600)
            except Exception:
                pass
        avg_resolution = round(sum(times) / len(times), 1) if times else 0

    return {
        # FIX: frontend uses stats.total, stats.high, stats.medium, stats.low,
        #      stats.total_officers, stats.recent_7days — all were missing/misnamed
        "total":               total,
        "total_complaints":    total,        # keep legacy key too
        "pending":             pending + assigned,   # FIX: frontend shows "Pending/Assigned" together
        "pending_only":        pending,
        "assigned":            assigned,
        "in_progress":         in_prog,
        "completed":           completed,
        "high":                high,
        "high_severity":       high,         # legacy
        "medium":              medium,
        "medium_severity":     medium,       # legacy
        "low":                 low,
        "low_severity":        low,          # legacy
        "total_citizens":      citizens,
        "total_officers":      officers,
        "active_officers":     officers,     # legacy
        "recent_7days":        recent_7days,
        "avg_resolution_hours": avg_resolution,
        "resolution_rate":     round((completed / total * 100) if total > 0 else 0, 1),
    }


# ── All Complaints ─────────────────────────────────────────────────────────────
@router.get("/complaints")
def get_all_complaints(
    status:   Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0, limit: int = 200,
    db: Session = Depends(get_db),
    admin=Depends(get_admin)
):
    query = db.query(Complaint)
    if status:
        try:
            query = query.filter(Complaint.status == ComplaintStatus(status))
        except Exception:
            pass
    if severity:
        try:
            query = query.filter(Complaint.severity == SeverityLevel(severity))
        except Exception:
            pass
    complaints = query.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for c in complaints:
        officer_name = citizen_name = citizen_phone = None
        try:
            if c.officer_id:
                o = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first()
                officer_name = o.name if o else None
        except Exception:
            pass
        try:
            if c.user_id:
                u = db.query(User).filter(User.id == c.user_id).first()
                if u:
                    citizen_name  = u.name
                    citizen_phone = getattr(u, "phone", "")
        except Exception:
            pass

        item = {
            "id":           c.id,
            "complaint_id": c.complaint_id,
            "latitude":     c.latitude,
            "longitude":    c.longitude,
            "address":      c.address,
            "damage_type":  c.damage_type.value  if hasattr(c.damage_type,  "value") else str(c.damage_type),
            "severity":     c.severity.value     if hasattr(c.severity,     "value") else str(c.severity),
            "status":       c.status.value       if hasattr(c.status,       "value") else str(c.status),
            "ai_confidence":c.ai_confidence,
            "description":  c.description,
            "image_url":    c.image_url,
            "officer_notes":c.officer_notes,
            "created_at":   str(c.created_at),
            "resolved_at":  str(c.resolved_at) if c.resolved_at else None,
            "officer_name": officer_name,
            "citizen_name": citizen_name,
            "citizen_phone":citizen_phone,
        }
        for field in ["allocated_fund", "fund_note", "priority_score",
                      "rainfall_mm", "traffic_volume", "road_age_years", "weather_condition"]:
            try:
                item[field] = getattr(c, field, None)
            except Exception:
                item[field] = None
        result.append(item)
    return result


# ── Officers ──────────────────────────────────────────────────────────────────
@router.get("/officers")
def get_all_officers(db: Session = Depends(get_db), admin=Depends(get_admin)):
    officers = db.query(FieldOfficer).all()
    result = []
    for o in officers:
        total     = db.query(Complaint).filter(Complaint.officer_id == o.id).count()
        completed = db.query(Complaint).filter(
            Complaint.officer_id == o.id,
            Complaint.status     == ComplaintStatus.COMPLETED
        ).count()
        pending   = db.query(Complaint).filter(
            Complaint.officer_id == o.id,
            Complaint.status.in_([ComplaintStatus.PENDING, ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS])
        ).count()
        high      = db.query(Complaint).filter(
            Complaint.officer_id == o.id,
            Complaint.severity   == SeverityLevel.HIGH
        ).count()
        result.append({
            "id":               o.id,
            "name":             o.name,
            "email":            o.email,
            "phone":            getattr(o, "phone", ""),
            "zone":             o.zone,
            "is_active":        o.is_active,
            "total_complaints": total,
            "completed":        completed,
            "pending":          pending,
            "high_severity":    high,
            "performance":      round((completed / total * 100) if total > 0 else 0, 1),
            "resolution_rate":  round((completed / total * 100) if total > 0 else 0, 1),
        })
    return result


# ── Citizens ──────────────────────────────────────────────────────────────────
@router.get("/citizens")
def get_all_citizens(db: Session = Depends(get_db), admin=Depends(get_admin)):
    users = db.query(User).all()
    result = []
    for u in users:
        total = db.query(Complaint).filter(Complaint.user_id == u.id).count()
        high  = db.query(Complaint).filter(
            Complaint.user_id  == u.id,
            Complaint.severity == SeverityLevel.HIGH
        ).count()
        fixed = db.query(Complaint).filter(
            Complaint.user_id == u.id,
            Complaint.status  == ComplaintStatus.COMPLETED
        ).count()
        result.append({
            "id":            u.id,
            "name":          u.name,
            "email":         u.email,
            "phone":         getattr(u, "phone", ""),
            "points":        getattr(u, "points", 0),
            "is_active":     getattr(u, "is_active", True),
            "total_reports": total,
            "high_severity": high,
            "fixed":         fixed,
            "completed":     fixed,
        })
    return result


# ── Officer CRUD ──────────────────────────────────────────────────────────────
@router.patch("/officers/{officer_id}")
async def update_officer(officer_id: int, request: Request,
                         db: Session = Depends(get_db), admin=Depends(get_admin)):
    body = await request.json()
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    if "name"      in body: o.name      = body["name"]
    if "phone"     in body: o.phone     = body["phone"]
    if "zone"      in body: o.zone      = body["zone"]
    if "is_active" in body: o.is_active = body["is_active"]
    if body.get("password"):
        from app.services.auth_service import pwd_context
        o.hashed_password = pwd_context.hash(body["password"])
    db.commit()
    db.refresh(o)
    return {
        "id": o.id, "name": o.name, "email": o.email,
        "zone": o.zone, "is_active": o.is_active,
        "phone": getattr(o, "phone", "")
    }


# FIX: Frontend calls PATCH /admin/officers/{id}/toggle but endpoint didn't exist
@router.patch("/officers/{officer_id}/toggle")
async def toggle_officer(officer_id: int,
                         db: Session = Depends(get_db), admin=Depends(get_admin)):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    o.is_active = not o.is_active
    db.commit()
    return {"id": o.id, "is_active": o.is_active, "message": "Officer updated"}


@router.delete("/officers/{officer_id}")
def delete_officer(officer_id: int,
                   db: Session = Depends(get_db), admin=Depends(get_admin)):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    db.query(Complaint).filter(Complaint.officer_id == officer_id).update(
        {"officer_id": None, "status": ComplaintStatus.PENDING}
    )
    db.delete(o)
    db.commit()
    return {"message": "Officer deleted"}


# ── Citizen actions ───────────────────────────────────────────────────────────
@router.patch("/citizens/{user_id}/block")
async def toggle_citizen_block(user_id: int, request: Request,
                               db: Session = Depends(get_db), admin=Depends(get_admin)):
    body = await request.json()
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        u.is_active = body.get("is_active", True)
        db.commit()
    except Exception:
        db.rollback()
    return {"id": u.id, "is_active": getattr(u, "is_active", True), "message": "Updated"}


# FIX: Frontend calls PATCH /admin/citizens/{id}/toggle but endpoint didn't exist
@router.patch("/citizens/{user_id}/toggle")
async def toggle_citizen(user_id: int,
                         db: Session = Depends(get_db), admin=Depends(get_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        u.is_active = not getattr(u, "is_active", True)
        db.commit()
    except Exception:
        db.rollback()
    return {"id": u.id, "is_active": getattr(u, "is_active", True)}


# FIX: Frontend calls DELETE /admin/citizens/{id} but endpoint didn't exist
@router.delete("/citizens/{user_id}")
def delete_citizen(user_id: int,
                   db: Session = Depends(get_db), admin=Depends(get_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        # Anonymise their complaints rather than hard-delete
        db.query(Complaint).filter(Complaint.user_id == user_id).update({"user_id": None})
        db.delete(u)
        db.commit()
        return {"message": "Citizen deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Reassign complaint ─────────────────────────────────────────────────────────
@router.patch("/complaints/{complaint_id}/reassign")
async def reassign_complaint(complaint_id: str, request: Request,
                             db: Session = Depends(get_db), admin=Depends(get_admin)):
    body = await request.json()
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    new_officer_id = body.get("officer_id")
    c.officer_id = new_officer_id
    c.status     = ComplaintStatus.ASSIGNED
    db.commit()

    # Notify officer — snapshot ORM values before thread to avoid DetachedInstanceError
    officer_notified = False
    try:
        import threading as _t3, logging as _l3
        from app.services.notification_service import notify_officer_assigned
        officer = db.query(FieldOfficer).filter(FieldOfficer.id == new_officer_id).first()
        if officer:
            officer_notified = True
            # Snapshot complaint + officer into plain objects
            class _CS:
                complaint_id  = str(c.complaint_id)
                severity      = type("S",(),{"value": c.severity.value if hasattr(c.severity,"value") else str(c.severity)})()
                damage_type   = type("D",(),{"value": c.damage_type.value if hasattr(c.damage_type,"value") else str(c.damage_type)})()
                priority_score= float(getattr(c,"priority_score",0) or 0)
                area_type     = str(getattr(c,"area_type","unknown") or "unknown")
                address       = str(c.address or "")
                latitude      = float(c.latitude)
                longitude     = float(c.longitude)
                description   = str(c.description or "Road damage detected.")
            class _OS:
                email = str(officer.email or "")
                name  = str(officer.name  or "")
                id    = officer.id
            _cs, _os = _CS(), _OS()
            def _send_reassign():
                try:
                    ok = notify_officer_assigned(_os, _cs)
                    _l3.getLogger(__name__).info(f"Reassign email {'SENT' if ok else 'FAILED'} → {_os.email}")
                except Exception as ex:
                    _l3.getLogger(__name__).warning(f"Reassign notification error: {ex}")
            _t3.Thread(target=_send_reassign, daemon=True).start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Officer notification setup error: {e}")

    return {"message": "Complaint reassigned", "officer_notified": officer_notified}


# ── Charts ────────────────────────────────────────────────────────────────────
@router.get("/chart/daily")
def daily_chart(db: Session = Depends(get_db), admin=Depends(get_admin)):
    complaints = db.query(Complaint).all()
    daily: dict = {}
    for c in complaints:
        try:
            if c.created_at:
                day = str(c.created_at)[:10]
                daily[day] = daily.get(day, 0) + 1
        except Exception:
            pass
    sorted_days = sorted(daily.items())[-14:]
    return [{"date": d, "count": n} for d, n in sorted_days]


# ── Login logs ────────────────────────────────────────────────────────────────
@router.get("/login-logs")
def get_login_logs(db: Session = Depends(get_db), admin=Depends(get_admin)):
    try:
        result = db.execute(text("SELECT * FROM login_logs ORDER BY logged_in_at DESC LIMIT 100"))
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []