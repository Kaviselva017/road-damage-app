from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import bcrypt

from app.database import get_db
from app.models import Officer, Complaint, Citizen
from app.dependencies import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class OfficerCreate(BaseModel):
    name: str
    email: str
    password: str
    badge_number: str
    phone: Optional[str] = None


# ── Officers ─────────────────────────────────────────────────────────────────

@router.get("/officers")
def list_officers(
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    officers = db.query(Officer).filter(Officer.is_admin == False).all()
    return [
        {
            "id": o.id,
            "name": o.name,
            "email": o.email,
            "badge_number": o.badge_number,
            "phone": getattr(o, "phone", None),
            "is_active": getattr(o, "is_active", True),
        }
        for o in officers
    ]


@router.post("/officers", status_code=status.HTTP_201_CREATED)
def create_officer(
    payload: OfficerCreate,
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    # Check duplicate email
    if db.query(Officer).filter(Officer.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check duplicate badge
    if db.query(Officer).filter(Officer.badge_number == payload.badge_number).first():
        raise HTTPException(status_code=400, detail="Badge number already in use")

    hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    officer = Officer(
        name=payload.name,
        email=payload.email,
        hashed_password=hashed,
        badge_number=payload.badge_number,
        phone=payload.phone,
        is_admin=False,
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    return {"message": "Officer created successfully", "id": officer.id}


@router.delete("/officers/{officer_id}")
def delete_officer(
    officer_id: int,
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    officer = db.query(Officer).filter(Officer.id == officer_id).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    if officer.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin account")
    db.delete(officer)
    db.commit()
    return {"message": "Officer deleted"}


# ── Citizens ──────────────────────────────────────────────────────────────────

@router.get("/citizens")
def list_citizens(
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    citizens = db.query(Citizen).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": getattr(c, "phone", None),
            "reward_points": getattr(c, "reward_points", 0),
        }
        for c in citizens
    ]


# ── Complaints ────────────────────────────────────────────────────────────────

@router.get("/complaints")
def list_complaints(
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    complaints = db.query(Complaint).all()
    result = []
    for c in complaints:
        citizen = db.query(Citizen).filter(Citizen.id == c.citizen_id).first()
        officer = db.query(Officer).filter(Officer.id == c.assigned_officer_id).first() if c.assigned_officer_id else None
        result.append(
            {
                "id": c.id,
                "description": c.description,
                "location": getattr(c, "location", ""),
                "status": c.status,
                "severity": getattr(c, "severity", "medium"),
                "image_url": getattr(c, "image_url", None),
                "created_at": str(c.created_at) if hasattr(c, "created_at") else "",
                "citizen_name": citizen.name if citizen else "Unknown",
                "officer_name": officer.name if officer else "Unassigned",
            }
        )
    return result


@router.put("/complaints/{complaint_id}/assign")
def assign_complaint(
    complaint_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    officer_id = payload.get("officer_id")
    if officer_id:
        officer = db.query(Officer).filter(Officer.id == officer_id).first()
        if not officer:
            raise HTTPException(status_code=404, detail="Officer not found")
    complaint.assigned_officer_id = officer_id
    db.commit()
    return {"message": "Complaint assigned"}


@router.put("/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    complaint.status = payload.get("status", complaint.status)
    db.commit()
    return {"message": "Status updated"}


# ── Dashboard Stats ───────────────────────────────────────────────────────────

@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    total_complaints = db.query(Complaint).count()
    pending = db.query(Complaint).filter(Complaint.status == "pending").count()
    resolved = db.query(Complaint).filter(Complaint.status == "resolved").count()
    total_citizens = db.query(Citizen).count()
    total_officers = db.query(Officer).filter(Officer.is_admin == False).count()
    return {
        "total_complaints": total_complaints,
        "pending_complaints": pending,
        "resolved_complaints": resolved,
        "total_citizens": total_citizens,
        "total_officers": total_officers,
    }