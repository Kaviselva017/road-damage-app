from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
import os

router = APIRouter()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
