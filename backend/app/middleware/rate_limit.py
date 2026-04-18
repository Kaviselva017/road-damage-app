import os
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Uses slowapi==0.1.9 with Redis backend
redis_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
if os.getenv("CELERY_ENABLED", "false").lower() not in ("true", "1", "yes"):
    redis_url = "memory://"

# Whitelist env var RATE_LIMIT_WHITELIST (comma-separated IPs)
whitelist_str = os.getenv("RATE_LIMIT_WHITELIST", "")
whitelist_ips = [ip.strip() for ip in whitelist_str.split(",") if ip.strip()]

import uuid

def get_real_ip(request: Request) -> str:
    ip = request.headers.get("x-forwarded-for")
    if not ip:
        ip = get_remote_address(request)
    
    if ip in whitelist_ips:
        return f"whitelist-{uuid.uuid4()}"
    return ip

limiter = Limiter(
    key_func=get_real_ip,
    storage_uri=redis_url,
    strategy="fixed-window"
)

async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # Build a temporary response to have slowapi inject headers
    temp_resp = JSONResponse({"error": "rate_limit_exceeded"}, status_code=429)
    try:
        temp_resp = request.app.state.limiter._inject_headers(
            temp_resp, request.state.view_rate_limit
        )
        retry_after = temp_resp.headers.get("retry-after", 60)
    except Exception:
        retry_after = 60
        
    response = JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "retry_after": int(retry_after)}
    )
    # Add back the headers that slowapi generated
    if 'temp_resp' in locals():
        for k, v in temp_resp.headers.items():
            if k.lower() != 'content-length':
                response.headers[k] = v
                
    return response
