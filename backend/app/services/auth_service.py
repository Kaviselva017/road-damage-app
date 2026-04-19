import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db

"""
RoadWatch — Auth Service
Provides JWT creation/decoding PLUS FastAPI dependency injectors.

New exports used by the complaints router patch:
  - AuthPrincipal   dataclass that carries role + user/officer objects
  - get_current_principal  dependency that accepts both citizen and officer tokens
  - get_current_user       (unchanged)
  - get_current_officer    (unchanged)
"""


env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


SECRET_KEY = os.getenv("SECRET_KEY", "roadwatch-dev-secret-CHANGE-IN-PRODUCTION-2026")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
EXPIRE_MINS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


# ── Password helpers ──────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ── Token helpers ─────────────────────────────────────────────────


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or EXPIRE_MINS)
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        print(f"DEBUG auth_service.decode_token error: {e}")
        return None


# ── Auth principal ────────────────────────────────────────────────


@dataclass
class AuthPrincipal:
    """
    Unified auth context accepted by endpoints that handle both citizens
    and officers (e.g. GET /api/complaints/{id}).
    """

    role: str  # "citizen" | "officer" | "admin"
    citizen: object | None = field(default=None)
    officer: object | None = field(default=None)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin" or bool(self.officer and getattr(self.officer, "is_admin", False))


def _extract_token(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return creds.credentials


# ── FastAPI dependency: citizen only ──────────────────────────────


def get_current_user(
    token: str = Depends(_extract_token),
    db: Session = Depends(get_db),
):
    from app.models.models import User  # local import avoids circular

    payload = decode_token(token)
    if not payload or payload.get("role") != "citizen":
        raise HTTPException(status_code=401, detail="Invalid citizen token")
    user = db.execute(select(User).filter(User.id == payload.get("sub"))).scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


# ── FastAPI dependency: officer / admin only ──────────────────────


def get_current_officer(
    token: str = Depends(_extract_token),
    db: Session = Depends(get_db),
):
    from app.models.models import FieldOfficer  # local import avoids circular

    payload = decode_token(token)
    if not payload or payload.get("role") not in ("officer", "admin"):
        raise HTTPException(status_code=401, detail="Invalid officer token")
    officer = db.execute(select(FieldOfficer).filter(FieldOfficer.id == payload.get("sub"))).scalars().first()
    if not officer or not officer.is_active:
        raise HTTPException(status_code=401, detail="Officer not found or inactive")
    return officer


# ── FastAPI dependency: any authenticated principal ───────────────


def get_current_principal(
    token: str = Depends(_extract_token),
    db: Session = Depends(get_db),
) -> AuthPrincipal:
    """
    Accepts tokens from both citizens and officers.
    Used by endpoints that need to enforce per-resource access control
    without restricting the endpoint to a single role.
    """
    from app.models.models import FieldOfficer, User  # local import avoids circular

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    role = payload.get("role", "")
    sub = payload.get("sub")

    if role == "citizen":
        user = db.execute(select(User).filter(User.id == sub)).scalars().first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return AuthPrincipal(role="citizen", citizen=user)

    if role in ("officer", "admin"):
        officer = db.execute(select(FieldOfficer).filter(FieldOfficer.id == sub)).scalars().first()
        if not officer or not officer.is_active:
            raise HTTPException(status_code=401, detail="Officer not found or inactive")
        resolved_role = "admin" if getattr(officer, "is_admin", False) else "officer"
        return AuthPrincipal(role=resolved_role, officer=officer)

    raise HTTPException(status_code=401, detail="Unknown token role")


# ── Admin guard ───────────────────────────────────────────────────


def get_current_admin(
    officer=Depends(get_current_officer),
):
    if not getattr(officer, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return officer
