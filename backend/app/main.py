"""
RoadWatch — FastAPI Application Entry Point (v2.2.0)

Clean, modularized setup with:
  - Sentry & Prometheus integrated
  - Lifespan-based task & metrics management
  - Strict Pydantic settings
  - WebSocket & Background Workers
"""
import logging
import os
import time
import json
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_fastapi_instrumentator import Instrumentator
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration

# ── Environment & Config ──────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

class Settings(BaseSettings):
    APP_ENV: str = "production"
    CORS_ORIGINS: str = ""
    SENTRY_DSN: str | None = None
    APP_VERSION: str = "1.0.0"
    
    model_config = SettingsConfigDict(env_file=str(env_path), extra="ignore")

    @model_validator(mode="after")
    def validate_origins(self) -> Self:
        if self.APP_ENV != "development":
            if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
                raise ValueError("CORS_ORIGINS must be set in production.")
        return self

    @property
    def parsed_cors_origins(self) -> list[str]:
        if self.APP_ENV == "development":
            return ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://10.0.2.2:8000"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

settings = Settings()

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("roadwatch")

# ── Sentry Initialization ─────────────────────────────────────────────
def _sentry_before_send(event, hint):
    if "user" in event and "email" in event["user"]:
        event["user"].pop("email")
    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]
        from fastapi import HTTPException
        if isinstance(exc_value, HTTPException) and exc_value.status_code in (401, 403, 404, 422):
            return None
    return event

# Removed module-level sentry init

# ── Core Services & DB ───────────────────────────────────────────────
from app.database import Base, engine
from app.ws_manager import manager # noqa
from app.models.models import User, FieldOfficer, Complaint, Notification, Message, LoginLog, ComplaintOfficer # noqa
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

Base.metadata.create_all(bind=engine)
limiter = Limiter(key_func=get_remote_address)

# Initialize Instrumentator globally so it's available in lifespan
instrumentator = Instrumentator(
    should_group_status_codes=True,
    env_var_name="ENABLE_METRICS",
)

# ── Lifespan & App Setup ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    from app.tasks.escalation_task import run_escalation_check
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_escalation_check, "interval", hours=1)
    scheduler.start()
    
    # Instrumentation
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
    
    sentry_dsn = os.getenv("SENTRY_DSN", "")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("APP_ENV", "production"),
            release="roadwatch@2.2.0",
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            before_send=lambda event, hint: event,  # hook for PII scrubbing
        )
        logger.info("Sentry initialized for environment: %s", os.getenv("APP_ENV"))
    else:
        logger.warning("SENTRY_DSN not set — error monitoring disabled")

    logger.info(f"RoadWatch {settings.APP_VERSION} started ({settings.APP_ENV})")
    yield
    scheduler.shutdown()

app = FastAPI(
    title="RoadWatch API",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

instrumentator.instrument(app)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        if response.status_code >= 500:
            sentry_sdk.capture_message(f"{response.status_code}: {request.method} {request.url.path}", level="error")
    except Exception:
        sentry_sdk.capture_message(f"5xx: {request.method} {request.url.path}", level="error")
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    
    elapsed = (time.perf_counter() - start) * 1000
    if elapsed > 1000:
        logger.warning(f"SLOW {request.method} {request.url.path} {elapsed:.0f}ms")
    return response

# ── Directories ───────────────────────────────────────────────────────
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def _html(name: str):
    p = STATIC_DIR / name
    return FileResponse(str(p), media_type="text/html") if p.exists() else HTMLResponse("Not Found", status_code=404)

# ── Routes ────────────────────────────────────────────────────────────
from app.api import admin, auth, complaints, messages, officers, map
app.include_router(auth.router,       prefix="/api")
app.include_router(complaints.router, prefix="/api")
app.include_router(messages.router,   prefix="/api")
app.include_router(admin.router,      prefix="/api")
app.include_router(officers.router,   prefix="/api")
app.include_router(map.router,        prefix="/api")

@app.get("/", include_in_schema=False)
def root(): return _html("login.html")

@app.get("/healthz", include_in_schema=False)
def health():
    return {
        "status": "ok",
        "sentry": "configured" if os.getenv("SENTRY_DSN") else "not_configured",
        "env": settings.APP_ENV
    }

if settings.APP_ENV == "development":
    @app.post("/api/debug/sentry-test", tags=["debug"])
    def trigger_error():
        raise ZeroDivisionError("Sentry test")

# ── WebSockets ────────────────────────────────────────────────────────
from app.websockets.complaint_ws import complaint_ws_manager
from app.services.auth_service import decode_token

@app.websocket("/ws/complaints/{complaint_id}")
async def websocket_complaint_status(websocket: WebSocket, complaint_id: str, token: str = None):
    if not token or not decode_token(token):
        await websocket.close(code=4001)
        return

    await complaint_ws_manager.connect(complaint_id, websocket)
    
    async def keep_alive():
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except: break

    ping_task = asyncio.create_task(keep_alive())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        complaint_ws_manager.disconnect(complaint_id, websocket)
    finally:
        ping_task.cancel()