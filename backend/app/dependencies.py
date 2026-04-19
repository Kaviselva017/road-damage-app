import os
from jose import JWTError, jwt
import sentry_sdk
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import FieldOfficer, User
from app.services.auth_service import decode_token
from app.middleware.security import is_jti_blacklisted, is_account_locked

JWT_SECRET  = os.getenv("JWT_SECRET_KEY", "changeme")
ALGORITHM   = "HS256"

bearer = HTTPBearer(auto_error=False)


def _token(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return creds.credentials


def get_current_user(token: str = Depends(_token), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") == "temp":
        raise HTTPException(status_code=401, detail="Temp token — complete phone setup")

    jti = payload.get("jti", "")
    if is_jti_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    user = db.execute(select(User).filter(User.id == int(payload.get("sub", 0)))).scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    
    google_sub = payload.get("google_sub", "")
    if is_account_locked(google_sub):
        raise HTTPException(status_code=423, detail="Account temporarily locked")

    sentry_sdk.set_user({"id": user.id, "email": user.email, "role": "citizen"})
    return user

def get_current_temp_user(token: str = Depends(_token), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired temp token")

    if payload.get("type") != "temp":
        raise HTTPException(status_code=401, detail="Not a temp token")

    user = db.execute(select(User).filter(User.id == int(payload.get("sub", 0)))).scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_phone_complete(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.phone_number:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "phone_required",
                "message": "Add your phone number to submit complaints.",
            },
        )
    return current_user


def get_current_officer(token: str = Depends(_token), db: Session = Depends(get_db)) -> FieldOfficer:
    print(f"DEBUG: get_current_officer token len: {len(token)}")
    payload = decode_token(token)
    print(f"DEBUG: get_current_officer payload: {payload}")
    if not payload or payload.get("role") not in ("officer", "admin"):
        print("DEBUG: get_current_officer raising 401 because payload role mismatch or no payload")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    officer = db.execute(select(FieldOfficer).filter(FieldOfficer.id == payload.get("sub"))).scalars().first()
    print(f"DEBUG: get_current_officer officer found: {officer}")
    if not officer or not officer.is_active:
        print("DEBUG: get_current_officer raising 401 because officer not found or not active")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sentry_sdk.set_user({"id": officer.id, "email": officer.email, "role": payload.get("role")})
    return officer


def get_current_admin(officer: FieldOfficer = Depends(get_current_officer)) -> FieldOfficer:
    if not officer.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return officer
