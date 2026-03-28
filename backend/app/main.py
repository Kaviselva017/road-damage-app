import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import complaints, officers, auth, uploads, messages, admin
from app.database import assert_schema_current

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = Path(complaints.UPLOAD_DIR)

assert_schema_current()

app = FastAPI(title="Road Damage Reporting API", version="3.0.0")


def _load_cors_origins():
    configured = os.getenv("CORS_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://10.0.2.2:8000",
    ]


CORS_ORIGINS = _load_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth.router,       prefix="/api/auth",       tags=["Auth"])
app.include_router(complaints.router, prefix="/api/complaints",  tags=["Complaints"])
app.include_router(officers.router,   prefix="/api/officers",    tags=["Officers"])
app.include_router(uploads.router,    prefix="/api/uploads",     tags=["Uploads"])
app.include_router(messages.router,   prefix="/api/messages",    tags=["Messages"])
app.include_router(admin.router,      prefix="/api/admin",       tags=["Admin"])

@app.get("/healthz")
def healthcheck():
    return {"status": "ok"}

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "login.html")

@app.get("/login")
def login_page():
    return FileResponse(STATIC_DIR / "login.html")

@app.get("/citizen")
def citizen_app():
    return FileResponse(STATIC_DIR / "citizen.html")

@app.get("/dashboard")
def dashboard_app():
    return FileResponse(STATIC_DIR / "dashboard.html")

@app.get("/admin")
def admin_panel():
    return FileResponse(STATIC_DIR / "admin.html")
