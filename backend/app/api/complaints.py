from datetime import datetime
from pathlib import Path
import logging
import os
import shutil
from types import SimpleNamespace
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status, WebSocket, WebSocketDisconnect, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Complaint, User, FieldOfficer, SeverityLevel, ComplaintStatus, DamageType
from app.services.auth_service import AuthPrincipal, get_current_principal, get_current_user, get_current_officer
from app.services.ai_service import analyze_image, is_road_image

router = APIRouter()
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = str(Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))).resolve())
os.makedirs(UPLOAD_DIR, exist_ok=True)

try:
    from ws_manager import manager as ws_manager
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False

def generate_complaint_id():
    return f"RD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"


def _remove_uploaded_file(filepath: Optional[str]):
    if not filepath:
        return
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError as exc:
        logger.warning("Could not remove upload %s: %s", filepath, exc)


def _is_admin_officer(officer: FieldOfficer) -> bool:
    return bool(getattr(officer, "is_admin", False))


def _ensure_complaint_access(complaint: Complaint, principal: AuthPrincipal):
    if principal.role == "citizen":
        if not principal.citizen or complaint.user_id != principal.citizen.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this complaint")
        return

    if principal.is_admin:
        return

    if not principal.officer or complaint.officer_id != principal.officer.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this complaint")


def _ensure_officer_controls_complaint(complaint: Complaint, officer: FieldOfficer):
    if complaint.officer_id == officer.id or _is_admin_officer(officer):
        return
    raise HTTPException(status_code=403, detail="Not authorized to manage this complaint")


def _notification_snapshot(complaint: Complaint, citizen: User, officer: Optional[FieldOfficer]):
    return {
        "complaint": {
            "complaint_id": complaint.complaint_id,
            "severity": complaint.severity.value if hasattr(complaint.severity, "value") else str(complaint.severity),
            "damage_type": complaint.damage_type.value if hasattr(complaint.damage_type, "value") else str(complaint.damage_type),
            "priority_score": getattr(complaint, "priority_score", 0) or 0,
            "area_type": getattr(complaint, "area_type", "unknown") or "unknown",
            "address": complaint.address,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
        },
        "citizen": {
            "name": citizen.name,
            "email": citizen.email,
        },
        "officer": {
            "name": officer.name,
            "email": officer.email,
        } if officer else None,
    }


def _as_notification_object(data: dict):
    return SimpleNamespace(**data)


AREA_KEYWORDS = {
    "hospital": ("hospital", "clinic", "medical", "health", "trauma"),
    "school": ("school", "college", "university", "academy", "campus"),
    "highway": ("highway", "expressway", "bypass", "nh-", "sh-"),
    "market": ("market", "mall", "shopping", "commercial", "bazaar"),
}

AREA_CRITICALITY_SCORES = {
    "hospital": 30,
    "school": 25,
    "highway": 25,
    "market": 20,
    "residential": 10,
    "unknown": 10,
}

AREA_TRAFFIC_SCORES = {
    "hospital": 20,
    "school": 18,
    "market": 18,
    "highway": 16,
    "residential": 8,
    "unknown": 8,
}

SEVERITY_BASE_SCORES = {
    "high": 35,
    "medium": 20,
    "low": 10,
}

DAMAGE_TYPE_BONUS = {
    "pothole": 5,
    "multiple": 8,
    "crack": 3,
    "surface_damage": 2,
}

DAMAGE_RISK_SCORES = {
    "pothole": 15,
    "multiple": 14,
    "crack": 8,
    "surface_damage": 6,
}

AREA_TYPE_ALIASES = {
    "clinic": "hospital",
    "medical": "hospital",
    "college": "school",
    "university": "school",
    "commercial": "market",
    "general": "residential",
}


def _enum_value(value) -> str:
    if hasattr(value, "value"):
        return str(value.value).lower()
    return str(value).split(".")[-1].lower()


def _infer_area_type(address: Optional[str]) -> str:
    if not address:
        return "residential"

    lowered = address.lower()
    for area_type, keywords in AREA_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return area_type
    return "residential"


def _normalize_area_type(area_type: Optional[str], address: Optional[str] = None) -> str:
    candidate = str(area_type or "").strip().lower().replace(" ", "_")
    candidate = AREA_TYPE_ALIASES.get(candidate, candidate)
    if candidate in AREA_CRITICALITY_SCORES:
        return candidate
    return _infer_area_type(address)


