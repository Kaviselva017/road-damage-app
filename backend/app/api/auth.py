"""
RoadWatch Auth API
Endpoints used by login.html, citizen.html, admin.html — matched exactly.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from passlib.context import CryptContext
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import User, FieldOfficer, LoginLog
from app.dependencies import get_current_user, get_current_admin
from app.services.auth_service import create_access_token
from app.services import audit_service
import os
from app.main import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _make_token(data: dict) -> str:
    """Create a JWT using the shared auth_service (same SECRET_KEY)."""
    return create_access_token(data)


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


class FcmTokenUpdate(BaseModel):
    fcm_token: str


# ── Citizen Register ──────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(os.getenv("RATE_LIMIT_AUTH", "20/minute"))
def citizen_register(request: Request, payload: CitizenRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """POST /api/auth/register — login.html & citizen.html"""
    try:
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

        # Send welcome email in background
        try:
            from app.services.notification_service import notify_welcome
            background_tasks.add_task(notify_welcome, to_email=user.email, citizen_name=user.name)
        except Exception as e:
            logging.getLogger("roadwatch").warning(f"Failed to queue welcome email: {e}")

        token = _make_token({"sub": str(user.id), "role": "citizen"})
        return {"access_token": token, "token_type": "bearer", "name": user.name}
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger("roadwatch").error(f"Registration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Citizen Login ─────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit(os.getenv("RATE_LIMIT_AUTH", "20/minute"))
def citizen_login(payload: CitizenLogin, request: Request, db: Session = Depends(get_db)):
    """POST /api/auth/login — login.html & citizen.html"""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not pwd_ctx.verify(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")
    token = _make_token({"sub": str(user.id), "role": "citizen"})
    # Log the login
    db.add(LoginLog(
        email=payload.email, role="citizen",
        ip_address=request.client.host if request.client else None,
        logged_in_at=_now(),
    ))
    db.commit()

    # AUDIT: User Access
    audit_service.log_event(
        db, "user", str(user.id), "accessed", 
        actor_id=user.id, actor_role="citizen", 
        request=request
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "name": user.name,
        "reward_points": user.reward_points or 0,
    }


# ── Officer / Admin Login ─────────────────────────────────────────────────────

@router.post("/officer/login")
def officer_login(payload: OfficerLogin, request: Request, db: Session = Depends(get_db)):
    """POST /api/auth/officer/login — login.html (officer+admin) & admin.html doLogin()"""
    officer = db.query(FieldOfficer).filter(FieldOfficer.email == payload.email).first()
    if not officer or not pwd_ctx.verify(payload.password, officer.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not officer.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")
    officer.last_login = _now()
    role = "admin" if officer.is_admin else "officer"
    # Log the login
    db.add(LoginLog(
        email=payload.email, role=role,
        ip_address=request.client.host if request.client else None,
        logged_in_at=_now(),
    ))
    db.commit()
    token = _make_token({"sub": str(officer.id), "role": role})

    # AUDIT: Officer Access
    audit_service.log_event(
        db, "officer", str(officer.id), "accessed", 
        actor_id=officer.id, actor_role=role, 
        request=request
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "name": officer.name,
        "role": role,
    }


# ── Create Officer (admin only) ───────────────────────────────────────────────

@router.post("/officer/register", status_code=status.HTTP_201_CREATED)
def officer_register(
    payload: OfficerCreate,
    db: Session = Depends(get_db),
    current_admin: FieldOfficer = Depends(get_current_admin),
):
    """POST /api/auth/officer/register — admin.html Add Officer modal"""
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


# ── /me ───────────────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """GET /api/auth/me — citizen.html fetchUserPoints()"""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "reward_points": current_user.reward_points or 0,
    }


@router.patch("/fcm-token")
def update_fcm_token(
    payload: FcmTokenUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """PATCH /api/auth/fcm-token — update FCM token for push notifications."""
    if payload.fcm_token == "":
        current_user.fcm_token = None
    else:
        current_user.fcm_token = payload.fcm_token
    db.commit()
    return {"status": "ok"}


@router.get("/admin/me")
def get_admin_me(current_admin: FieldOfficer = Depends(get_current_admin)):
    return {
        "id": current_admin.id,
        "name": current_admin.name,
        "email": current_admin.email,
    }


# ── Login Logs (admin only) ──────────────────────────────────────────────────

@router.get("/logs")
def get_login_logs(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    """GET /api/auth/logs — returns all login logs (admin only)"""
    rows = db.query(LoginLog).order_by(LoginLog.logged_in_at.desc()).limit(200).all()
    return [{
        "id": r.id,
        "email": r.email,
        "role": r.role,
        "ip_address": r.ip_address,
        "logged_in_at": _iso(r.logged_in_at),
        "logged_out_at": _iso(r.logged_out_at),
        "session_minutes": r.session_minutes,
    } for r in rows]