"""
Updated complaints.py — add this to your backend/app/api/complaints.py
Key additions:
1. WebSocket broadcast on new complaint
2. After-repair photo upload endpoint
3. Broadcast on status update
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid, os, shutil

from app.database import get_db
from app.models.models import Complaint, User, FieldOfficer, SeverityLevel, ComplaintStatus
from app.schemas.schemas import ComplaintOut, ComplaintStatusUpdate
from app.services.auth_service import get_current_user, get_current_officer
from app.services.ai_service import analyze_image
from app.services.notification_service import notify_officer

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# WebSocket manager (import from ws_manager.py placed in backend root)
try:
    from ws_manager import manager as ws_manager
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False
    print("WebSocket manager not found — real-time disabled")

def generate_complaint_id() -> str:
    return f"RD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"


# ── WebSocket endpoint ────────────────────────────────
@router.websocket("/ws/officer")
async def websocket_officer(websocket: WebSocket):
    """Officers connect here to receive real-time updates."""
    if not WS_ENABLED:
        await websocket.close(); return
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep alive — accept ping messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Submit Complaint ──────────────────────────────────
@router.post("/submit", response_model=ComplaintOut)
async def submit_complaint(
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: Optional[str] = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Save image
    ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(image.file, f)

    # AI detection
    detection = analyze_image(filepath)

    # Duplicate check (~50m radius)
    existing = db.query(Complaint).filter(
        Complaint.latitude.between(latitude - 0.0005, latitude + 0.0005),
        Complaint.longitude.between(longitude - 0.0005, longitude + 0.0005),
        Complaint.status != ComplaintStatus.COMPLETED
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate complaint nearby: {existing.complaint_id}"
        )

    # Auto-assign officer
    officer = db.query(FieldOfficer).filter(FieldOfficer.is_active == 1).first()

    complaint = Complaint(
        complaint_id=generate_complaint_id(),
        user_id=current_user.id,
        officer_id=officer.id if officer else None,
        latitude=latitude, longitude=longitude, address=address,
        damage_type=detection.damage_type, severity=detection.severity,
        ai_confidence=detection.confidence, description=detection.description,
        image_url=f"/uploads/{filename}",
        status=ComplaintStatus.ASSIGNED if officer else ComplaintStatus.PENDING
    )
    db.add(complaint)
    current_user.points += 10
    db.commit()
    db.refresh(complaint)

    # Notify officer (email/push)
    if officer:
        notify_officer(officer, complaint)

    # Real-time WebSocket broadcast
    if WS_ENABLED:
        await ws_manager.broadcast_new_complaint(complaint)

    return complaint


# ── Upload After-Repair Photo ─────────────────────────
@router.post("/{complaint_id}/after-photo")
async def upload_after_photo(
    complaint_id: str,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    c = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.officer_id == current_officer.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")

    ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
    filename = f"{uuid.uuid4()}_after.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(image.file, f)

    # Store after photo URL (add after_image_url column or use description field)
    c.officer_notes = (c.officer_notes or "") + f"\n[AFTER_PHOTO:/uploads/{filename}]"
    db.commit()
    return {"after_image_url": f"/uploads/{filename}"}


# ── My Complaints ─────────────────────────────────────
@router.get("/my", response_model=List[ComplaintOut])
def my_complaints(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Complaint).filter(
        Complaint.user_id == current_user.id
    ).order_by(Complaint.created_at.desc()).all()


# ── Get Single Complaint ──────────────────────────────
@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: str, db: Session = Depends(get_db)):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return c


# ── List Complaints (Officer) ─────────────────────────
@router.get("/", response_model=List[ComplaintOut])
def list_complaints(
    status: Optional[ComplaintStatus] = None,
    severity: Optional[SeverityLevel] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    query = db.query(Complaint).filter(Complaint.officer_id == current_officer.id)
    if status: query = query.filter(Complaint.status == status)
    if severity: query = query.filter(Complaint.severity == severity)
    return query.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()


# ── Update Status ─────────────────────────────────────
@router.patch("/{complaint_id}/status", response_model=ComplaintOut)
async def update_status(
    complaint_id: str,
    update: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    c = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.officer_id == current_officer.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found")
    c.status = update.status
    if update.officer_notes:
        c.officer_notes = update.officer_notes
    if update.status == ComplaintStatus.COMPLETED:
        c.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(c)

    # Real-time broadcast
    if WS_ENABLED:
        await ws_manager.broadcast_status_update(c)

    return c
