import sentry_sdk
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import FieldOfficer, User
from app.services.auth_service import decode_token

bearer = HTTPBearer(auto_error=False)


def _token(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return creds.credentials


def get_current_user(token: str = Depends(_token), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    if not payload or payload.get("role") != "citizen":
        raise HTTPException(status_code=401, detail="Invalid citizen token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    sentry_sdk.set_user({"id": user.id, "email": user.email, "role": "citizen"})
    return user


def get_current_officer(token: str = Depends(_token), db: Session = Depends(get_db)) -> FieldOfficer:
    payload = decode_token(token)
    if not payload or payload.get("role") not in ("officer", "admin"):
        raise HTTPException(status_code=401, detail="Invalid officer token")
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == payload.get("sub")).first()
    if not officer or not officer.is_active:
        raise HTTPException(status_code=401, detail="Officer not found or inactive")
    sentry_sdk.set_user({"id": officer.id, "email": officer.email, "role": payload.get("role")})
    return officer


def get_current_admin(officer: FieldOfficer = Depends(get_current_officer)) -> FieldOfficer:
    if not officer.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return officer
