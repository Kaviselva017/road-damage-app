from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id                 = Column(Integer, primary_key=True)
    jti                = Column(String(36),  unique=True, nullable=False, index=True)
    user_id            = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash         = Column(String(256), nullable=False)
    family_id          = Column(String(36),  nullable=False, index=True)
    device_fingerprint = Column(String(512), nullable=True)
    created_at         = Column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at         = Column(DateTime,    nullable=False)
    used_at            = Column(DateTime,    nullable=True)
    revoked            = Column(Boolean,     nullable=False, default=False)


class RevocationToken(Base):
    __tablename__ = "revocation_tokens"

    id         = Column(Integer, primary_key=True)
    token      = Column(String(64), unique=True, nullable=False)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    used       = Column(Boolean,  nullable=False, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
