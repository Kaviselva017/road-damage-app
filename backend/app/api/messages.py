from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_officer, get_current_user
from app.models.models import Complaint, FieldOfficer, Message, User
from app.schemas.schemas import MessageSend
from app.services.auth_service import decode_token

router = APIRouter(prefix="/messages", tags=["messages"])


def _iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _m(msg: Message, sender_name: str = None) -> dict:
    return {"id": msg.id, "complaint_id": msg.complaint_id, "sender_id": msg.sender_id, "sender_role": msg.sender_role, "sender_name": sender_name or ("Officer" if msg.sender_role == "officer" else "Citizen"), "message": msg.message, "created_at": _iso(msg.created_at)}


@router.get("/{complaint_id}")
def get_messages(complaint_id: str, request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    tok = auth.replace("Bearer ", "").strip()
    if not tok or not decode_token(tok):
        raise HTTPException(401, "Not authenticated")
    c = db.execute(select(Complaint).filter(Complaint.complaint_id == complaint_id)).scalars().first()
    if not c:
        raise HTTPException(404, "Complaint not found")
    msgs = db.execute(select(Message).filter(Message.complaint_id == complaint_id).order_by(Message.created_at.asc())).scalars().all()
    # Resolve sender names
    result = []
    name_cache = {}
    for m in msgs:
        cache_key = (m.sender_role, m.sender_id)
        if cache_key not in name_cache:
            if m.sender_role == "officer":
                o = db.execute(select(FieldOfficer).filter(FieldOfficer.id == m.sender_id)).scalars().first()
                name_cache[cache_key] = o.name if o else "Officer"
            else:
                u = db.execute(select(User).filter(User.id == m.sender_id)).scalars().first()
                name_cache[cache_key] = u.name if u else "Citizen"
        result.append(_m(m, name_cache[cache_key]))
    return result


@router.post("/{complaint_id}/send-citizen")
def send_citizen(complaint_id: str, data: MessageSend, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.execute(select(Complaint).filter(Complaint.complaint_id == complaint_id)).scalars().first()
    if not c:
        raise HTTPException(404, "Complaint not found")
    msg = Message(complaint_id=complaint_id, sender_id=user.id, sender_role="citizen", message=data.message, created_at=datetime.now(timezone.utc))
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _m(msg, user.name)


@router.post("/{complaint_id}/send-officer")
def send_officer(complaint_id: str, data: MessageSend, db: Session = Depends(get_db), officer: FieldOfficer = Depends(get_current_officer)):
    c = db.execute(select(Complaint).filter(Complaint.complaint_id == complaint_id)).scalars().first()
    if not c:
        raise HTTPException(404, "Complaint not found")
    msg = Message(complaint_id=complaint_id, sender_id=officer.id, sender_role="officer", message=data.message, created_at=datetime.now(timezone.utc))
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _m(msg, officer.name)
