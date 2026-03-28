"""
RoadWatch — Auth API
All exceptions return JSON, never plain text 500s.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.models import FieldOfficer, LoginLog, User
from app.schemas.schemas import OfficerLogin, OfficerRegister, TokenResponse, UserLogin, UserRegister
from app.services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register_citizen(data: UserRegister, db: Session = Depends(get_db)):
    # Check duplicate
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in.")

    try:
        user = User(
            name            = data.name.strip(),
            email           = data.email.strip().lower(),
            phone           = (data.phone or "").strip() or None,
            hashed_password = hash_password(data.password),
            is_active       = True,
            reward_points   = 0,
            created_at      = datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

    # Welcome email — never block registration if email fails
    try:
        from app.services.notification_service import notify_welcome
        notify_welcome(user.email, user.name)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[Email] welcome email failed (non-fatal): {e}")

    token = create_access_token({"sub": user.id, "role": "citizen"})
    return TokenResponse(access_token=token, name=user.name)


@router.post("/login", response_model=TokenResponse)
def login_citizen(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled. Contact admin.")
    try:
        db.add(LoginLog(email=data.email, role="citizen", logged_in_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
    token = create_access_token({"sub": user.id, "role": "citizen"})
    return TokenResponse(access_token=token, name=user.name)


@router.post("/officer/login", response_model=TokenResponse)
def login_officer(data: OfficerLogin, db: Session = Depends(get_db)):
    officer = db.query(FieldOfficer).filter(FieldOfficer.email == data.email.strip().lower()).first()
    if not officer or not verify_password(data.password, officer.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not officer.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled. Contact admin.")
    try:
        officer.last_login = datetime.utcnow()
        role = "admin" if officer.is_admin else "officer"
        db.add(LoginLog(email=data.email, role=role, logged_in_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
    role = "admin" if officer.is_admin else "officer"
    token = create_access_token({"sub": officer.id, "role": role})
    return TokenResponse(access_token=token, name=officer.name)


@router.post("/officer/register", response_model=TokenResponse)
def register_officer(
    data: OfficerRegister,
    db: Session = Depends(get_db),
    admin: FieldOfficer = Depends(get_current_admin),
):
    if db.query(FieldOfficer).filter(FieldOfficer.email == data.email.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        officer = FieldOfficer(
            name            = data.name.strip(),
            email           = data.email.strip().lower(),
            phone           = (data.phone or "").strip() or None,
            zone            = data.zone,
            hashed_password = hash_password(data.password),
            is_active       = True,
            is_admin        = False,
            created_at      = datetime.utcnow(),
        )
        db.add(officer)
        db.commit()
        db.refresh(officer)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create officer: {str(e)}")

    token = create_access_token({"sub": officer.id, "role": "officer"})
    return TokenResponse(access_token=token, name=officer.name)