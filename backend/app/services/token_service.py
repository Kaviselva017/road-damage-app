from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken, RevocationToken
from app.models.models import User

logger = logging.getLogger(__name__)

JWT_SECRET      = os.getenv("JWT_SECRET_KEY",     "changeme")
REFRESH_SECRET  = os.getenv("REFRESH_SECRET_KEY", "changeme2")
ALGORITHM       = "HS256"
ACCESS_EXPIRE   = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_EXPIRE  = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS",   7))
MAX_SESSIONS    = int(os.getenv("MAX_CONCURRENT_SESSIONS",     5))


@dataclass
class TokenPair:
    access_token:  str
    refresh_token: str
    jti:           str
    family_id:     str


# ── hashing ───────────────────────────────────────────────────────────────────

def _sha256(value: str) -> bytes:
    """Pre-hash with SHA-256 before bcrypt to avoid 72-byte truncation."""
    return hashlib.sha256(value.encode()).digest()

def hash_token(token: str) -> str:
    return bcrypt.hashpw(_sha256(token), bcrypt.gensalt()).decode()

def verify_token_hash(token: str, hashed: str) -> bool:
    return bcrypt.checkpw(_sha256(token), hashed.encode())


# ── device fingerprint ────────────────────────────────────────────────────────

def device_fingerprint(request: Request) -> str:
    ua   = request.headers.get("user-agent", "")
    lang = request.headers.get("accept-language", "")
    ip   = request.client.host if request.client else ""
    raw  = f"{ip}|{ua}|{lang}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── token creation ────────────────────────────────────────────────────────────

def issue_token_pair(
    user: User,
    db: Session,
    request: Optional[Request] = None,
    family_id: Optional[str] = None,
) -> TokenPair:
    now        = datetime.now(timezone.utc)
    jti        = str(uuid.uuid4())
    fid        = family_id or str(uuid.uuid4())
    expires_at = now + timedelta(days=REFRESH_EXPIRE)
    fp         = device_fingerprint(request) if request else None

    access = jwt.encode(
        {"sub": str(user.id), "google_sub": user.google_sub,
         "jti": jti, "exp": now + timedelta(minutes=ACCESS_EXPIRE)},
        JWT_SECRET, algorithm=ALGORITHM,
    )
    refresh_raw = jwt.encode(
        {"sub": str(user.id), "google_sub": user.google_sub,
         "jti": jti, "type": "refresh", "exp": expires_at},
        REFRESH_SECRET, algorithm=ALGORITHM,
    )

    db.add(RefreshToken(
        jti=jti,
        user_id=user.id,
        token_hash=hash_token(refresh_raw),
        family_id=fid,
        device_fingerprint=fp,
        created_at=now,
        expires_at=expires_at,
        revoked=False,
    ))
    db.flush()

    # Enforce concurrent session limit — revoke oldest family if over limit
    active = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked == False,
        )
        .order_by(RefreshToken.created_at.asc())
        .all()
    )
    # Filter expired ones manually if needed to count properly, but for concurrent limit, non-revoked is fine.
    active = [r for r in active if getattr(r.expires_at, "replace", lambda **kw: r.expires_at)(tzinfo=timezone.utc) > now]
    if len(active) > MAX_SESSIONS:
        oldest_family = active[0].family_id
        _revoke_family(oldest_family, db)
        logger.info("Session limit reached for user %s — revoked family %s",
                    user.id, oldest_family)

    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh_raw,
                     jti=jti, family_id=fid)


# ── rotation ──────────────────────────────────────────────────────────────────

def rotate_refresh_token(
    raw_token: str,
    db: Session,
    request: Optional[Request] = None,
) -> tuple[TokenPair, User]:
    """Returns new TokenPair. Raises HTTPException on any security violation."""
    try:
        payload = jwt.decode(raw_token, REFRESH_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    jti = payload.get("jti")
    record = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()

    if not record:
        raise HTTPException(status_code=401, detail="Token not found")

    if record.revoked:
        raise HTTPException(status_code=401, detail="Token revoked")

    
    # SQLite naive datetime vs timezone-aware. Let's make sure it's UTC before compare
    exp = record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    if not verify_token_hash(raw_token, record.token_hash):
        raise HTTPException(status_code=401, detail="Token hash mismatch")

    # ── stolen token detection ────────────────────────────────────────────────
    if record.used_at is not None:
        logger.warning(
            "STOLEN TOKEN DETECTED — family %s user %s — revoking all",
            record.family_id, record.user_id,
        )
        _revoke_family(record.family_id, db)
        db.commit()

        user = db.query(User).filter(User.id == record.user_id).first()
        if user:
            _send_compromise_email(user, request)

        raise HTTPException(
            status_code=401,
            detail="Session invalidated due to suspicious activity. Please sign in again.",
        )

    # ── device fingerprint mismatch (warn, don't block) ───────────────────────
    if request and record.device_fingerprint:
        fp = device_fingerprint(request)
        if fp != record.device_fingerprint:
            logger.warning(
                "Device fingerprint mismatch for user %s — possible token theft",
                record.user_id,
            )
            user = db.query(User).filter(User.id == record.user_id).first()
            if user:
                _send_suspicious_login_email(user, request)

    # Mark used and rotate
    record.used_at = datetime.now(timezone.utc)
    db.commit()

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_pair = issue_token_pair(user, db, request, family_id=record.family_id)
    return new_pair, user


# ── revocation helpers ────────────────────────────────────────────────────────

def _revoke_family(family_id: str, db: Session) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.family_id == family_id
    ).update({"revoked": True})


def revoke_all_user_tokens(user_id: int, db: Session) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id
    ).update({"revoked": True})
    db.commit()


def make_revocation_token(user_id: int, db: Session) -> str:
    tok = secrets.token_urlsafe(32)
    db.add(RevocationToken(
        token=tok,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    return tok


def consume_revocation_token(token: str, db: Session) -> int:
    """Returns user_id on success, raises 401/410 on failure."""
    rec = db.query(RevocationToken).filter(RevocationToken.token == token).first()
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid revocation token")
    if rec.used:
        raise HTTPException(status_code=410, detail="Link already used")
        
    exp = rec.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Link expired")
        
    rec.used = True
    db.commit()
    return rec.user_id


# ── email helpers (import deferred to avoid circular) ────────────────────────

def _send_compromise_email(user: User, request: Optional[Request]) -> None:
    try:
        from app.services.email_service import email_service
        from app.services.email_templates import suspicious_login_email
        import asyncio
        ip       = request.client.host if request and request.client else "unknown"
        device   = request.headers.get("user-agent", "unknown") if request else "unknown"
        subj, html = suspicious_login_email(
            name=user.name, email=user.email,
            ip=ip, location="unknown", device=device,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            revoke_url=f"{os.getenv('FRONTEND_URL','')}/auth/revoke-all",
        )
        asyncio.create_task(email_service.send_email(user.email, subj, html))
    except Exception as e:
        logger.error("Failed to send compromise email: %s", e)


def _send_suspicious_login_email(user: User, request: Request) -> None:
    _send_compromise_email(user, request)
