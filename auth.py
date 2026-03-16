from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User, FieldOfficer, LoginLog
from app.services.auth_service import pwd_context, create_access_token, get_current_user
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None

class OfficerRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    zone: Optional[str] = None

def log_login(db, email, role, name, ip, status, user_id=None):
    log = LoginLog(
        user_id=user_id,
        email=email,
        role=role,
        name=name,
        ip_address=ip,
        logged_in_at=datetime.utcnow(),
        status=status
    )
    db.add(log)
    db.commit()

# ── Citizen Register ──────────────────────────────────
@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=req.name, email=req.email,
        phone=req.phone,
        hashed_password=pwd_context.hash(req.password),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Account created successfully", "id": user.id}

# ── Citizen Login ─────────────────────────────────────
@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not pwd_context.verify(req.password, user.hashed_password):
        log_login(db, req.email, "citizen", None, ip, "failed")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        log_login(db, req.email, "citizen", user.name, ip, "blocked")
        raise HTTPException(status_code=403, detail="Account is blocked")
    token = create_access_token({"sub": str(user.id), "role": "citizen"})
    log_login(db, req.email, "citizen", user.name, ip, "success", user_id=user.id)
    return {"access_token": token, "token_type": "bearer", "name": user.name}

# ── Officer Login ─────────────────────────────────────
@router.post("/officer/login")
def officer_login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    officer = db.query(FieldOfficer).filter(FieldOfficer.email == req.email).first()
    if not officer or not pwd_context.verify(req.password, officer.hashed_password):
        log_login(db, req.email, "officer", None, ip, "failed")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not officer.is_active:
        log_login(db, req.email, "officer", officer.name, ip, "blocked")
        raise HTTPException(status_code=403, detail="Account is inactive")
    role = "admin" if officer.zone == "All Zones" else "officer"
    token = create_access_token({"sub": str(officer.id), "role": role})
    log_login(db, req.email, role, officer.name, ip, "success", user_id=officer.id)
    return {"access_token": token, "token_type": "bearer", "name": officer.name, "role": role}

# ── Officer Register ──────────────────────────────────
@router.post("/officer/register")
def officer_register(req: OfficerRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(FieldOfficer).filter(FieldOfficer.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    officer = FieldOfficer(
        name=req.name, email=req.email,
        phone=req.phone, zone=req.zone,
        hashed_password=pwd_context.hash(req.password),
        is_active=True
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    return {"message": "Officer created", "id": officer.id}

# ── Get Login Logs (Admin) ────────────────────────────
@router.get("/logs")
def get_login_logs(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db)
):
    logs = db.query(LoginLog).order_by(LoginLog.logged_in_at.desc()).offset(skip).limit(limit).all()
    return [{
        "id": l.id, "email": l.email, "role": l.role,
        "name": l.name, "ip_address": l.ip_address,
        "logged_in_at": l.logged_in_at.isoformat() if l.logged_in_at else None,
        "status": l.status
    } for l in logs]
