"""
RoadWatch — Complaints API
Uses plain strings for status/severity/damage_type — no SQLAlchemy Enum issues.
All datetimes returned with Z suffix for correct browser parsing.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_officer, get_current_user
from app.models.models import Complaint, ComplaintOfficer, FieldOfficer, Notification, User
from app.schemas.schemas import FundUpdate, StatusUpdate
from app.services import ai_service
from app.ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/complaints", tags=["complaints"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

VALID_STATUSES  = {"pending", "assigned", "in_progress", "completed", "rejected"}
VALID_SEVERITIES = {"high", "medium", "low"}
VALID_DAMAGES   = {"pothole", "crack", "surface_damage", "multiple"}


def _now():
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """Always return ISO with Z so ALL browsers parse correctly."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _area(addr: str) -> str:
    a = (addr or "").lower()
    if any(w in a for w in ["hospital", "clinic", "medical", "health"]): return "hospital"
    if any(w in a for w in ["school", "college", "university", "academy"]): return "school"
    if any(w in a for w in ["highway", "nh-", "sh-", "expressway"]): return "highway"
    if any(w in a for w in ["mall", "market", "shopping", "commercial"]): return "market"
    return "residential"


def _priority(sev: str, dmg: str, area: str) -> float:
    s = {"high": 35, "medium": 20, "low": 10}.get(sev, 10)
    d = {"pothole": 5, "multiple": 8, "crack": 3, "surface_damage": 2}.get(dmg, 0)
    a = {"hospital": 30, "school": 25, "highway": 25, "market": 20, "residential": 10}.get(area, 10)
    t = {"hospital": 20, "school": 18, "market": 18, "highway": 16, "residential": 8}.get(area, 8)
    r = {"pothole": 15, "multiple": 14, "crack": 8, "surface_damage": 6}.get(dmg, 6)
    return min(float(s + d + a + t + r), 100.0)


def _best_officer(db: Session) -> Optional[FieldOfficer]:
    officers = db.query(FieldOfficer).filter(
        FieldOfficer.is_active == True,
        FieldOfficer.is_admin  == False,
    ).all()
    if not officers:
        return None
    return min(officers, key=lambda o: db.query(Complaint).filter(
        Complaint.officer_id == o.id,
        Complaint.status.in_(["pending", "assigned"]),
    ).count())


def _c(c: Complaint, db: Session) -> dict:
    oname, uname = None, None
    if c.officer_id:
        o = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first()
        oname = o.name if o else None
    if c.user_id:
        u = db.query(User).filter(User.id == c.user_id).first()
        uname = u.name if u else None
    return {
        "id":             c.id,
        "complaint_id":   c.complaint_id,
        "user_id":        c.user_id,
        "officer_id":     c.officer_id,
        "officer_name":   oname,
        "citizen_name":   uname,
        "latitude":       c.latitude,
        "longitude":      c.longitude,
        "address":        c.address,
        "area_type":      c.area_type,
        "damage_type":    c.damage_type,
        "severity":       c.severity,
        "ai_confidence":  c.ai_confidence,
        "description":    c.description,
        "image_url":      c.image_url,
        "after_image_url": c.after_image_url,
        "status":         c.status,
        "officer_notes":  c.officer_notes,
        "priority_score": c.priority_score,
        "allocated_fund": c.allocated_fund,
        "fund_note":      c.fund_note,
        "is_duplicate":   c.is_duplicate,
        "duplicate_of":   c.duplicate_of,
        "created_at":     _iso(c.created_at),
        "resolved_at":    _iso(c.resolved_at),
    }


