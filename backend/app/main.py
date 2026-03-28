"""
RoadWatch — FastAPI Application Entry Point
"""
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.ws_manager import manager

# ── Always create tables (safety net if alembic fails) ────────
Base.metadata.create_all(bind=engine)

# ── Import routers AFTER create_all ───────────────────────────
from app.api import auth, complaints, admin, messages

app = FastAPI(title="RoadWatch API", version="2.0.0", docs_url="/docs")

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Uploads dir ───────────────────────────────────────────────
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ── Static HTML dir ───────────────────────────────────────────
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _html(name: str):
    p = STATIC_DIR / name
    if p.exists():
        return FileResponse(str(p), media_type="text/html")
    return HTMLResponse(f"<h3>{name} not found in static/</h3>", status_code=404)


# ── Page routes ───────────────────────────────────────────────
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


# ── Health ────────────────────────────────────────────────────
@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "ok", "version": "2.0.0"}


# ── API routers ───────────────────────────────────────────────
app.include_router(auth.router,       prefix="/api")
app.include_router(complaints.router, prefix="/api")
app.include_router(messages.router,   prefix="/api")
app.include_router(admin.router,      prefix="/api")


# ── WebSocket ─────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)