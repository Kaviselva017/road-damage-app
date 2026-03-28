from dataclasses import dataclass
from datetime import datetime, timedelta
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import FieldOfficer, User
from app.utils.datetime_utils import utc_now

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
APP_ENV = os.getenv("APP_ENV", "development").lower()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _validate_secret_key():
    insecure_markers = {
        "your-secret-key-change-in-production",
        "roadwatch-secure-key-2026",
        "roadwatch-secure-key-2026-change-in-prod",
        "CHANGE_ME_IN_RENDER",
    }
    if APP_ENV in {"development", "dev", "local", "test"}:
        return
    if not SECRET_KEY or SECRET_KEY in insecure_markers or "change-in-prod" in SECRET_KEY.lower():
        raise RuntimeError("SECRET_KEY must be set to a strong unique value in production")


_validate_secret_key()


@dataclass
class AuthPrincipal:
    role: str
    citizen: User | None = None
    officer: FieldOfficer | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def officer_is_admin(officer: FieldOfficer | None) -> bool:
    return bool(officer and getattr(officer, "is_admin", False))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = utc_now() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _auth_exception(detail: str = "Could not validate credentials", code: int = status.HTTP_401_UNAUTHORIZED):
    return HTTPException(status_code=code, detail=detail)


def _get_id(payload):
    uid = payload.get("user_id") or payload.get("sub")
    try:
        return int(uid)
    except Exception:
        return None


def decode_access_token(token: str):
    ex = _auth_exception()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise ex

    role = payload.get("role")
    uid = _get_id(payload)
    if role not in ("citizen", "officer", "admin") or not uid:
        raise ex
    return payload, role, uid


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    ex = _auth_exception()
    _, role, uid = decode_access_token(token)
    if role != "citizen":
        raise ex
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise ex
    if not user.is_active:
        raise _auth_exception("Account is blocked", status.HTTP_403_FORBIDDEN)
    return user


def get_current_officer(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> FieldOfficer:
    ex = _auth_exception()
    _, role, uid = decode_access_token(token)
    if role not in ("officer", "admin"):
        raise ex
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == uid).first()
    if not officer:
        raise ex
    if not officer.is_active:
        raise _auth_exception("Account is inactive", status.HTTP_403_FORBIDDEN)
    if role == "admin" and not officer_is_admin(officer):
        raise ex
    return officer


def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> FieldOfficer:
    ex = _auth_exception()
    _, role, uid = decode_access_token(token)
    if role != "admin":
        raise ex
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == uid).first()
    if not officer:
        raise ex
    if not officer.is_active:
        raise _auth_exception("Account is inactive", status.HTTP_403_FORBIDDEN)
    if not officer_is_admin(officer):
        raise ex
    return officer


def get_current_principal(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> AuthPrincipal:
    _, role, uid = decode_access_token(token)
    if role == "citizen":
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise _auth_exception()
        if not user.is_active:
            raise _auth_exception("Account is blocked", status.HTTP_403_FORBIDDEN)
        return AuthPrincipal(role=role, citizen=user)

    officer = db.query(FieldOfficer).filter(FieldOfficer.id == uid).first()
    if not officer:
        raise _auth_exception()
    if not officer.is_active:
        raise _auth_exception("Account is inactive", status.HTTP_403_FORBIDDEN)
    if role == "admin" and not officer_is_admin(officer):
        raise _auth_exception()
    return AuthPrincipal(role=role, officer=officer)