# ── Submit ─────────────────────────────────────────────────────
@router.post("/submit")
async def submit(
    latitude:  float = Form(...),
    longitude: float = Form(...),
    address:   Optional[str] = Form(None),
    nearby_sensitive: Optional[str] = Form(None),
    image:     UploadFile = File(...),
    db:        Session = Depends(get_db),
    user:      User    = Depends(get_current_user),
):
    # Basic file check
    if not image or not image.filename:
        raise HTTPException(400, "Missing image file")

    # Save image
    ext      = Path(image.filename).suffix or ".jpg"
    fname    = f"{uuid.uuid4().hex}{ext}"
    fpath    = Path(UPLOAD_DIR) / fname
    img_bytes = await image.read()
    with open(fpath, "wb") as f:
        f.write(img_bytes)

    # Road Image Validation (Accuracy)
    is_road, conf = ai_service.is_road_image(str(fpath))
    if not is_road:
        # Delete invalid file
        if fpath.exists(): fpath.unlink()
        raise HTTPException(400, f"Image rejected: Not a road or damage photo (Confidence: {conf})")

    img_hash = ai_service.image_hash(img_bytes)

    # Duplicate check — Hash first
    dup = db.query(Complaint).filter(
        Complaint.image_hash == img_hash,
        Complaint.status != "rejected",
    ).first()

    # Duplicate check — Proximity (Same region)
    if not dup:
        margin = 0.00015
        nearby_candidates = db.query(Complaint).filter(
            Complaint.latitude.between(latitude - margin, latitude + margin),
            Complaint.longitude.between(longitude - margin, longitude + margin),
            Complaint.status != "rejected",
            Complaint.status != "completed",
        ).all()
        for cand in nearby_candidates:
            if (cand.latitude - latitude)**2 + (cand.longitude - longitude)**2 <= margin**2:
                dup = cand
                break

    if dup:
        dup.report_count += 1
        db.commit()
        # Clean up the newly uploaded image as it's a duplicate
        if fpath.exists(): fpath.unlink()
        return {
            "warning": "duplicate",
            "existing_complaint_id": dup.complaint_id,
            "message": "A similar complaint already exists in this exact region. We've added your report to the existing one to increase its priority.",
            "report_count": dup.report_count
        }

    # AI Analysis
    ai = ai_service.analyze_image(str(fpath))

    # Priority calculation (using sensitive info + AI results)
    area     = _area(nearby_sensitive or address or "")
    priority = _priority(ai["severity"], ai["damage_type"], area)
    
    # Generate ID and find best officer
    cid      = f"RD-{_now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    officer  = _best_officer(db)

    c = Complaint(
        complaint_id   = cid,
        user_id        = user.id,
        officer_id     = officer.id if officer else None,
        latitude       = latitude,
        longitude      = longitude,
        address        = address,
        area_type      = area,
        damage_type    = ai["damage_type"],
        severity       = ai["severity"],
        ai_confidence  = ai["ai_confidence"],
        description    = ai["description"],
        image_url      = f"/uploads/{fname}",
        image_hash     = img_hash,
        status         = "assigned" if officer else "pending",
        priority_score = priority,
        allocated_fund = 0.0,
        is_duplicate   = False,
        created_at     = _now(),
    )
    db.add(c)
    if officer:
        db.add(ComplaintOfficer(complaint_id=cid, officer_id=officer.id, assigned_at=_now()))
    user.reward_points = (user.reward_points or 0) + 10
    db.flush()

    db.add(Notification(
        user_id      = user.id,
        complaint_id = cid,
        message      = f"Complaint {cid} registered and assigned to a field officer.",
        type         = "submitted",
        created_at   = _now(),
    ))
    db.commit()

    # Email Notifications (non-blocking)
    try:
        from app.services.notification_service import notify_complaint_submitted, notify_officer_assignment
        base_url = os.getenv('BASE_URL', 'https://road-damage-appsystem.onrender.com')
        full_img_url = f"{base_url}{c.image_url}" if c.image_url else ""
        
        # 1. Notify Citizen
        notify_complaint_submitted(
            to_email=user.email, citizen_name=user.name,
            complaint_id=cid, damage_type=ai["damage_type"],
            severity=ai["severity"], priority_score=priority, area_type=area,
            image_url=full_img_url, location=address, nearby_places=nearby_sensitive
        )
        
        # 2. Notify Officer (if assigned)
        if officer:
            notify_officer_assignment(
                to_email=officer.email, officer_name=officer.name,
                complaint_id=cid, damage_type=ai["damage_type"],
                severity=ai["severity"], priority_score=priority, area_type=area,
                location=address, coords=f"{latitude}, {longitude}",
                image_url=full_img_url, notes=ai["description"],
                nearby_places=nearby_sensitive
            )
    except Exception as e:
        logger.warning(f"[Email] submit/assign: {e}")

    if ai["severity"] == "high":
        try:
            from app.services.notification_service import notify_admin_emergency
            notify_admin_emergency(
                complaint_id=cid, severity=ai["severity"],
                damage_type=ai["damage_type"], address=address or "",
                priority_score=priority, latitude=latitude, longitude=longitude,
                image_url=full_img_url
            )
        except Exception as e:
            logger.warning(f"[Email] admin alert: {e}")

    try:
        await manager.broadcast_new_complaint(c)
    except Exception:
        pass

    return _c(c, db)


