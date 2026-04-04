"""
RoadWatch — FastAPI Application Entry Point (v2.2.0)

Improvements over v2.1.0:
  - Global exception handler middleware for clean error responses
  - Structured logging with request context
  - Health check now tests DB connectivity
  - CORS origins from env with proper validation
  - Static file mounts guarded
"""
import logging
import os
import time
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.ws_manager import manager  # noqa – kept for re-export convenience

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("roadwatch")

# ── Import models so they are registered with Base.metadata ─────────
from app.models.models import User, FieldOfficer, Complaint, Notification, Message, LoginLog, ComplaintOfficer # noqa

# ── Always create tables (safety net if alembic fails) ──
Base.metadata.create_all(bind=engine)

# ── Import routers ─────────
from app.api import admin, auth, complaints, messages, officers  # noqa

app = FastAPI(title="RoadWatch API", version="2.2.0", docs_url="/docs")

# ── CORS ──────────────────────────────────────────────────────────────
_raw_origins = os.getenv("CORS_ORIGINS", "*")
if _raw_origins == "*":
    allow_origins     = ["*"]
    allow_credentials = False   # credentials + wildcard origin is invalid
else:
    allow_origins     = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing middleware ─────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    elapsed = (time.perf_counter() - start) * 1000
    if elapsed > 500:  # log slow requests
        logger.warning("SLOW %s %s %.0fms", request.method, request.url.path, elapsed)
    return response


# ── Uploads directory ─────────────────────────────────────────────────
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ── Static HTML pages ─────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _html(name: str):
    p = STATIC_DIR / name
    if p.exists():
        return FileResponse(str(p), media_type="text/html")
    return HTMLResponse(f"<h3>{name} not found in static/</h3>", status_code=404)


# ── Page routes ───────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return _html("login.html")


@app.get("/citizen", include_in_schema=False)
def citizen():
    return _html("citizen.html")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return _html("admin.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return _html("dashboard.html")


# ── Health check (with DB connectivity test) ──────────────────────────
@app.get("/healthz", include_in_schema=False)
def health():
    try:
        from sqlalchemy import text
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": "2.2.0",
        "database": "connected" if db_ok else "error",
    }


# ── API routers ───────────────────────────────────────────────────────
app.include_router(auth.router,       prefix="/api")
app.include_router(complaints.router, prefix="/api")
app.include_router(messages.router,   prefix="/api")
app.include_router(admin.router,      prefix="/api")
app.include_router(officers.router,   prefix="/api")

# NOTE: The /api/complaints/ws/officer WebSocket endpoint lives inside
# complaints.router.  There is intentionally NO separate /ws endpoint here —
# having two managers broadcasting to different sets of sockets was a bug.

logger.info("RoadWatch v2.2.0 ready")