from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import Message, Complaint, User, FieldOfficer
from app.schemas.schemas import MessageCreate, MessageOut
from app.services.auth_service import AuthPrincipal, get_current_principal, get_current_user, get_current_officer
from app.utils.datetime_utils import serialize_datetime

router = APIRouter()


def _is_admin_officer(officer: FieldOfficer) -> bool:
    return bool(getattr(officer, "is_admin", False))


def _serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "complaint_id": message.complaint_id,
        "sender_role": message.sender_role,
        "sender_name": message.sender_name,
        "message": message.message,
        "created_at": serialize_datetime(message.created_at),
    }

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
    if complaint.officer_id != current_officer.id and not _is_admin_officer(current_officer):
        raise HTTPException(status_code=403, detail="Not authorized to message this complaint")
    message = Message(
        complaint_id=complaint_id,
        sender_role="officer",
        sender_name=current_officer.name,
        message=msg.message
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return _serialize_message(message)

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
    if complaint.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to message this complaint")
    message = Message(
        complaint_id=complaint_id,
        sender_role="citizen",
        sender_name=current_user.name,
        message=msg.message
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return _serialize_message(message)

@router.get("/{complaint_id}", response_model=List[MessageOut])
def get_messages(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_principal: AuthPrincipal = Depends(get_current_principal)
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if current_principal.role == "citizen":
        if not current_principal.citizen or complaint.user_id != current_principal.citizen.id:
            raise HTTPException(status_code=403, detail="Not authorized to access messages for this complaint")
    elif not current_principal.is_admin:
        if not current_principal.officer or complaint.officer_id != current_principal.officer.id:
            raise HTTPException(status_code=403, detail="Not authorized to access messages for this complaint")
    messages = db.query(Message).filter(
        Message.complaint_id == complaint_id
    ).order_by(Message.created_at.asc()).all()
    return [_serialize_message(message) for message in messages]

@router.get("/citizen/all", response_model=List[MessageOut])
def get_citizen_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    complaints = db.query(Complaint).filter(Complaint.user_id == current_user.id).all()
    complaint_ids = [c.complaint_id for c in complaints]
    messages = db.query(Message).filter(
        Message.complaint_id.in_(complaint_ids),
        Message.sender_role == "officer"
    ).order_by(Message.created_at.desc()).all()
    return [_serialize_message(message) for message in messages]
