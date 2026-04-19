from __future__ import annotations

import logging
import os

import redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AUTH_FAIL_LIMIT = int(os.getenv("AUTH_FAIL_LIMIT", 10))
AUTH_FAIL_TTL   = int(os.getenv("AUTH_FAIL_TTL_SECONDS", 3600))   # 1 hour window
LOCKOUT_TTL     = int(os.getenv("AUTH_LOCKOUT_SECONDS", 3600))    # 1 hour lockout

try:
    _redis = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
    _redis.ping()
except Exception:
    _redis = None
    logger.warning("Redis not available — JWT blacklist and rate limiting disabled")


# ── public helpers ────────────────────────────────────────────────────────────

def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    """Called on logout to prevent reuse of the access token until it expires."""
    if _redis:
        try:
            _redis.setex(f"blacklist:{jti}", ttl_seconds, "1")
        except Exception as e:
            logger.error("Redis blacklist write failed: %s", e)


def is_jti_blacklisted(jti: str) -> bool:
    if not _redis:
        return False
    try:
        return bool(_redis.exists(f"blacklist:{jti}"))
    except Exception:
        return False


def record_auth_failure(identifier: str) -> int:
    """Increment failure counter. Returns current count."""
    if not _redis:
        return 0
    key = f"auth_fail:{identifier}"
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, AUTH_FAIL_TTL)
        return count
    except Exception:
        return 0


def clear_auth_failures(identifier: str) -> None:
    if _redis:
        try:
            _redis.delete(f"auth_fail:{identifier}")
        except Exception:
            pass


def is_account_locked(identifier: str) -> bool:
    if not _redis:
        return False
    try:
        count_raw = _redis.get(f"auth_fail:{identifier}")
        return int(count_raw or 0) >= AUTH_FAIL_LIMIT
    except Exception:
        return False


def lock_account(identifier: str) -> None:
    if _redis:
        try:
            _redis.setex(f"auth_fail:{identifier}", LOCKOUT_TTL, str(AUTH_FAIL_LIMIT))
        except Exception:
            pass


# ── security headers middleware ───────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = \
            "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["Referrer-Policy"]         = "no-referrer"
        response.headers["Content-Security-Policy"] = \
            "default-src 'self'; img-src 'self' data: https:; " \
            "script-src 'self'; style-src 'self' 'unsafe-inline'"
        return response
