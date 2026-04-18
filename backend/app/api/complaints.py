# ruff: noqa: E402, E712, B904, E722
"""
RoadWatch — Complaints API
Uses plain strings for status/severity/damage_type — no SQLAlchemy Enum issues.
All datetimes returned with Z suffix for correct browser parsing.
"""

import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.dependencies import get_current_officer, get_current_user
from app.main import limiter
from app.models.models import Complaint, ComplaintOfficer, FieldOfficer, Notification, User
from app.schemas.complaint import ComplaintStatusOut
from app.schemas.schemas import FundUpdate, StatusUpdate
from app.services import ai_service, audit_service, priority_service, sla_service, storage_service, weather_service
from app.services.cache_service import cache
from app.utils import cache_keys, metrics
from app.ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/complaints", tags=["complaints"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

VALID_STATUSES = {"pending", "assigned", "in_progress", "completed", "rejected"}
VALID_SEVERITIES = {"high", "medium", "low"}
VALID_DAMAGES = {"pothole", "crack", "surface_damage", "multiple"}


def _now():
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    """Always return ISO with Z so ALL browsers parse correctly."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _area(addr: str) -> str:
    a = (addr or "").lower()
    if any(w in a for w in ["hospital", "clinic", "medical", "health", "dispensary"]):
        return "hospital"
    if any(w in a for w in ["school", "college", "university", "academy", "educational"]):
        return "school"
    if any(w in a for w in ["highway", "nh-", "sh-", "expressway", "bypass"]):
        return "highway"
    if any(w in a for w in ["mall", "multiplex", "cinema", "theatre", "stadium", "bus_stand", "junction"]):
        return "crowd_place"
    if any(w in a for w in ["market", "shopping", "commercial", "plaza"]):
        return "market"
    return "residential"


def _priority(sev: str, dmg: str, area: str, nearby_sensitive: str = "") -> float:
    s = {"high": 35, "medium": 20, "low": 10}.get(sev, 10)
    d = {"pothole": 5, "multiple": 8, "crack": 3, "surface_damage": 2}.get(dmg, 0)
    a = {"hospital": 35, "school": 30, "highway": 28, "crowd_place": 25, "market": 22, "residential": 12}.get(area, 12)
    t = {"hospital": 22, "school": 20, "market": 20, "highway": 18, "crowd_place": 18, "residential": 10}.get(area, 10)
    r = {"pothole": 15, "multiple": 14, "crack": 8, "surface_damage": 6}.get(dmg, 6)
    # Nearby sensitive location bonus from POI scan
    nb = 0
    if nearby_sensitive:
        ns = nearby_sensitive.lower()
        if any(w in ns for w in ["hospital", "clinic", "pharmacy"]):
            nb += 15
        if any(w in ns for w in ["school", "college", "university"]):
            nb += 10
        if any(w in ns for w in ["fire_station", "police"]):
            nb += 12
        if any(w in ns for w in ["mall", "stadium", "airport", "railway", "bus_stand"]):
            nb += 10
        if any(w in ns for w in ["marketplace", "place_of_worship", "cinema"]):
            nb += 6
    return min(float(s + d + a + t + r + nb), 100.0)


def _best_officer(db: Session, address: str = "") -> FieldOfficer | None:
    """
    Advanced Load Balancing & Zone-Aware Assignment:
    1. Filter: Active, non-admin officers.
    2. Zone Match: If officer.zone (e.g. 'Zone A') is in address, prioritize them.
    3. Load Balance: Pick the officer with the fewest 'pending' or 'assigned' cases.
    """
    officers = (
        db.query(FieldOfficer)
        .filter(
            FieldOfficer.is_active == True,
            FieldOfficer.is_admin == False,
        )
        .all()
    )
    if not officers:
        return None

    addr_lower = (address or "").lower()

    # Try to find officers in the matching zone first
    zone_matches = []
    if addr_lower:
        for o in officers:
            if o.zone and o.zone.lower() in addr_lower:
                zone_matches.append(o)

    # Target pool: Use zone matches if any, else use all officers
    target_pool = zone_matches if zone_matches else officers

    # Pick the one with the lowest current workload in the target pool
    return min(
        target_pool,
        key=lambda o: (
            db.query(Complaint)
            .filter(
                Complaint.officer_id == o.id,
                Complaint.status.in_(["pending", "assigned"]),
            )
            .count()
        ),
    )


def _c(c: Complaint, db: Session) -> dict:
    oname, uname = None, None
    if c.officer_id:
        o = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first()
        oname = o.name if o else None
    u_email, u_phone = None, None
    if c.user_id:
        u = db.query(User).filter(User.id == c.user_id).first()
        uname = u.name if u else None
        u_email = u.email if u else None
        u_phone = u.phone if u else None
    return {
        "id": c.id,
        "complaint_id": c.complaint_id,
        "user_id": c.user_id,
        "officer_id": c.officer_id,
        "officer_name": oname,
        "citizen_name": uname,
        "citizen_email": u_email,
        "citizen_phone": u_phone,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "address": c.address,
        "area_type": c.area_type,
        "damage_type": c.damage_type,
        "severity": c.severity,
        "ai_confidence": c.ai_confidence,
        "description": c.description,
        "image_url": c.image_url,
        "after_image_url": c.after_image_url,
        "status": c.status,
        "officer_notes": c.officer_notes,
        "priority_score": c.priority_score,
        "allocated_fund": c.allocated_fund,
        "fund_note": c.fund_note,
        "is_duplicate": c.is_duplicate,
        "duplicate_of": c.duplicate_of,
        "report_count": getattr(c, "report_count", 1),
        "created_at": _iso(c.created_at),
        "resolved_at": _iso(c.resolved_at),
    }


async def process_inference_background(complaint_id: str, fpath_str: str, img_bytes: bytes, filename: str, content_type: str, address: str | None, nearby_sensitive: str | None, user_id: int):
    # This runs in a worker thread. We need our own DB session.
    db = SessionLocal()
    try:
        c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if not c:
            return

        # 1. Road Check (Still uses AI, moved to background so it doesn't block)
        is_road, conf = ai_service.is_road_image(fpath_str)
        if not is_road:
            c.status = "failed"
            c.officer_notes = f"AI Rejection: Not a valid road or damage image. (Confidence: {conf})"
            db.commit()
            return

        # 2. Heavy AI Inference
        import time

        from app.utils import metrics

        inf_start = time.perf_counter()

        ai = ai_service.analyze_image(fpath_str)

        inf_duration = time.perf_counter() - inf_start

        image_url = storage_service.upload_file(img_bytes, filename, content_type)

        if ai["ai_confidence"] < 0.10:
            metrics.AI_INFERENCE_TOTAL.labels(result="undetected").inc()
            c.detected_damage_type = None
            c.confidence_score = None
            c.analyzed_at = _now()

            # Legacy defaults for undetected
            c.damage_type = "unknown"
            c.severity = "low"
            c.ai_confidence = 0.0
            c.description = "No clear road damage surpassed the confidence threshold."
            c.priority_score = 0.0
            c.image_url = image_url
            c.area_type = _area(nearby_sensitive or address or "")
            c.status = "undetected"

            db.commit()
        else:
            area = _area(nearby_sensitive or address or "")
            priority = _priority(ai["severity"], ai["damage_type"], area, nearby_sensitive or "")
            officer = _best_officer(db, address or "")

            # New Background task fields
            c.detected_damage_type = ai["damage_type"]
            c.confidence_score = ai["ai_confidence"]
            c.analyzed_at = _now()

            # Legacy mappings
            c.damage_type = ai["damage_type"]
            c.severity = ai["severity"]
            c.ai_confidence = ai["ai_confidence"]
            c.description = ai["description"]
            c.priority_score = priority
            c.image_url = image_url
            c.area_type = area

            # SLA & Routing
            c.department_id = sla_service.get_department_for_damage(db, ai["damage_type"], area)

            # --- Advanced Priority Scoring ---
            weather_risk = await weather_service.fetch_weather_risk(c.latitude, c.longitude)
            # Fetch nearby sensitive from area metadata or logic
            nearby = area if "hospital" in area.lower() or "school" in area.lower() else ""

            p_res = priority_service.calculate_priority_score(damage_type=ai["damage_type"], severity=ai["severity"], confidence=ai["ai_confidence"], area_type=area, nearby_sensitive=nearby, report_count=c.report_count or 1, latitude=c.latitude, longitude=c.longitude, weather_risk=weather_risk, db=db)

            c.priority_score = p_res["score"]
            c.urgency_label = p_res["urgency_label"]
            c.priority_breakdown = p_res["factors"]

            # Use recommended SLA if it matches or overrides previous simple logic
            c.sla_deadline = _now() + timedelta(hours=p_res["recommended_sla_hours"])

            if officer:
                c.officer_id = officer.id
                c.status = "analyzed"
                db.add(ComplaintOfficer(complaint_id=c.complaint_id, officer_id=officer.id, assigned_at=_now()))
            else:
                c.status = "analyzed"

            metrics.AI_INFERENCE_DURATION_SECONDS.labels(damage_type=ai["damage_type"]).observe(inf_duration)
            metrics.AI_INFERENCE_TOTAL.labels(result="detected").inc()

            db.commit()

        # Database Notifications
        notify_status = c.status
        db.add(
            Notification(
                user_id=user_id,
                complaint_id=c.complaint_id,
                message=f"Complaint {c.complaint_id} processed. Status: {notify_status}",
                type="submitted",
                created_at=_now(),
            )
        )
        user_record = db.query(User).filter(User.id == user_id).first()
        if user_record:
            user_record.reward_points = (user_record.reward_points or 0) + 10

            # --- FCM Push Notification Support ---
            if user_record.fcm_token:
                try:
                    from app.services.fcm_service import send_status_update

                    await send_status_update(user_record.fcm_token, c.complaint_id, c.status)
                except Exception as ex:
                    logger.warning(f"Push notify failed for {complaint_id}: {ex}")

        db.commit()

        # Emails
        from app.services.notification_service import notify_admin_emergency, notify_complaint_submitted, notify_officer_assignment

        base_url = os.getenv("BASE_URL", "https://road-damage-appsystem.onrender.com")
        full_img_url = f"{base_url}{c.image_url}" if c.image_url else ""

        try:
            if user_record:
                notify_complaint_submitted(to_email=user_record.email, citizen_name=user_record.name, complaint_id=complaint_id, damage_type=c.damage_type, severity=c.severity, priority_score=c.priority_score, area_type=c.area_type, image_url=full_img_url, location=address, nearby_places=nearby_sensitive)
            if c.officer_id and c.status == "analyzed":
                officer = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first()
                if officer:
                    notify_officer_assignment(
                        to_email=officer.email,
                        officer_name=officer.name,
                        complaint_id=complaint_id,
                        damage_type=c.damage_type,
                        severity=c.severity,
                        priority_score=c.priority_score,
                        area_type=c.area_type,
                        location=address,
                        coords=f"{c.latitude}, {c.longitude}",
                        image_url=full_img_url,
                        notes=c.description,
                        nearby_places=nearby_sensitive,
                    )
            if c.severity == "high":
                notify_admin_emergency(complaint_id=complaint_id, severity=c.severity, damage_type=c.damage_type, address=address or "", priority_score=c.priority_score, latitude=c.latitude, longitude=c.longitude, image_url=full_img_url)
        except Exception as e:
            logger.warning(f"[Email Background] failed inside task: {e}")

        # WS & Map Cache Invalidation
        try:
            # Broadcast new complaint to any listeners
            await manager.broadcast_new_complaint(c)

            # Broadcast status update for specifics
            from app.websockets.complaint_ws import complaint_ws_manager

            await complaint_ws_manager.broadcast_status(complaint_id=c.complaint_id, status=c.status, extra_data={"damage_type": c.damage_type, "confidence": c.confidence_score or c.ai_confidence})

            # Invalidate map cache
            from app.services.cache_service import cache as cache_service

            await cache_service.delete_pattern("map:*")
        except Exception as e:
            logger.warning(f"Background broadcast error: {e}")

        db.commit()

    except Exception as e:
        import sentry_sdk

        logger.error(f"Inference failed for {complaint_id}: {e}", exc_info=True)
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("complaint_id", complaint_id)
            scope.set_tag("task", "yolo_inference")
            scope.set_context(
                "inference_context",
                {
                    "complaint_id": complaint_id,
                    "error_type": type(e).__name__,
                },
            )
            sentry_sdk.capture_exception(e)

        c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if c:
            c.status = "failed"
            c.officer_notes = "System Error: AI inference failed to complete."
            metrics.AI_INFERENCE_TOTAL.labels(result="failed").inc()
            db.commit()
    finally:
        fpath = Path(fpath_str)
        if fpath.exists():
            fpath.unlink()
        db.close()


# ── Submit ─────────────────────────────────────────────────────
@router.post("/submit", status_code=202)
@limiter.limit(os.getenv("RATE_LIMIT_SUBMIT", "10/minute"))
async def submit(
    request: Request,
    background_tasks: BackgroundTasks,
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: str | None = Form(None),
    nearby_sensitive: str | None = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start_time = time.perf_counter()
    if not image or not image.filename:
        raise HTTPException(400, "Missing image file")

    from app.utils.file_validators import validate_image

    img_bytes, error_resp = await validate_image(image)
    if error_resp:
        return error_resp

    img_hash = ai_service.image_hash(img_bytes)

    # Use Geo Service for proximity duplicate detection
    from app.services.geo_service import find_duplicate_complaint

    # We pass damage_type=None here since inference hasn't run yet
    is_duplicate = find_duplicate_complaint(latitude, longitude, None, db, hours=24)
    if is_duplicate:
        metrics.COMPLAINTS_DUPLICATE_TOTAL.labels(detection_method="geo").inc()
        return JSONResponse(status_code=409, content={"detail": "Similar damage already reported nearby", "code": "DUPLICATE"})

    # Invalidate Cache
    background_tasks.add_task(cache.delete_pattern, cache_keys.NEARBY_PATTERN)
    background_tasks.add_task(cache.delete_pattern, cache_keys.COMPLAINTS_LIST_PATTERN)

    # Save initial pending state
    cid = f"RD-{_now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    c = Complaint(
        complaint_id=cid,
        user_id=user.id,
        latitude=latitude,
        longitude=longitude,
        address=address,
        status="pending",
        image_hash=img_hash,
        is_duplicate=False,
        nearby_places=nearby_sensitive,
        created_at=_now(),
    )
    db.add(c)
    db.commit()

    # AUDIT: Complaint Created
    audit_service.log_event(db, "complaint", cid, "created", actor_id=user.id, actor_role="citizen", new_value={"status": "pending", "lat": latitude, "lng": longitude}, request=None)

    # Track submission duration & total
    duration = time.perf_counter() - start_time
    metrics.COMPLAINT_SUBMISSION_DURATION_SECONDS.observe(duration)
    metrics.COMPLAINTS_SUBMITTED_TOTAL.labels(area_type=_area(nearby_sensitive or address or ""), status="pending").inc()

    # Save to temp file for the background worker
    ext = Path(image.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(img_bytes)
        fpath = Path(tmp.name)

    content_type = image.content_type or "image/jpeg"

    # Fire and forget inference
    background_tasks.add_task(process_inference_background, cid, str(fpath), img_bytes, image.filename, content_type, address, nearby_sensitive, user.id)

    return JSONResponse(status_code=202, content={"complaint_id": cid, "status": "pending", "message": "Complaint saved. AI Inference running in background."})


# ── Status Poller ──────────────────────────────────────────────
@router.get("/{id}/status", response_model=ComplaintStatusOut)
def get_complaint_status(
    id: str,
    db: Session = Depends(get_db),
):
    c = db.query(Complaint).filter((Complaint.complaint_id == id) | (Complaint.id == id if id.isdigit() else False)).first()
    if not c:
        raise HTTPException(404, "Complaint not found")

    return {"id": c.id, "status": c.status, "damage_type": c.detected_damage_type or c.damage_type, "confidence": c.confidence_score or c.ai_confidence}


# ── Nearby Complaints ──────────────────────────────────────────
@router.get("/nearby")
async def get_nearby_complaints(lat: float, lng: float, radius: int = 500, db: Session = Depends(get_db)):
    """Returns complaints within radius meters. Max 5000m. Cached 60s."""
    if radius > 5000:
        radius = 5000

    ckey = cache_keys.get_nearby_key(lat, lng, radius)
    cached = await cache.get(ckey)
    if cached:
        return cached

    from app.services.geo_service import find_nearby_complaints

    comps = find_nearby_complaints(lat, lng, db, radius_meters=radius)
    data = [_c(c, db) for c in comps]
    await cache.set(ckey, data, ttl_seconds=60)
    return data


# ── My complaints ──────────────────────────────────────────────
@router.get("/my")
def my_complaints(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Complaint).filter(Complaint.user_id == user.id).order_by(Complaint.created_at.desc()).all()
    return [_c(r, db) for r in rows]


# ── Priority ranking ───────────────────────────────────────────
@router.get("/priority/ranking")
def priority_ranking(db: Session = Depends(get_db), _: FieldOfficer = Depends(get_current_officer)):
    rows = db.query(Complaint).filter(Complaint.status != "completed").order_by(Complaint.priority_score.desc()).limit(50).all()
    return [_c(r, db) for r in rows]


# ── Budget recommendations ─────────────────────────────────────
@router.get("/budget/recommendations")
def budget_recommendations(db: Session = Depends(get_db), _: FieldOfficer = Depends(get_current_officer)):
    """Returns budget allocation recommendations based on open complaints."""
    open_complaints = db.query(Complaint).filter(Complaint.status.in_(["pending", "assigned", "in_progress"])).all()

    cost_map = {
        "pothole": 15000,
        "crack": 8000,
        "surface_damage": 20000,
        "multiple": 35000,
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
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return [{"id": n.id, "user_id": n.user_id, "complaint_id": n.complaint_id, "message": n.message, "type": n.type, "is_read": n.is_read, "created_at": _iso(n.created_at)} for n in rows]


@router.post("/notifications/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"status": "ok"}


# ── Officer: list all ──────────────────────────────────────────
@router.get("/")
async def list_complaints(
    status: str | None = None,
    severity: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
    officer: FieldOfficer = Depends(get_current_officer),
):
    # Distinct caching per officer if restricted, or global for admins
    ctx = f"officer:{officer.id}" if not officer.is_admin else "admin"
    ckey = f"complaints:list:{ctx}:{status or 'all'}:{severity or 'all'}:{page}"

    cached = await cache.get(ckey)
    if cached:
        return cached

    q = db.query(Complaint)
    if not officer.is_admin:
        q = q.filter((Complaint.officer_id == officer.id) | (Complaint.status == "pending"))
    if status:
        q = q.filter(Complaint.status == status)
    if severity:
        q = q.filter(Complaint.severity == severity)

    # Simple pagination: 50 per page
    rows = q.order_by(Complaint.priority_score.desc(), Complaint.created_at.desc()).offset((page - 1) * 50).limit(50).all()
    data = [_c(r, db) for r in rows]

    await cache.set(ckey, data, ttl_seconds=30)
    return data


# ── Officer PDF Report Download ────────────────────────────────
# NOTE: Must be registered BEFORE /{complaint_id} to avoid route collision
@router.get("/report/download")
def officer_download_report(
    db: Session = Depends(get_db),
    officer: FieldOfficer = Depends(get_current_officer),
):
    """Generate a PDF report for all complaints assigned to this officer."""
    import io

    from fastapi.responses import StreamingResponse

    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(500, "PDF library not available")

    complaints = db.query(Complaint).filter(Complaint.officer_id == officer.id).order_by(Complaint.created_at.desc()).all()

    class OfficerPDF(FPDF):
        def header(self):
            self.set_fill_color(15, 23, 42)
            self.rect(0, 0, 210, 38, "F")
            self.set_font("helvetica", "B", 20)
            self.set_text_color(0, 229, 255)
            self.set_y(8)
            self.cell(0, 10, "RoadWatch Officer Report", align="C", ln=True)
            self.set_font("helvetica", "", 10)
            self.set_text_color(148, 163, 184)
            self.cell(0, 6, f"Officer: {officer.name} | Zone: {officer.zone or 'N/A'} | Generated: {_now().strftime('%d %b %Y, %I:%M %p')} UTC", align="C", ln=True)
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 10, f"Page {self.page_no()} / {{nb}} - RoadWatch Officer Report - Confidential", align="C")

    pdf = OfficerPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    if not complaints:
        pdf.set_font("helvetica", "B", 14)
        pdf.set_text_color(100)
        pdf.cell(0, 40, "No complaints assigned to you.", align="C")
    else:
        total = len(complaints)
        done = sum(1 for c in complaints if c.status == "completed")
        active = sum(1 for c in complaints if c.status in ("assigned", "in_progress"))
        high = sum(1 for c in complaints if c.severity == "high")

        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 8, f"Summary: {total} Total | {done} Completed | {active} Active | {high} High Severity", ln=True)
        pdf.ln(4)

        for c in complaints:
            if pdf.get_y() > 220:
                pdf.add_page()

            pdf.set_fill_color(30, 41, 59)
            pdf.rect(10, pdf.get_y(), 190, 10, "F")
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(255, 255, 255)
            cid = c.complaint_id or f"RD-{c.id:06d}"
            pdf.set_x(15)
            pdf.cell(100, 10, f"COMPLAINT: {cid}", ln=False, align="L")

            pdf.set_font("helvetica", "B", 9)
            st = (c.status or "PENDING").upper().replace("_", " ")
            if c.status == "completed":
                pdf.set_text_color(52, 211, 153)
            elif c.status == "rejected":
                pdf.set_text_color(248, 113, 113)
            else:
                pdf.set_text_color(251, 191, 36)
            pdf.cell(80, 10, f"STATUS: {st}   ", ln=True, align="R")
            pdf.ln(3)

            pdf.set_x(15)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(32, 6, "Damage:")
            pdf.set_font("helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 6, (c.damage_type or "Unknown").replace("_", " ").title(), ln=True)

            pdf.set_x(15)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(32, 6, "Severity:")
            pdf.set_font("helvetica", "B", 9)
            sev = (c.severity or "medium").upper()
            pdf.set_text_color(185, 28, 28) if sev == "HIGH" else pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 6, sev, ln=True)

            ts = c.created_at.strftime("%d %b %Y, %I:%M %p") if c.created_at else "N/A"
            pdf.set_x(15)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(32, 6, "Reported:")
            pdf.set_font("helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 6, ts, ln=True)

            pdf.set_x(15)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(32, 6, "Coords:")
            pdf.set_font("helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 6, f"{c.latitude:.5f}, {c.longitude:.5f}", ln=True)

            pdf.set_x(15)
            pdf.set_font("helvetica", "B", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(32, 6, "Location:")
            pdf.set_font("helvetica", "", 8.5)
            pdf.set_text_color(30, 41, 59)
            addr = (c.address or "GPS Location").encode("ascii", "ignore").decode("ascii")
            pdf.multi_cell(0, 5, addr[:120])

            if c.allocated_fund and c.allocated_fund > 0:
                pdf.set_x(15)
                pdf.set_font("helvetica", "B", 9)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(32, 6, "Budget:")
                pdf.set_font("helvetica", "B", 9)
                pdf.set_text_color(16, 185, 129)
                pdf.cell(0, 6, f"Rs. {c.allocated_fund:,.0f}", ln=True)

            pdf.ln(4)
            pdf.set_draw_color(226, 232, 240)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(6)

    pdf_bytes = pdf.output()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=RoadWatch_Officer_{officer.name}_{_now().strftime('%Y%m%d')}.pdf"},
    )


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
    data: StatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
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
        # Automate: Reward citizen with bonus points upon successful repair
        if c.user_id:
            user = db.query(User).filter(User.id == c.user_id).first()
            if user:
                user.reward_points = (user.reward_points or 0) + 5

    db.flush()

    if c.user_id and c.status != old:
        msgs = {
            "assigned": f"Complaint {complaint_id} assigned to a field officer.",
            "in_progress": f"Repair work started on complaint {complaint_id}.",
            "completed": f"Complaint {complaint_id} has been repaired! Thank you.",
            "rejected": f"Complaint {complaint_id} has been reviewed and closed.",
        }
        db.add(
            Notification(
                user_id=c.user_id,
                complaint_id=complaint_id,
                message=msgs.get(data.status, f"Status updated to {data.status}."),
                type=data.status,
                created_at=_now(),
            )
        )
        db.commit()
        try:
            from app.services.notification_service import notify_status_update

            user = db.query(User).filter(User.id == c.user_id).first()
            if user:
                base_url = os.getenv("BASE_URL", "https://road-damage-appsystem.onrender.com")
                full_img_url = f"{base_url}{c.image_url}" if c.image_url else ""
                background_tasks.add_task(notify_status_update, to_email=user.email, citizen_name=user.name, complaint_id=complaint_id, new_status=data.status, officer_notes=data.officer_notes or "", officer_name=officer.name, image_url=full_img_url)
        except Exception as e:
            logger.warning(f"[Email Background] status update trigger error: {e}")

        # AUDIT: Status Change
        audit_service.log_event(db, "complaint", complaint_id, "status_changed", actor_id=officer.id, actor_role="officer", old_value={"status": old}, new_value={"status": data.status}, request=None)

        # --- FCM Push Update (Task Specification) ---
        try:
            from app.services.fcm_service import send_status_update

            token_user = db.query(User).filter(User.id == c.user_id).first()
            if token_user and token_user.fcm_token:
                background_tasks.add_task(send_status_update, token_user.fcm_token, complaint_id, data.status)
        except Exception as ex:
            logger.warning(f"Failed to queue FCM push: {ex}")

        # Invalidate Heatmap/Map cache
        await cache.delete_pattern("map:*")

        db.commit()

    try:
        await manager.broadcast_status_update(c)
    except Exception:
        pass

    # Invalidate cache on status change
    background_tasks.add_task(cache.delete_pattern, cache_keys.COMPLAINTS_LIST_PATTERN)
    background_tasks.add_task(cache.delete_pattern, cache_keys.NEARBY_PATTERN)

    return _c(c, db)


# ── Allocate fund ──────────────────────────────────────────────
@router.patch("/{complaint_id}/fund")
def fund(
    complaint_id: str,
    data: FundUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    officer: FieldOfficer = Depends(get_current_officer),
):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(404, "Complaint not found")
    c.allocated_fund = data.amount
    c.fund_note = data.note
    c.fund_allocated_at = _now()

    # Automate: Transition to 'in_progress' from 'assigned' or 'pending' if budget is allocated
    if c.status in ["pending", "assigned"] and data.amount > 0:
        c.status = "in_progress"

    db.flush()
    if c.user_id:
        db.add(
            Notification(
                user_id=c.user_id,
                complaint_id=complaint_id,
                message=f"Rs. {data.amount:,.0f} allocated for complaint {complaint_id}.",
                type="funded",
                created_at=_now(),
            )
        )
        db.commit()
        try:
            from app.services.notification_service import notify_fund_allocated

            user = db.query(User).filter(User.id == c.user_id).first()
            if user:
                notify_fund_allocated(user.email, user.name, complaint_id, data.amount, data.note or "")
        except Exception as e:
            logger.warning(f"[Email] fund: {e}")
        # --- FCM Fund Push ---
        try:
            if user and user.fcm_token:
                from app.services.fcm_service import send_fund_allocated_notification

                background_tasks.add_task(send_fund_allocated_notification, user.fcm_token, complaint_id, data.amount)
        except Exception as e:
            logger.warning(f"FCM fund push failed: {e}")

        db.commit()
    return _c(c, db)


# ── SLA & Dashboard ──────────────────────────────────────────────


@router.get("/{complaint_id}/sla")
def get_complaint_sla(complaint_id: str, db: Session = Depends(get_db)):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c or not c.sla_deadline:
        raise HTTPException(404, "SLA data not available")

    now = datetime.now(timezone.utc)
    deadline = c.sla_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    delta = deadline - now
    hours_remaining = delta.total_seconds() / 3600

    status = "on_track"
    if hours_remaining < 0:
        status = "overdue"
    elif hours_remaining < 12:
        status = "at_risk"

    return {"deadline": deadline.isoformat().replace("+00:00", "Z"), "hours_remaining": round(hours_remaining, 2), "escalation_level": c.escalation_level, "status": status}


@router.post("/{complaint_id}/resolve")
async def resolve_complaint(complaint_id: str, background_tasks: BackgroundTasks, proof: UploadFile = File(...), db: Session = Depends(get_db), officer: FieldOfficer = Depends(get_current_officer)):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(404, "Not found")

    # Save proof photo
    content = await proof.read()
    proof_url = storage_service.upload_file(content, proof.filename, proof.content_type)

    c.status = "completed"
    c.resolved_proof_url = proof_url
    c.resolved_at = datetime.now(timezone.utc)
    db.commit()

    # AUDIT: Resolved
    audit_service.log_event(
        db,
        "complaint",
        complaint_id,
        "resolved",
        actor_id=officer.id,
        actor_role="officer",
        new_value={"status": "completed", "proof": proof_url},
        request=None,  # Request object might not be cleanly available here unless passed
    )

    # Notify user via Push
    try:
        user = db.query(User).filter(User.id == c.user_id).first()
        if user and user.fcm_token:
            from app.services.fcm_service import send_status_update

            background_tasks.add_task(send_status_update, user.fcm_token, complaint_id, "completed")
    except Exception as e:
        logger.warning(f"FCM resolve push failed: {e}")

    return {"status": "ok", "proof_url": proof_url}
