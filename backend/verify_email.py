import requests
import random
import time

API = "http://127.0.0.1:8000/api"
email = "studentofficial2002@gmail.com"
password = "password123"

print(f"--- Verifying for {email} ---")

# Step 1: Register
print("Registering...")
reg_data = {
    "name": "Student Official",
    "email": email,
    "password": password,
    "phone": "9876543210"
}
res = requests.post(f"{API}/auth/register", json=reg_data)
if res.status_code == 400 and "already" in res.text.lower():
    print("User already exists.")
else:
    print(f"Register status: {res.status_code}")

# Step 2: Login
print("Logging in...")
res = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
if res.status_code != 200:
    print(f"Login failed: {res.text}")
    exit(1)
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Step 3: Submit unique complaint
# Shift coordinates randomly to avoid duplicate detection if testing multiple times
lat = 11.0168 + random.uniform(0.01, 0.05)
lng = 76.9558 + random.uniform(0.01, 0.05)

print(f"Submitting complaint at {lat}, {lng}...")
data = {
    "latitude": lat,
    "longitude": lng,
    "address": "Test Location at " + time.ctime(),
    "nearby_sensitive": "Hospital and School Zone"
}

# Using bad.jpg as the demo image
try:
    with open('bad.jpg', 'rb') as img:
        res = requests.post(f"{API}/complaints/submit", data=data, files={"image": img}, headers=headers)
except FileNotFoundError:
    print("bad.jpg not found, please ensure it exists in the backend directory.")
    exit(1)

print(f"Submit status: {res.status_code}")
print(f"Response: {res.text}")

if res.status_code == 200:
    print("\nSUCCESS: Complaint submitted! Please check your email inbox for studentofficial2002@gmail.com.")
else:
    print("\nFAILED: Submission error.")
