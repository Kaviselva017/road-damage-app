"""
RoadWatch — Admin API
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.models import Complaint, ComplaintOfficer, FieldOfficer, User
from app.schemas.schemas import OfficerUpdate, ReassignUpdate
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _iso(dt):
    if dt is None: return None
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _ostats(o: FieldOfficer, db: Session) -> dict:
    total = db.query(Complaint).filter(Complaint.officer_id == o.id).count()
    done  = db.query(Complaint).filter(Complaint.officer_id == o.id, Complaint.status == "completed").count()
    pend  = db.query(Complaint).filter(Complaint.officer_id == o.id, Complaint.status.in_(["pending","assigned"])).count()
    prog  = db.query(Complaint).filter(Complaint.officer_id == o.id, Complaint.status == "in_progress").count()
    return {"id": o.id, "name": o.name, "email": o.email,
            "phone": o.phone, "zone": o.zone, "is_admin": o.is_admin, "is_active": o.is_active,
            "total_complaints": total, "completed": done, "pending": pend, "in_progress": prog}


def _ustats(u: User, db: Session) -> dict:
    total = db.query(Complaint).filter(Complaint.user_id == u.id).count()
    high  = db.query(Complaint).filter(Complaint.user_id == u.id, Complaint.severity == "high").count()
    fixed = db.query(Complaint).filter(Complaint.user_id == u.id, Complaint.status == "completed").count()
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone,
            "is_active": u.is_active, "reward_points": u.reward_points or 0,
            "total_reports": total, "high_severity": high, "fixed": fixed, "completed": fixed,
            "created_at": _iso(u.created_at)}


# ── Stats ─────────────────────────────────────────────────────
@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    all_c = db.query(Complaint).all()
    def cs(s): return sum(1 for c in all_c if c.status == s)
    def sv(s): return sum(1 for c in all_c if c.severity == s)

    cutoff = datetime.utcnow() - timedelta(days=7)
    recent = sum(1 for c in all_c if c.created_at and c.created_at >= cutoff)

    total_officers  = db.query(FieldOfficer).count()
    active_officers = db.query(FieldOfficer).filter(FieldOfficer.is_active == True).count()
    total_citizens  = db.query(User).count()

    total     = len(all_c)
    pending   = cs("pending") + cs("assigned")
    completed = cs("completed")
    high      = sv("high")

    return {
        # Keys the frontend reads
        "total": total, "pending": pending,
        "in_progress": cs("in_progress"), "completed": completed,
        "rejected": cs("rejected"),
        "high": high, "medium": sv("medium"), "low": sv("low"),
        "total_officers": total_officers, "active_officers": active_officers,
        "total_citizens": total_citizens, "recent_7days": recent,
        # Alias keys for backward compat
        "total_complaints": total, "high_severity": high,
        "pending_count": pending, "completed_count": completed,
    }


# ── Admin chart: daily trends ─────────────────────────────────
@router.get("/chart/daily")
def chart_daily(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Return last 14 days complaint counts."""
    from collections import defaultdict
    cutoff = datetime.utcnow() - timedelta(days=14)
    rows = db.query(Complaint).filter(Complaint.created_at >= cutoff).all()
    counts = defaultdict(int)
    for c in rows:
        if c.created_at:
            day = c.created_at.strftime("%d %b")
            counts[day] += 1
    result = []
    for i in range(13, -1, -1):
        d = datetime.utcnow() - timedelta(days=i)
        label = d.strftime("%d %b")
        result.append({"date": label, "count": counts.get(label, 0)})
    return result


# ── Complaints ─────────────────────────────────────────────────
@router.get("/complaints")
def admin_complaints(
    status: Optional[str] = None, severity: Optional[str] = None,
    db: Session = Depends(get_db), _=Depends(get_current_admin),
):
    from app.api.complaints import _c
    q = db.query(Complaint)
    if status:   q = q.filter(Complaint.status == status)
    if severity: q = q.filter(Complaint.severity == severity)
    rows = q.order_by(Complaint.priority_score.desc(), Complaint.created_at.desc()).all()
    return [_c(r, db) for r in rows]


@router.patch("/complaints/{complaint_id}/reassign")
def reassign(
    complaint_id: str, data: ReassignUpdate,
    db: Session = Depends(get_db), _=Depends(get_current_admin),
):
    from app.api.complaints import _c
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c: raise HTTPException(404, "Complaint not found")
    o = db.query(FieldOfficer).filter(FieldOfficer.id == data.officer_id).first()
    if not o: raise HTTPException(404, "Officer not found")
    c.officer_id = data.officer_id
    c.status = "assigned"
    db.add(ComplaintOfficer(complaint_id=complaint_id, officer_id=data.officer_id,
                            assigned_at=datetime.utcnow()))
    db.commit()
    return _c(c, db)


# ── Officers ───────────────────────────────────────────────────
@router.get("/officers")
def get_officers(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return [_ostats(o, db) for o in db.query(FieldOfficer).all()]


@router.patch("/officers/{oid}")
def update_officer(
    oid: int, data: OfficerUpdate,
    db: Session = Depends(get_db), _=Depends(get_current_admin),
):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == oid).first()
    if not o: raise HTTPException(404, "Officer not found")
    if data.name:     o.name  = data.name
    if data.phone:    o.phone = data.phone
    if data.zone:     o.zone  = data.zone
    if data.password: o.hashed_password = hash_password(data.password)
    db.commit()
    return _ostats(o, db)


@router.patch("/officers/{oid}/toggle")
def toggle_officer(oid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == oid).first()
    if not o: raise HTTPException(404, "Officer not found")
    o.is_active = not o.is_active
    db.commit()
    return {"id": o.id, "is_active": o.is_active, "name": o.name}


@router.delete("/officers/{oid}")
def delete_officer(oid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == oid).first()
    if not o: raise HTTPException(404, "Officer not found")
    db.query(Complaint).filter(Complaint.officer_id == oid).update(
        {"officer_id": None, "status": "pending"}
    )
    db.delete(o)
    db.commit()
    return {"deleted": True, "id": oid}


# ── Citizens ───────────────────────────────────────────────────
@router.get("/citizens")
def get_citizens(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return [_ustats(u, db) for u in db.query(User).all()]


@router.patch("/citizens/{uid}/toggle")
def toggle_citizen(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404, "Citizen not found")
    u.is_active = not u.is_active
    db.commit()
    return {"id": u.id, "is_active": u.is_active, "name": u.name}


@router.delete("/citizens/{uid}")
def delete_citizen(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404, "Citizen not found")
    u.is_active = False
    db.commit()
    return {"deleted": True, "id": uid}