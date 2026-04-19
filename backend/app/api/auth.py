"""
RoadWatch — Auth API (Google OAuth2 + Phone verification)
AUTH-1: Google Sign-In, JWT access/refresh tokens, rotation, logout
AUTH-2: Phone number collection, E.164 validation, uniqueness
"""

import uuid
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import phonenumbers
from phonenumbers import NumberParseException
from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import get_db
from app.models.models import User
from app.services.google_auth_service import google_auth_service
from app.dependencies import get_current_user, get_current_temp_user

from app.services.token_service import (
    issue_token_pair, rotate_refresh_token,
    revoke_all_user_tokens, make_revocation_token, consume_revocation_token,
)
from app.middleware.security import (
    blacklist_jti, record_auth_failure,
    clear_auth_failures, is_account_locked, lock_account, AUTH_FAIL_LIMIT,
)

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET       = os.getenv("JWT_SECRET_KEY", "changeme")
REFRESH_SECRET   = os.getenv("REFRESH_SECRET_KEY", "changeme2")
ACCESS_EXPIRE    = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_EXPIRE   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ALGORITHM        = "HS256"
TEMP_EXPIRE_MIN  = 10

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_access_token(user_id: int, google_sub: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE)
    return jwt.encode(
        {"sub": str(user_id), "google_sub": google_sub,
         "jti": str(uuid.uuid4()), "exp": exp},
        JWT_SECRET, algorithm=ALGORITHM
    )

def _make_refresh_token(user_id: int, google_sub: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE)
    return jwt.encode(
        {"sub": str(user_id), "google_sub": google_sub,
         "jti": str(uuid.uuid4()), "type": "refresh", "exp": exp},
        REFRESH_SECRET, algorithm=ALGORITHM
    )

def _make_temp_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=TEMP_EXPIRE_MIN)
    return jwt.encode(
        {"sub": str(user_id), "type": "temp", "exp": exp},
        JWT_SECRET, algorithm=ALGORITHM
    )

def _hash(token: str) -> str:
    import hashlib
    # SHA-256 first to avoid bcrypt's 72-byte truncation (JWTs share prefixes)
    digest = hashlib.sha256(token.encode()).hexdigest()
    return bcrypt.hashpw(digest.encode(), bcrypt.gensalt()).decode()

def _verify_hash(token: str, hashed: str) -> bool:
    import hashlib
    digest = hashlib.sha256(token.encode()).hexdigest()
    return bcrypt.checkpw(digest.encode(), hashed.encode())

# ── schemas ───────────────────────────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    id_token: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

class PhoneRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def normalise_e164(cls, v: str) -> str:
        try:
            parsed = phonenumbers.parse(v, None)
        except NumberParseException:
            raise ValueError("Invalid phone number. Use +CountryCodeNumber e.g. +919876543210")
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number. Use +CountryCodeNumber e.g. +919876543210")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

# ── routes ────────────────────────────────────────────────────────────────────

@router.post("/google")
async def google_login(
    body: GoogleLoginRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        g_user = google_auth_service.verify_id_token(body.id_token)
    except HTTPException:
        # Count failures per Google sub (use raw token prefix as identifier)
        identifier = body.id_token[:32]
        count = record_auth_failure(identifier)
        if count >= AUTH_FAIL_LIMIT:
            lock_account(identifier)
        raise

    if not g_user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified by Google")

    user = db.query(User).filter(User.google_sub == g_user.sub).first()
    is_new = False

    if is_account_locked(g_user.sub):
        raise HTTPException(status_code=423,
                            detail="Account temporarily locked. Check your email.")

    if not user:
        is_new = True
        user = User(
            google_sub=g_user.sub, email=g_user.email,
            name=g_user.name, picture_url=g_user.picture,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.name = g_user.name
        user.picture_url = g_user.picture
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()

    clear_auth_failures(g_user.sub)

    if is_new:
        from app.services.email_templates import welcome_email
        from app.services.email_service import email_service
        subj, html = welcome_email(user.name, user.email)
        background_tasks.add_task(email_service.send_email_sync, user.email, subj, html)

    if not user.phone_number:
        return {"requires_phone": True, "temp_token": _make_temp_token(user.id)}

    pair = issue_token_pair(user, db, request)
    return {
        "requires_phone": False,
        "access_token":  pair.access_token,
        "refresh_token": pair.refresh_token,
        "user": {"id": user.id, "name": user.name,
                 "email": user.email, "picture": user.picture_url},
    }


@router.post("/refresh")
def refresh_token(
    body: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    pair, _ = rotate_refresh_token(body.refresh_token, db, request)
    return {"access_token": pair.access_token, "refresh_token": pair.refresh_token}


@router.post("/logout")
def logout(
    body: LogoutRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    # Blacklist the current access token
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        jti = payload.get("jti", "")
        exp = payload.get("exp", 0)
        ttl = max(0, int(exp - datetime.now(timezone.utc).timestamp()))
        blacklist_jti(jti, ttl)
    except JWTError:
        pass  # already invalid — fine

    # Revoke the refresh token record
    try:
        rp = jwt.decode(body.refresh_token, REFRESH_SECRET, algorithms=[ALGORITHM])
        from app.models.refresh_token import RefreshToken
        rec = db.query(RefreshToken).filter(
            RefreshToken.jti == rp.get("jti")
        ).first()
        if rec:
            rec.revoked = True
            db.commit()
    except JWTError:
        pass

    return {"message": "Logged out"}


@router.post("/logout-all")
def logout_all_devices(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    revoke_all_user_tokens(current_user.id, db)
    revoke_token = make_revocation_token(current_user.id, db)
    return {"message": "All sessions revoked", "revoke_token": revoke_token}


@router.get("/revoke-all")
def revoke_all_via_email_link(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """One-time link from suspicious login email — no auth header needed."""
    user_id = consume_revocation_token(token, db)
    revoke_all_user_tokens(user_id, db)

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        from app.services.email_service import email_service
        # Send confirmation — reuse status_update as a simple notify
        background_tasks.add_task(email_service.send_email_sync,
            user.email,
            "All devices signed out — Road Damage Reporter",
            f"<p>Hi {user.name}, all sessions have been signed out successfully.</p>"
            f"<p>If you didn't request this, please contact support.</p>",
        )

    return {"message": "All sessions signed out. You can now sign in again safely."}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id, "name": current_user.name,
        "email": current_user.email, "picture": current_user.picture_url,
        "phone": current_user.phone_number,
    }


@router.post("/phone")
def set_phone(
    body: PhoneRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_temp_user),
):
    # Uniqueness check
    existing = db.query(User).filter(
        User.phone_number == body.phone_number,
        User.id != user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "phone_already_registered",
                "message": "This number is linked to another account.",
            },
        )

    user.phone_number = body.phone_number
    user.phone_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Issue full token pair now that profile is complete
    pair = issue_token_pair(user, db, request)

    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "user": {
            "id": user.id, "name": user.name, "email": user.email,
            "picture": user.picture_url, "phone": user.phone_number,
        },
    }


@router.get("/check-phone")
def check_phone_availability(phone: str, db: Session = Depends(get_db)):
    """Real-time availability check — rate limited 10 req/min per IP."""
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"available": False, "reason": "invalid_format"}
        normalised = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except NumberParseException:
        return {"available": False, "reason": "invalid_format"}

    taken = db.query(User).filter(User.phone_number == normalised).first()
    return {"available": taken is None}
