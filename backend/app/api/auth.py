from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import bcrypt
import jwt
import os
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Officer, Citizen
from app.dependencies import get_current_citizen, get_current_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "road-damage-secret-2024")
ALGORITHM = "HS256"


def create_token(data: dict, expires_hours: int = 24) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


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
    badge_number: str


class AdminLogin(BaseModel):
    email: str
    password: str
    admin_code: str


# ── Citizen Auth ──────────────────────────────────────────────────────────────

@router.post("/citizen/register", status_code=status.HTTP_201_CREATED)
def citizen_register(payload: CitizenRegister, db: Session = Depends(get_db)):
    if db.query(Citizen).filter(Citizen.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    citizen = Citizen(
        name=payload.name,
        email=payload.email,
        hashed_password=hashed,
        phone=payload.phone,
        reward_points=0,
    )
    db.add(citizen)
    db.commit()
    db.refresh(citizen)
    token = create_token({"sub": str(citizen.id), "role": "citizen"})
    return {"access_token": token, "token_type": "bearer", "name": citizen.name}


@router.post("/citizen/login")
def citizen_login(payload: CitizenLogin, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.email == payload.email).first()
    if not citizen or not bcrypt.checkpw(payload.password.encode(), citizen.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": str(citizen.id), "role": "citizen"})
    return {
        "access_token": token,
        "token_type": "bearer",
        "name": citizen.name,
        "reward_points": citizen.reward_points,
    }


# ── Officer Auth ──────────────────────────────────────────────────────────────

@router.post("/officer/login")
def officer_login(payload: OfficerLogin, db: Session = Depends(get_db)):
    officer = (
        db.query(Officer)
        .filter(Officer.email == payload.email, Officer.badge_number == payload.badge_number)
        .first()
    )
    if not officer or not bcrypt.checkpw(payload.password.encode(), officer.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if officer.is_admin:
        raise HTTPException(status_code=403, detail="Use admin login")
    token = create_token({"sub": str(officer.id), "role": "officer"})
    return {"access_token": token, "token_type": "bearer", "name": officer.name}


# ── Admin Auth ────────────────────────────────────────────────────────────────

ADMIN_CODE = os.getenv("ADMIN_CODE", "ADM-2030")


@router.post("/admin/login")
def admin_login(payload: AdminLogin, db: Session = Depends(get_db)):
    if payload.admin_code != ADMIN_CODE:
        raise HTTPException(status_code=401, detail="Invalid admin code")
    officer = db.query(Officer).filter(Officer.email == payload.email, Officer.is_admin == True).first()
    if not officer or not bcrypt.checkpw(payload.password.encode(), officer.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": str(officer.id), "role": "admin"})
    return {"access_token": token, "token_type": "bearer", "name": officer.name}


# ── /me endpoints ─────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_citizen: Citizen = Depends(get_current_citizen),
):
    """Returns current citizen info including reward_points."""
    return {
        "id": current_citizen.id,
        "name": current_citizen.name,
        "email": current_citizen.email,
        "reward_points": getattr(current_citizen, "reward_points", 0),
    }


@router.get("/admin/me")
def get_admin_me(
    db: Session = Depends(get_db),
    current_admin: Officer = Depends(get_current_admin),
):
    return {
        "id": current_admin.id,
        "name": current_admin.name,
        "email": current_admin.email,
    }