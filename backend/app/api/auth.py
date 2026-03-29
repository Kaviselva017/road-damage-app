"""
RoadWatch — Auth API
Added: GET /auth/me — returns current user info + reward_points
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin, get_current_user
from app.models.models import FieldOfficer, LoginLog, User
from app.schemas.schemas import OfficerLogin, OfficerRegister, TokenResponse, UserLogin, UserRegister
from app.services.auth_service import create_access_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register_citizen(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email.strip().lower()).first():
        raise HTTPException(400, "Email already registered. Please sign in.")
    try:
        user = User(
            name=data.name.strip(),
            email=data.email.strip().lower(),
            phone=(data.phone or "").strip() or None,
            hashed_password=hash_password(data.password),
            is_active=True, reward_points=0,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Registration failed: {str(e)}")

    try:
        from app.services.notification_service import notify_welcome
        notify_welcome(user.email, user.name)
    except Exception:
        pass

    token = create_access_token({"sub": user.id, "role": "citizen"})
    return TokenResponse(access_token=token, name=user.name)


@router.post("/login", response_model=TokenResponse)
def login_citizen(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    try:
        db.add(LoginLog(email=data.email, role="citizen", logged_in_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
    token = create_access_token({"sub": user.id, "role": "citizen"})
    return TokenResponse(access_token=token, name=user.name)


@router.get("/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    """Return current user profile. Works for both citizens and officers."""
    auth  = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")

    role = payload.get("role")
    uid  = payload.get("sub")

    if role == "citizen":
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(404, "User not found")
        return {
            "id":            user.id,
            "name":          user.name,
            "email":         user.email,
            "phone":         user.phone,
            "role":          "citizen",
            "reward_points": user.reward_points or 0,
            "is_active":     user.is_active,
        }
    elif role in ("officer", "admin"):
        officer = db.query(FieldOfficer).filter(FieldOfficer.id == uid).first()
        if not officer:
            raise HTTPException(404, "Officer not found")
        return {
            "id":       officer.id,
            "name":     officer.name,
            "email":    officer.email,
            "phone":    officer.phone,
            "role":     role,
            "zone":     officer.zone,
            "is_admin": officer.is_admin,
        }
    raise HTTPException(401, "Invalid token role")


@router.post("/officer/login", response_model=TokenResponse)
def login_officer(data: OfficerLogin, db: Session = Depends(get_db)):
    officer = db.query(FieldOfficer).filter(FieldOfficer.email == data.email.strip().lower()).first()
    if not officer or not verify_password(data.password, officer.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    if not officer.is_active:
        raise HTTPException(403, "Account is disabled")
    try:
        officer.last_login = datetime.utcnow()
        role = "admin" if officer.is_admin else "officer"
        db.add(LoginLog(email=data.email, role=role, logged_in_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
    role  = "admin" if officer.is_admin else "officer"
    token = create_access_token({"sub": officer.id, "role": role})
    return TokenResponse(access_token=token, name=officer.name)


@router.post("/officer/register", response_model=TokenResponse)
def register_officer(
    data: OfficerRegister,
    db: Session = Depends(get_db),
    admin: FieldOfficer = Depends(get_current_admin),
):
    if db.query(FieldOfficer).filter(FieldOfficer.email == data.email.strip().lower()).first():
        raise HTTPException(400, "Email already registered")
    try:
        officer = FieldOfficer(
            name=data.name.strip(), email=data.email.strip().lower(),
            phone=(data.phone or "").strip() or None, zone=data.zone,
            hashed_password=hash_password(data.password),
            is_active=True, is_admin=False, created_at=datetime.utcnow(),
        )
        db.add(officer)
        db.commit()
        db.refresh(officer)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to create officer: {str(e)}")
    token = create_access_token({"sub": officer.id, "role": "officer"})
    return TokenResponse(access_token=token, name=officer.name)