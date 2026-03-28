from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_officer, get_current_user
from app.models.models import Complaint, FieldOfficer, Message, User
from app.schemas.schemas import MessageSend
from app.services.auth_service import decode_token

router = APIRouter(prefix="/messages", tags=["messages"])


def _iso(dt):
    if dt is None: return None
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _m(msg: Message) -> dict:
    return {"id": msg.id, "complaint_id": msg.complaint_id,
            "sender_id": msg.sender_id, "sender_role": msg.sender_role,
            "message": msg.message, "created_at": _iso(msg.created_at)}


@router.get("/{complaint_id}")
def get_messages(complaint_id: str, request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    tok  = auth.replace("Bearer ", "").strip()
    if not tok or not decode_token(tok):
        raise HTTPException(401, "Not authenticated")
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c:
        raise HTTPException(404, "Complaint not found")
    msgs = db.query(Message).filter(
        Message.complaint_id == complaint_id
    ).order_by(Message.created_at.asc()).all()
    return [_m(m) for m in msgs]


@router.post("/{complaint_id}/send-citizen")
def send_citizen(complaint_id: str, data: MessageSend,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c: raise HTTPException(404, "Complaint not found")
    msg = Message(complaint_id=complaint_id, sender_id=user.id,
                  sender_role="citizen", message=data.message,
                  created_at=datetime.utcnow())
    db.add(msg); db.commit(); db.refresh(msg)
    return _m(msg)


@router.post("/{complaint_id}/send-officer")
def send_officer(complaint_id: str, data: MessageSend,
                 db: Session = Depends(get_db), officer: FieldOfficer = Depends(get_current_officer)):
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not c: raise HTTPException(404, "Complaint not found")
    msg = Message(complaint_id=complaint_id, sender_id=officer.id,
                  sender_role="officer", message=data.message,
                  created_at=datetime.utcnow())
    db.add(msg); db.commit(); db.refresh(msg)
    return _m(msg)