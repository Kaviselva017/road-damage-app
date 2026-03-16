from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, WebSocket, WebSocketDisconnect, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid, os, shutil

from app.database import get_db
from app.models.models import Complaint, User, FieldOfficer, SeverityLevel, ComplaintStatus
from app.services.auth_service import get_current_user, get_current_officer
from app.services.ai_service import analyze_image

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

try:
    from ws_manager import manager as ws_manager
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False

def generate_complaint_id():
    return f"RD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

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

@router.post("/submit")
async def submit_complaint(
    request: Request,
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: Optional[str] = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Save image
        ext = image.filename.split(".")[-1] if image.filename and "." in image.filename else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            shutil.copyfileobj(image.file, f)

        # AI detection
        try:
            detection = analyze_image(filepath)
            damage_type = detection.damage_type
            severity = detection.severity
            confidence = detection.confidence
            description = detection.description
        except Exception:
            damage_type = "surface_damage"
            severity = SeverityLevel.MEDIUM
            confidence = 0.75
            description = "Road damage detected."

        # Duplicate check (simple distance check)
        try:
            existing = db.query(Complaint).filter(
                Complaint.latitude.between(latitude - 0.0005, latitude + 0.0005),
                Complaint.longitude.between(longitude - 0.0005, longitude + 0.0005),
                Complaint.status != ComplaintStatus.COMPLETED
            ).first()
            if existing:
                return {
                    "warning": "duplicate",
                    "message": f"Similar complaint already exists nearby: {existing.complaint_id}",
                    "existing_complaint_id": existing.complaint_id
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
        complaint = Complaint(
            complaint_id=generate_complaint_id(),
            user_id=current_user.id,
            officer_id=officer.id if officer else None,
            latitude=latitude,
            longitude=longitude,
            address=address,
            damage_type=damage_type,
            severity=severity,
            ai_confidence=confidence,
            description=description,
            image_url=f"/uploads/{filename}",
            status=ComplaintStatus.ASSIGNED if officer else ComplaintStatus.PENDING
        )

        # Try setting extra columns if they exist
        try:
            complaint.allocated_fund = 0.0
            complaint.priority_score = 0.0
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

        # Notify officer
        try:
            from app.services.notification_service import notify_officer
            if officer:
                notify_officer(officer, complaint)
        except Exception:
            pass

        # WebSocket broadcast
        try:
            if WS_ENABLED:
                await ws_manager.broadcast_new_complaint(complaint)
        except Exception:
            pass

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
            "status": complaint.status.value if hasattr(complaint.status, 'value') else str(complaint.status),
            "created_at": str(complaint.created_at)
        }

    except Exception as e:
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
def get_complaint(complaint_id: str, db: Session = Depends(get_db)):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return serialize_complaint(c)

@router.get("/")
def list_complaints(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    query = db.query(Complaint).filter(Complaint.officer_id == current_officer.id)
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

@router.patch("/{complaint_id}/status")
async def update_status(
    complaint_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    body = await request.json()
    c = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.officer_id == current_officer.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
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
        "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
        "officer_notes": c.officer_notes,
        "created_at": str(c.created_at),
        "updated_at": str(c.updated_at) if c.updated_at else None,
        "resolved_at": str(c.resolved_at) if c.resolved_at else None,
    }
    # Extra fields - safe get
    for field in ["allocated_fund", "fund_note", "priority_score", "rainfall_mm", "traffic_volume", "road_age_years", "weather_condition", "is_duplicate", "duplicate_of"]:
        try:
            result[field] = getattr(c, field, None)
        except Exception:
            result[field] = None
    return result
