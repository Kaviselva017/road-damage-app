"""
RoadWatch — Auth API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.models import FieldOfficer, LoginLog, User
from app.schemas.schemas import (
    OfficerLogin, OfficerRegister, TokenResponse, UserLogin, UserRegister,
)
from app.services.auth_service import create_access_token, hash_password, verify_password
from app.services import notification_service as ns

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register_citizen(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already registered")
    user = User(
        name            = data.name,
        email           = data.email,
        phone           = data.phone,
        hashed_password = hash_password(data.password),
        is_active       = True,
        reward_points   = 0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Welcome email
    try:
        ns.notify_welcome(user.email, user.name)
    except Exception:
        pass

    token = create_access_token({"sub": user.id, "role": "citizen"})
    return TokenResponse(access_token=token, name=user.name)


@router.post("/login", response_model=TokenResponse)
def login_citizen(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account inactive")
    db.add(LoginLog(email=data.email, role="citizen"))
    db.commit()
    token = create_access_token({"sub": user.id, "role": "citizen"})
    return TokenResponse(access_token=token, name=user.name)


@router.post("/officer/login", response_model=TokenResponse)
def login_officer(data: OfficerLogin, db: Session = Depends(get_db)):
    from datetime import datetime
    officer = db.query(FieldOfficer).filter(FieldOfficer.email == data.email).first()
    if not officer or not verify_password(data.password, officer.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    if not officer.is_active:
        raise HTTPException(403, "Account inactive")
    officer.last_login = datetime.utcnow()
    role = "admin" if officer.is_admin else "officer"
    db.add(LoginLog(email=data.email, role=role))
    db.commit()
    token = create_access_token({"sub": officer.id, "role": role})
    return TokenResponse(access_token=token, name=officer.name)


@router.post("/officer/register", response_model=TokenResponse)
def register_officer(
    data:  OfficerRegister,
    db:    Session       = Depends(get_db),
    admin: FieldOfficer  = Depends(get_current_admin),
):
    if db.query(FieldOfficer).filter(FieldOfficer.email == data.email).first():
        raise HTTPException(400, "Email already registered")
    officer = FieldOfficer(
        name            = data.name,
        email           = data.email,
        phone           = data.phone,
        zone            = data.zone,
        hashed_password = hash_password(data.password),
        is_active       = True,
        is_admin        = False,
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    token = create_access_token({"sub": officer.id, "role": "officer"})
    return TokenResponse(access_token=token, name=officer.name)