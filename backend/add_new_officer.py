import requests
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

API_BASE = "http://localhost:8000/api/admin"
ADMIN_KEY = os.getenv("ADMIN_SIGNATURE", "MUNICIPAL_AUTH_2026_BYPASS")

payload = {
    "name": "HIT Officer",
    "email": "720823108017@hit.edu.in",
    "password": "password123"
}

headers = {
    "X-Municipal-Signature": ADMIN_KEY,
    "Content-Type": "application/json"
}

try:
    print(f"Adding officer: {payload['email']}...")
    resp = requests.post(f"{API_BASE}/officers", json=payload, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
