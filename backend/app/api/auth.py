"""
RoadWatch Auth API — endpoints match exactly what login.html & citizen.html call.

  POST /api/auth/register          ← citizen register (login.html + citizen.html)
  POST /api/auth/login             ← citizen login    (login.html + citizen.html)
  POST /api/auth/officer/login     ← officer + admin login (login.html + admin.html)
  POST /api/auth/officer/register  ← create officer from admin panel (admin.html)
  GET  /api/auth/me                ← citizen points refresh (citizen.html)
  GET  /api/auth/admin/me          ← admin name in header (admin.html via /api/auth/officer/login redirects here)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from passlib.context import CryptContext
from jose import jwt
import os
from datetime import datetime, timedelta

from app.database import get_db
from app.models.models import User, FieldOfficer
from app.dependencies import get_current_user, get_current_admin, get_current_officer

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "road-damage-secret-2024")
ALGORITHM  = "HS256"
pwd_ctx    = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_token(data: dict, expires_hours: int = 24) -> str:
    p = data.copy()
    p["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    return jwt.encode(p, SECRET_KEY, algorithm=ALGORITHM)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CitizenRegister(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None


class CitizenLogin(BaseModel):
    email: str
    password: str


class OfficerLogin(BaseModel):
    email: str
    password: str


class OfficerCreate(BaseModel):
    name: str
    email: str
    password: str
    zone: Optional[str] = None
    phone: Optional[str] = None


# ── Citizen Auth ──────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def citizen_register(payload: CitizenRegister, db: Session = Depends(get_db)):
    """POST /api/auth/register — used by login.html & citizen.html"""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=pwd_ctx.hash(payload.password),
        phone=payload.phone,
        reward_points=0,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token({"sub": user.id, "role": "citizen"})
    return {"access_token": token, "token_type": "bearer", "name": user.name}


@router.post("/login")
def citizen_login(payload: CitizenLogin, db: Session = Depends(get_db)):
    """POST /api/auth/login — used by login.html & citizen.html"""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not pwd_ctx.verify(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")
    token = create_token({"sub": user.id, "role": "citizen"})
    return {
        "access_token": token,
        "token_type": "bearer",
        "name": user.name,
        "reward_points": user.reward_points or 0,
    }


# ── Officer / Admin Auth ──────────────────────────────────────────────────────

@router.post("/officer/login")
def officer_login(payload: OfficerLogin, db: Session = Depends(get_db)):
    """POST /api/auth/officer/login — used by both officer & admin in login.html + admin.html"""
    officer = db.query(FieldOfficer).filter(FieldOfficer.email == payload.email).first()
    if not officer or not pwd_ctx.verify(payload.password, officer.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not officer.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")
    officer.last_login = datetime.utcnow()
    db.commit()
    role = "admin" if officer.is_admin else "officer"
    token = create_token({"sub": officer.id, "role": role})
    return {"access_token": token, "token_type": "bearer", "name": officer.name, "role": role}


@router.post("/officer/register", status_code=status.HTTP_201_CREATED)
def officer_register(
    payload: OfficerCreate,
    db: Session = Depends(get_db),
    current_admin: FieldOfficer = Depends(get_current_admin),
):
    """POST /api/auth/officer/register — used by admin.html to create officers"""
    if db.query(FieldOfficer).filter(FieldOfficer.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    officer = FieldOfficer(
        name=payload.name,
        email=payload.email,
        hashed_password=pwd_ctx.hash(payload.password),
        phone=payload.phone,
        zone=payload.zone,
        is_admin=False,
        is_active=True,
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    return {"message": "Officer created", "id": officer.id, "name": officer.name}


# ── /me endpoints ─────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """GET /api/auth/me — citizen points refresh (citizen.html)"""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "reward_points": current_user.reward_points or 0,
    }


@router.get("/admin/me")
def get_admin_me(current_admin: FieldOfficer = Depends(get_current_admin)):
    """GET /api/auth/admin/me — admin name in header"""
    return {
        "id": current_admin.id,
        "name": current_admin.name,
        "email": current_admin.email,
        "is_admin": current_admin.is_admin,
    }