def _clamp_float(value, minimum: float = 0.0, maximum: float = 100.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = minimum
    return max(minimum, min(maximum, numeric))


def _clamp_int(value, minimum: int = 0, maximum: int = 25) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = minimum
    return max(minimum, min(maximum, numeric))


def _calculate_priority_score(
    severity,
    damage_type,
    area_type: Optional[str],
    report_count: int = 1,
    impact_score: Optional[float] = None,
    sensitive_location_count: int = 0,
) -> float:
    severity_key = _enum_value(severity)
    damage_key = _enum_value(damage_type)
    area_key = _normalize_area_type(area_type)
    duplicate_bonus = min(max(report_count - 1, 0) * 5, 15)
    impact_bonus = round(_clamp_float(impact_score) / 10)
    nearby_bonus = min(_clamp_int(sensitive_location_count), 5)

    score = (
        SEVERITY_BASE_SCORES.get(severity_key, 10)
        + DAMAGE_TYPE_BONUS.get(damage_key, 0)
        + AREA_CRITICALITY_SCORES.get(area_key, 10)
        + AREA_TRAFFIC_SCORES.get(area_key, 8)
        + DAMAGE_RISK_SCORES.get(damage_key, 6)
        + duplicate_bonus
        + impact_bonus
        + nearby_bonus
    )
    return float(min(score, 100))


def _count_nearby_open_reports(db: Session, latitude: float, longitude: float) -> int:
    return db.query(Complaint).filter(
        Complaint.latitude.between(latitude - 0.0005, latitude + 0.0005),
        Complaint.longitude.between(longitude - 0.0005, longitude + 0.0005),
        Complaint.status != ComplaintStatus.COMPLETED,
    ).count()

@router.websocket("/ws/officer")
async def websocket_officer(websocket: WebSocket):
    if not WS_ENABLED:
        await websocket.close(); return
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@router.get("/priority/preview")
def preview_priority(
    latitude: float = Query(...),
    longitude: float = Query(...),
    address: Optional[str] = Query(None),
    area_type: Optional[str] = Query(None),
    impact_score: Optional[float] = Query(None),
    sensitive_location_count: int = Query(0),
    severity: str = Query("medium"),
    damage_type: str = Query("surface_damage"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    del current_user
    resolved_area_type = _normalize_area_type(area_type, address)
    nearby_open_reports = _count_nearby_open_reports(db, latitude, longitude)
    report_count = max(nearby_open_reports, 0) + 1
    estimated_priority_score = _calculate_priority_score(
        severity,
        damage_type,
        resolved_area_type,
        report_count=report_count,
        impact_score=impact_score,
        sensitive_location_count=sensitive_location_count,
    )
    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "area_type": resolved_area_type,
        "impact_score": _clamp_float(impact_score),
        "sensitive_location_count": _clamp_int(sensitive_location_count),
        "estimated_priority_score": estimated_priority_score,
        "nearby_report_count": report_count,
        "duplicate_detected": nearby_open_reports > 0,
        "severity_basis": _enum_value(severity),
        "damage_type_basis": _enum_value(damage_type),
    }

@router.post("/submit")
async def submit_complaint(
    request: Request,
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: Optional[str] = Form(None),
    area_type: Optional[str] = Form(None),
    impact_score: Optional[float] = Form(None),
    sensitive_location_count: int = Form(0),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filepath = None
    try:
        # Save image
        ext = image.filename.split(".")[-1] if image.filename and "." in image.filename else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            shutil.copyfileobj(image.file, f)

        is_road, road_confidence = is_road_image(filepath)
        if not is_road:
            _remove_uploaded_file(filepath)
            filepath = None
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The uploaded image does not appear to show a road surface "
                    f"(confidence: {road_confidence:.0%}). Please upload a clearer road-damage photo."
                ),
            )

        # AI detection
        try:
            detection = analyze_image(filepath)
            damage_type = detection.damage_type
            severity = detection.severity
            confidence = detection.confidence
            description = detection.description
        except Exception as exc:
            logger.warning("Automated analysis failed for %s: %s", filepath, exc)
            damage_type = DamageType.SURFACE_DAMAGE
            severity = SeverityLevel.MEDIUM
            confidence = 0.0
            description = "Road image accepted, but automated analysis is unavailable. Officer review required."

        resolved_area_type = _normalize_area_type(area_type, address)

        # Duplicate check (simple distance check)
        try:
            existing = db.query(Complaint).filter(
                Complaint.latitude.between(latitude - 0.0005, latitude + 0.0005),
                Complaint.longitude.between(longitude - 0.0005, longitude + 0.0005),
                Complaint.status != ComplaintStatus.COMPLETED
            ).first()
            if existing:
                try:
                    existing.report_count = (getattr(existing, "report_count", 1) or 1) + 1
                    existing.area_type = getattr(existing, "area_type", None) or resolved_area_type
                    existing.priority_score = _calculate_priority_score(
                        existing.severity,
                        existing.damage_type,
                        existing.area_type,
                        existing.report_count,
                        impact_score=impact_score,
                        sensitive_location_count=sensitive_location_count,
                    )
                    db.commit()
                    db.refresh(existing)
                except Exception:
                    db.rollback()
                _remove_uploaded_file(filepath)
                filepath = None
                return {
                    "warning": "duplicate",
                    "message": f"Similar complaint already exists nearby: {existing.complaint_id}",
                    "existing_complaint_id": existing.complaint_id,
                    "priority_score": getattr(existing, "priority_score", 0) or 0,
                    "area_type": getattr(existing, "area_type", "residential") or "residential",
                    "report_count": getattr(existing, "report_count", 1) or 1,
                }
        except Exception:
            pass

        # Get officer
        officer = None
        try:
            officer = db.query(FieldOfficer).filter(FieldOfficer.is_active == True).first()
        except Exception:
            officer = db.query(FieldOfficer).first()

        # Create complaint with only base columns (safe)
        priority_score = _calculate_priority_score(
            severity,
            damage_type,
            resolved_area_type,
            report_count=1,
            impact_score=impact_score,
            sensitive_location_count=sensitive_location_count,
        )
        complaint = Complaint(
            complaint_id=generate_complaint_id(),
            user_id=current_user.id,
            officer_id=officer.id if officer else None,
            latitude=latitude,
            longitude=longitude,
            address=address,
            area_type=resolved_area_type,
            damage_type=damage_type,
            severity=severity,
            ai_confidence=confidence,
            description=description,
            image_url=f"/uploads/{filename}",
            status=ComplaintStatus.ASSIGNED if officer else ComplaintStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # Try setting extra columns if they exist
        try:
            complaint.allocated_fund = 0.0
            complaint.priority_score = priority_score
            complaint.report_count = 1
            complaint.is_duplicate = False
        except Exception:
            pass

        db.add(complaint)
        try:
            current_user.points = (current_user.points or 0) + 10
        except Exception:
            pass
        db.commit()
        db.refresh(complaint)

        try:
            from app.services.notification_service import (
                build_submission_notification,
                create_in_app_notification,
            )

            notification_type, title, message = build_submission_notification(
                officer_name=officer.name if officer else "",
                address=complaint.address or "",
            )
            create_in_app_notification(
                db,
                user_id=current_user.id,
                complaint_id=complaint.complaint_id,
                notification_type=notification_type,
                title=title,
                message=message,
            )
        except Exception as e:
            logger.warning("In-app submission notification error: %s", e)

        # ── FULL EMERGENCY NOTIFICATION FLOW ─────────────────
        notification_data = _notification_snapshot(complaint, current_user, officer)

        import traceback as _tb, threading as _threading
        _log = logging.getLogger(__name__)

        def _send_notifications():
            try:
                from app.services.notification_service import (
                    notify_admin_emergency,
                    notify_officer_assigned,
                    notify_citizen_submitted
                )
                complaint_data = notification_data["complaint"]
                citizen_data = notification_data["citizen"]
                officer_data = notification_data["officer"]
                complaint_obj = _as_notification_object(complaint_data)
                officer_obj = _as_notification_object(officer_data) if officer_data else None
                sev_val = complaint_data["severity"]
                priority_val = complaint_data["priority_score"]

                _log.info(
                    "Sending notifications for %s sev=%s to=%s",
                    complaint_data["complaint_id"],
                    sev_val,
                    citizen_data["email"],
                )

                ok1 = notify_citizen_submitted(
                    citizen_email=citizen_data["email"],
                    citizen_name=citizen_data["name"],
                    complaint_id=complaint_data["complaint_id"],
                    severity=sev_val,
                    address=complaint_data["address"] or "",
                    priority=priority_val
                )
                _log.info(f"Citizen email: {'sent' if ok1 else 'FAILED'}")

                if sev_val == "high":
                    ok2 = notify_admin_emergency(complaint_obj, citizen_data["name"])
                    _log.info(f"Admin emergency: {'sent' if ok2 else 'FAILED'}")

                if officer_obj:
                    ok3 = notify_officer_assigned(officer_obj, complaint_obj)
                    _log.info(f"Officer email: {'sent' if ok3 else 'FAILED'}")

            except Exception as e:
                _log.error(f"Notification error: {e}\n{_tb.format_exc()}")

        _threading.Thread(target=_send_notifications, daemon=True).start()

        # WebSocket broadcast
        try:
            if WS_ENABLED:
                await ws_manager.broadcast_new_complaint(complaint)
        except Exception:
            pass

        filepath = None

        return {
            "id": complaint.id,
            "complaint_id": complaint.complaint_id,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "address": complaint.address,
            "damage_type": complaint.damage_type.value if hasattr(complaint.damage_type, 'value') else str(complaint.damage_type),
            "severity": complaint.severity.value if hasattr(complaint.severity, 'value') else str(complaint.severity),
            "ai_confidence": complaint.ai_confidence,
            "description": complaint.description,
            "image_url": complaint.image_url,
            "area_type": getattr(complaint, "area_type", "residential") or "residential",
            "priority_score": getattr(complaint, "priority_score", 0) or 0,
            "report_count": getattr(complaint, "report_count", 1) or 1,
            "impact_score": _clamp_float(impact_score),
            "sensitive_location_count": _clamp_int(sensitive_location_count),
            "status": complaint.status.value if hasattr(complaint.status, 'value') else str(complaint.status),
            "created_at": complaint.created_at.isoformat() if complaint.created_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        _remove_uploaded_file(filepath)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{complaint_id}/after-photo")
async def upload_after_photo(
    complaint_id: str,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_officer_controls_complaint(c, current_officer)
    ext = image.filename.split(".")[-1] if image.filename and "." in image.filename else "jpg"
    filename = f"{uuid.uuid4()}_after.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(image.file, f)
    c.officer_notes = (c.officer_notes or "") + f"\n[AFTER_PHOTO:/uploads/{filename}]"
    db.commit()
    return {"after_image_url": f"/uploads/{filename}"}

@router.get("/my")
def my_complaints(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    complaints = db.query(Complaint).filter(
        Complaint.user_id == current_user.id
    ).order_by(Complaint.created_at.desc()).all()
    return [serialize_complaint(c) for c in complaints]

@router.get("/{complaint_id}")
def get_complaint(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_principal: AuthPrincipal = Depends(get_current_principal)
):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_complaint_access(c, current_principal)
    return serialize_complaint(c)

@router.get("/")
def list_complaints(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    query = db.query(Complaint)
    if not _is_admin_officer(current_officer):
        query = query.filter(Complaint.officer_id == current_officer.id)
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
    return [serialize_complaint(c) for c in complaints]

@router.get("/priority/ranking")
def priority_ranking(
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    query = db.query(Complaint)
    if not _is_admin_officer(current_officer):
        query = query.filter(Complaint.officer_id == current_officer.id)
    complaints = query.all()
    ranked = sorted(
        complaints,
        key=lambda c: (
            getattr(c, "priority_score", 0) or 0,
            1 if c.severity == SeverityLevel.HIGH else 0,
            c.created_at or datetime.min,
        ),
        reverse=True,
    )
    return [serialize_complaint(c) for c in ranked]

@router.get("/budget/recommendations")
def budget_recommendations(
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    query = db.query(Complaint)
    if not _is_admin_officer(current_officer):
        query = query.filter(Complaint.officer_id == current_officer.id)
    complaints = query.all()
    estimated_total = 0.0
    for complaint in complaints:
        if getattr(complaint, "allocated_fund", 0):
            estimated_total += complaint.allocated_fund or 0.0
            continue
        if complaint.severity == SeverityLevel.HIGH:
            estimated_total += 50000
        elif complaint.severity == SeverityLevel.MEDIUM:
            estimated_total += 25000
        else:
            estimated_total += 10000

    return {
        "complaint_count": len(complaints),
        "estimated_total_budget": estimated_total,
        "recommended_buffer": round(estimated_total * 0.1, 2),
    }

@router.patch("/{complaint_id}/status")
async def update_status(
    complaint_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    body = await request.json()
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_officer_controls_complaint(c, current_officer)
    try:
        c.status = ComplaintStatus(body.get("status", c.status.value))
    except Exception:
        pass
    if body.get("officer_notes"):
        c.officer_notes = body["officer_notes"]
    if c.status == ComplaintStatus.COMPLETED:
        c.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(c)
    final_status = c.status.value if hasattr(c.status, "value") else str(c.status)
    
    # Notify citizen of status change
    try:
        from app.services.notification_service import (
            build_status_notification,
            create_in_app_notification,
            notify_citizen_status,
        )
        from app.models.models import User
        citizen = db.query(User).filter(User.id == c.user_id).first()
        officer_name = current_officer.name if hasattr(current_officer,'name') else ""
        if citizen:
            try:
                notification_type, title, message = build_status_notification(
                    final_status,
                    address=c.address or "",
                    officer_name=officer_name,
                )
                create_in_app_notification(
                    db,
                    user_id=citizen.id,
                    complaint_id=c.complaint_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                )
            except Exception as e:
                logging.getLogger(__name__).warning(f"In-app status notification error: {e}")

            notify_citizen_status(
                citizen_email=citizen.email,
                citizen_name=citizen.name,
                complaint_id=c.complaint_id,
                new_status=final_status,
                address=c.address or "",
                officer_name=officer_name
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Status notification error: {e}")
    try:
        if WS_ENABLED:
            await ws_manager.broadcast_status_update(c)
    except Exception:
        pass
    return serialize_complaint(c)

@router.patch("/{complaint_id}/fund")
def allocate_fund(
    complaint_id: str,
    request_data: dict,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_officer_controls_complaint(c, current_officer)
    try:
        c.allocated_fund = request_data.get("amount", 0)
        c.fund_note = request_data.get("note", "")
        c.fund_allocated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return serialize_complaint(c)

def serialize_complaint(c):
    result = {
        "id": c.id,
        "complaint_id": c.complaint_id,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "address": c.address,
        "damage_type": c.damage_type.value if hasattr(c.damage_type, 'value') else str(c.damage_type),
        "severity": c.severity.value if hasattr(c.severity, 'value') else str(c.severity),
        "ai_confidence": c.ai_confidence,
        "description": c.description,
        "image_url": c.image_url,
        "area_type": getattr(c, "area_type", "residential") or "residential",
        "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
        "officer_notes": c.officer_notes,
        "created_at": c.created_at.isoformat() if c.created_at else datetime.utcnow().isoformat(),
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
    }
    # Extra fields - safe get
    for field in ["allocated_fund", "fund_note", "priority_score", "rainfall_mm", "traffic_volume", "road_age_years", "weather_condition", "is_duplicate", "duplicate_of", "report_count"]:
        try:
            result[field] = getattr(c, field, None)
        except Exception:
            result[field] = None
    return result

# ── NOTIFICATIONS ──────────────────────────────────────────
@router.get("/notifications/my")
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.models.models import Notification
        notifs = db.query(Notification).filter(
            Notification.user_id == current_user.id
        ).order_by(Notification.created_at.desc()).limit(30).all()
        return [{
            "id": n.id,
            "type": n.type or "info",
            "title": n.title or "",
            "message": n.message or "",
            "is_read": bool(n.is_read),
            "complaint_id": n.complaint_id,
            "created_at": n.created_at.isoformat() if n.created_at else None
        } for n in notifs]
    except Exception as e:
        return []

@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.models.models import Notification
        db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).update({"is_read": True})
        db.commit()
    except Exception:
        pass
    return {"success": True}

@router.patch("/notifications/{notif_id}/read")
def mark_one_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from app.models.models import Notification
        n = db.query(Notification).filter(
            Notification.id == notif_id,
            Notification.user_id == current_user.id
        ).first()
        if n:
            n.is_read = True
            db.commit()
    except Exception:
        pass
    return {"success": True}
