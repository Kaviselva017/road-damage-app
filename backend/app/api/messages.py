from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import Message, Complaint, User, FieldOfficer
from app.schemas.schemas import MessageCreate, MessageOut
from app.services.auth_service import get_current_user, get_current_officer

router = APIRouter()

@router.post("/{complaint_id}/send-officer", response_model=MessageOut)
def officer_send_message(
    complaint_id: str,
    msg: MessageCreate,
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer)
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    message = Message(
        complaint_id=complaint_id,
        sender_role="officer",
        sender_name=current_officer.name,
        message=msg.message
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

@router.post("/{complaint_id}/send-citizen", response_model=MessageOut)
def citizen_send_message(
    complaint_id: str,
    msg: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    message = Message(
        complaint_id=complaint_id,
        sender_role="citizen",
        sender_name=current_user.name,
        message=msg.message
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

@router.get("/{complaint_id}", response_model=List[MessageOut])
def get_messages(
    complaint_id: str,
    db: Session = Depends(get_db)
):
    return db.query(Message).filter(
        Message.complaint_id == complaint_id
    ).order_by(Message.created_at.asc()).all()

@router.get("/citizen/all", response_model=List[MessageOut])
def get_citizen_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    complaints = db.query(Complaint).filter(Complaint.user_id == current_user.id).all()
    complaint_ids = [c.complaint_id for c in complaints]
    return db.query(Message).filter(
        Message.complaint_id.in_(complaint_ids),
        Message.sender_role == "officer"
    ).order_by(Message.created_at.desc()).all()