# ── My complaints ──────────────────────────────────────────────
@router.get("/my")
def my_complaints(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Complaint).filter(
        Complaint.user_id == user.id
    ).order_by(Complaint.created_at.desc()).all()
    return [_c(r, db) for r in rows]


# ── Priority ranking ───────────────────────────────────────────
@router.get("/priority/ranking")
def priority_ranking(db: Session = Depends(get_db), _: FieldOfficer = Depends(get_current_officer)):
    rows = db.query(Complaint).filter(
        Complaint.status != "completed"
    ).order_by(Complaint.priority_score.desc()).limit(50).all()
    return [_c(r, db) for r in rows]


# ── Budget recommendations ─────────────────────────────────────
@router.get("/budget/recommendations")
def budget_recommendations(db: Session = Depends(get_db), _: FieldOfficer = Depends(get_current_officer)):
    """Returns budget allocation recommendations based on open complaints."""
    open_complaints = db.query(Complaint).filter(
        Complaint.status.in_(["pending", "assigned", "in_progress"])
    ).all()

    cost_map = {
        "pothole": 15000, "crack": 8000,
        "surface_damage": 20000, "multiple": 35000,
    }

    area_budgets = {}
    for c in open_complaints:
        area = c.area_type or "residential"
        cost = cost_map.get(c.damage_type, 10000)
        if c.severity == "high":
            cost = int(cost * 1.5)
        if area not in area_budgets:
            area_budgets[area] = {"area": area, "count": 0, "estimated_cost": 0, "high_priority": 0}
        area_budgets[area]["count"] += 1
        area_budgets[area]["estimated_cost"] += cost
        if c.priority_score and c.priority_score >= 70:
            area_budgets[area]["high_priority"] += 1

    total_est = sum(a["estimated_cost"] for a in area_budgets.values())
    return {
        "total_open": len(open_complaints),
        "total_estimated_budget": total_est,
        "by_area": list(area_budgets.values()),
    }



