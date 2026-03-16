# Road Damage System V2 — Upgrade Guide

## What's New in V2

| Feature | Details |
|--------|---------|
| 🌐 Citizen Web App | Full browser-based reporting with camera + GPS |
| 🗺 Live Google Maps | All complaints shown as colored markers by severity |
| 🔄 Real-time Updates | New complaints appear instantly via polling (10s) |
| 📸 Before/After | Drag slider to compare road before and after repair |
| 📍 Auto GPS | Browser captures exact GPS coordinates automatically |
| 🔔 Toast Alerts | Officer gets popup when new complaint arrives |
| 📊 Split/Map/List views | Officer can switch dashboard layout |

---

## Step 1 — Set up Citizen Web App

The citizen web app is a single HTML file — no build needed!

Copy it to your backend's static folder:

```bash
# From road-damage-v2 folder:
copy citizen-web\index.html D:\python\road-damage-app\backend\static\index.html
```

Then add static file serving to your backend `main.py`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add after app = FastAPI(...)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/citizen")
def citizen_app():
    return FileResponse("static/index.html")
```

Then visit: **http://localhost:8000/citizen**

---

## Step 2 — Set up Officer Dashboard V2

Same approach — single HTML file:

```bash
copy dashboard-v2\index.html D:\python\road-damage-app\backend\static\dashboard.html
```

Visit: **http://localhost:8000/static/dashboard.html**

OR open the file directly in browser:
```
D:\python\road-damage-v2\dashboard-v2\index.html
```

---

## Step 3 — Add Google Maps API Key

1. Go to: https://console.cloud.google.com
2. Create a project → Enable **Maps JavaScript API**
3. Create credentials → API Key
4. Open `dashboard-v2/index.html`
5. Find line: `const GMAPS_KEY = 'YOUR_GOOGLE_MAPS_API_KEY';`
6. Replace with your key

**Free tier**: Google Maps gives $200/month free credit (~28,000 map loads).

---

## Step 4 — Enable WebSocket Real-time Updates

Copy the WebSocket manager to your backend:

```bash
copy ws_manager.py D:\python\road-damage-app\backend\ws_manager.py
```

Replace your complaints API:
```bash
copy complaints_updated.py D:\python\road-damage-app\backend\app\api\complaints.py
```

The officer dashboard connects automatically via WebSocket on load.

---

## Step 5 — Add static folder and serve uploads

In `backend/app/main.py`, add:

```python
from fastapi.staticfiles import StaticFiles
import os

os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")
```

---

## Step 6 — Test the full flow

1. Start backend: `uvicorn app.main:app --reload`
2. Open citizen app: http://localhost:8000/citizen
3. Register/login as Ravi (ravi@citizen.com / ravi123)
4. Capture photo + submit complaint
5. Open officer dashboard: open dashboard-v2/index.html in browser
6. Login as Maran (maran@road.com / maran123)
7. See complaint appear on map within 10 seconds!
8. Click complaint → update status → upload after photo
9. Drag the before/after slider to compare

---

## Citizen App Features
- 📷 Camera capture (mobile) or gallery upload (desktop)
- 📍 Auto GPS with map preview
- 🤖 AI severity shown after submission
- 📋 Track complaint progress with step indicator
- 🔄 Auto-refreshes every 15 seconds

## Officer Dashboard Features  
- 🗺 Live Google Map with color-coded markers
- 🔴🟡🟢 Filter by severity or status
- 📊 Stats bar (total/pending/active/done)
- 🔔 Toast notification for new complaints
- 📸 Before/After drag comparison
- ✏️ Update status + officer notes
- 3 layout modes: Split / Map Only / List Only
