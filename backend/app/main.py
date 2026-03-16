from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import complaints, officers, auth, uploads, messages, admin
from app.database import engine, Base
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Road Damage Reporting API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router,       prefix="/api/auth",       tags=["Auth"])
app.include_router(complaints.router, prefix="/api/complaints",  tags=["Complaints"])
app.include_router(officers.router,   prefix="/api/officers",    tags=["Officers"])
app.include_router(uploads.router,    prefix="/api/uploads",     tags=["Uploads"])
app.include_router(messages.router,   prefix="/api/messages",    tags=["Messages"])
app.include_router(admin.router,      prefix="/api/admin",       tags=["Admin"])

@app.get("/")
def root():
    return FileResponse("static/login.html")

@app.get("/login")
def login_page():
    return FileResponse("static/login.html")

@app.get("/citizen")
def citizen_app():
    return FileResponse("static/citizen.html")

@app.get("/dashboard")
def dashboard_app():
    return FileResponse("static/dashboard.html")

@app.get("/admin")
def admin_panel():
    return FileResponse("static/admin.html")