# ── Notifications ──────────────────────────────────────────────
@router.get("/notifications/my")
def my_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Notification).filter(
        Notification.user_id == user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    return [{"id": n.id, "user_id": n.user_id, "complaint_id": n.complaint_id,
             "message": n.message, "type": n.type, "is_read": n.is_read,
             "created_at": _iso(n.created_at)} for n in rows]


@router.post("/notifications/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "ok"}


# ── Officer: list all ──────────────────────────────────────────
@router.get("/")
def list_complaints(
    status:   Optional[str] = None,
    severity: Optional[str] = None,
    db:       Session        = Depends(get_db),
    officer:  FieldOfficer   = Depends(get_current_officer),
):
    q = db.query(Complaint)
    if not officer.is_admin:
        q = q.filter(Complaint.officer_id == officer.id)
    if status:
        q = q.filter(Complaint.status == status)
    if severity:
        q = q.filter(Complaint.severity == severity)
    rows = q.order_by(Complaint.priority_score.desc(), Complaint.created_at.desc()).all()
    return [_c(r, db) for r in rows]


# ── Single complaint ───────────────────────────────────────────
@router.get("/{complaint_id}")
def get_complaint(
    complaint_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """View a single complaint. Accepts any valid Bearer token (citizen or officer)."""
    from app.services.auth_service import decode_token
    auth = request.headers.get("Authorization", "")
    token_str = auth.replace("Bearer ", "").strip() if auth else ""
    # Allow access with valid token OR if user is already authenticated via session
    if token_str and not decode_token(token_str):
        raise HTTPException(401, "Invalid token")
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(404, "Complaint not found")
    return _c(c, db)


# ── Update status ──────────────────────────────────────────────
@router.patch("/{complaint_id}/status")
async def update_status(
    complaint_id: str,
    data:    StatusUpdate,
    db:      Session      = Depends(get_db),
    officer: FieldOfficer = Depends(get_current_officer),
):
    if data.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Use: {VALID_STATUSES}")
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(404, "Complaint not found")

    old = c.status
    c.status = data.status
    if data.officer_notes is not None:
        c.officer_notes = data.officer_notes
    if data.status == "completed":
        c.resolved_at = _now()
    db.flush()

    if c.user_id and c.status != old:
        msgs = {
            "assigned":    f"Complaint {complaint_id} assigned to a field officer.",
            "in_progress": f"Repair work started on complaint {complaint_id}.",
            "completed":   f"Complaint {complaint_id} has been repaired! Thank you.",
            "rejected":    f"Complaint {complaint_id} has been reviewed and closed.",
        }
        db.add(Notification(
            user_id=c.user_id, complaint_id=complaint_id,
            message=msgs.get(data.status, f"Status updated to {data.status}."),
            type=data.status, created_at=_now(),
        ))
        db.commit()
        try:
            from app.services.notification_service import notify_status_update
            user = db.query(User).filter(User.id == c.user_id).first()
            if user:
                base_url = os.getenv('BASE_URL', 'https://road-damage-appsystem.onrender.com')
                full_img_url = f"{base_url}{c.image_url}" if c.image_url else ""
                notify_status_update(
                    to_email=user.email, citizen_name=user.name,
                    complaint_id=complaint_id, new_status=data.status,
                    officer_notes=data.officer_notes or "", officer_name=officer.name,
                    image_url=full_img_url
                )
        except Exception as e:
            logger.warning(f"[Email] status update: {e}")
    else:
        db.commit()

    try:
        await manager.broadcast_status_update(c)
    except Exception:
        pass

    return _c(c, db)


# ── Allocate fund ──────────────────────────────────────────────
@router.patch("/{complaint_id}/fund")
def fund(
    complaint_id: str,
    data:    FundUpdate,
    db:      Session      = Depends(get_db),
    officer: FieldOfficer = Depends(get_current_officer),
):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(404, "Complaint not found")
    c.allocated_fund    = data.amount
    c.fund_note         = data.note
    c.fund_allocated_at = _now()
    db.flush()
    if c.user_id:
        db.add(Notification(
            user_id=c.user_id, complaint_id=complaint_id,
            message=f"Rs. {data.amount:,.0f} allocated for complaint {complaint_id}.",
            type="funded", created_at=_now(),
        ))
        db.commit()
        try:
            from app.services.notification_service import notify_fund_allocated
            user = db.query(User).filter(User.id == c.user_id).first()
            if user:
                notify_fund_allocated(user.email, user.name, complaint_id, data.amount, data.note or "")
        except Exception as e:
            logger.warning(f"[Email] fund: {e}")
    else:
        db.commit()
    return _c(c, db)