# Citizen-Based AI Road Damage Reporting System

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Flutter App    │────▶│  FastAPI Backend  │────▶│   PostgreSQL DB  │
│  (Citizen)      │     │  + YOLOv8 AI     │     └──────────────────┘
└─────────────────┘     └──────────────────┘
                                │
                         ┌──────▼──────┐
                         │ React.js    │
                         │ Dashboard   │
                         │ (Officers)  │
                         └─────────────┘
```

## Project Structure

```
road-damage-app/
├── backend/               # FastAPI Python backend
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── api/           # Route handlers
│   │   └── services/      # AI, Auth, Notifications
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── mobile/                # Flutter citizen app
│   ├── lib/
│   │   ├── main.dart
│   │   ├── screens/
│   │   └── services/
│   └── pubspec.yaml
├── frontend/              # Vite.js officer dashboard
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   └── services/
│   ├── package.json
│   └── Dockerfile
├── ai_model/              # YOLOv8 model + training docs
└── docker-compose.yml
```

---

## Quickstart (Docker)

### 1. Clone and configure
```bash
cd road-damage-app
cp backend/.env.example backend/.env
# Edit backend/.env with your values
```

### 2. Add your AI model
```bash
# Place your trained YOLOv8 model at:
cp /path/to/best.pt ai_model/road_damage_yolov8.pt
# (Without this, system runs in mock/demo mode)
```

### 3. Start all services
```bash
docker-compose up --build
```

Services will be available at:
- **API:** http://localhost:8000
- **Health:** http://localhost:8000/healthz
- **API Docs:** http://localhost:8000/docs  ← Interactive Swagger UI
- **Officer Dashboard:** http://localhost:3000

---

## Backend Setup (Manual)

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe backend\seed.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000

# macOS / Linux
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
python -m alembic -c backend/alembic.ini upgrade head
python backend/seed.py
python -m uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
```

You can also start from the backend folder with:

```bash
# Bash
./start.sh

# PowerShell
./start.ps1
```

From the repo root, the wrapper scripts `./start.sh` and `./start.ps1` delegate to the backend startup path.

Fresh local SQLite databases should be initialized through Alembic and the seed script.
`backend/start.sh` and `backend/start.ps1` run `alembic upgrade head` before starting Uvicorn.
Direct `uvicorn` startup now requires the database to already be at the Alembic head revision.

Render and Docker entrypoints are also wired through `backend/start.sh`, so deployments apply migrations before the app boots.

For local test tooling and CI parity, install:

```bash
pip install -r backend/requirements-dev.txt
```

To verify that local-only artifacts are not tracked in git:

```bash
python scripts/check_repo_hygiene.py
```

---

## Flutter App Setup

```bash
cd mobile
flutter pub get

# Optional:
# flutter run --dart-define=ROADWATCH_API_URL=http://127.0.0.1:8000/api

flutter run
```

**Required Android permissions** (AndroidManifest.xml):
```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.INTERNET" />
```

---

## Frontend Setup (Manual)

```bash
cd frontend
npm install
# Create .env file:
echo "VITE_API_URL=http://localhost:8000/api" > .env
npm run dev     # Development
npm run build   # Production build
```

---

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /api/auth/register | Citizen registration | No |
| POST | /api/auth/login | Citizen login | No |
| POST | /api/auth/officer/register | Officer registration | Admin |
| POST | /api/auth/officer/login | Officer login | No |
| POST | /api/complaints/submit | Submit complaint + image | Citizen |
| GET | /api/complaints/my | Get my complaints | Citizen |
| GET | /api/complaints/ | List officer complaints | Officer |
| GET | /api/complaints/{id} | Get complaint details | Owner / Assigned Officer / Admin |
| PATCH | /api/complaints/{id}/status | Update repair status | Officer |

Full interactive docs: http://localhost:8000/docs
Health check: http://localhost:8000/healthz

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL connection string |
| SECRET_KEY | JWT signing secret (keep secret!) |
| APP_ENV | `development` locally, `production` in deployed environments |
| CORS_ORIGINS | Comma-separated allowed frontend origins |
| YOLO_MODEL_PATH | Path to trained .pt model file |
| RESEND_API_KEY | Primary email provider API key for hosted deployments |
| SMTP_USER | Optional SMTP username for local fallback email delivery |
| SMTP_PASS | Optional SMTP password for local fallback email delivery |
| EMAIL_FROM | Sender name and email address |
| ADMIN_EMAIL | Recipient for high-severity admin alerts |
| BASE_URL | Public app base URL used in notification links |

---

## Deployment (Production)

### AWS EC2 Recommended Setup
1. Launch Ubuntu 22.04 EC2 (t3.medium minimum, p3.xlarge for GPU inference)
2. Install Docker + Docker Compose
3. Clone repo, configure `.env`, run `docker-compose up -d`
4. Set up Nginx reverse proxy + SSL (Let's Encrypt)
5. Point domain DNS to EC2 IP
6. Set a strong `SECRET_KEY`, explicit `CORS_ORIGINS`, `BASE_URL`, and production `DATABASE_URL`

### Google Cloud Run (Serverless)
- Deploy backend as Cloud Run service
- Use Cloud SQL for PostgreSQL
- Use Cloud Storage for uploaded images

---

## Next Steps for Production

- [ ] Train YOLOv8 on RDD2022 dataset (see ai_model/README.md)
- [ ] Configure SendGrid for email notifications
- [ ] Set up Firebase for push notifications  
- [ ] Add Google Maps API key for map dashboard
- [ ] Enable SSL/HTTPS
- [ ] Set up S3/GCS for image storage (replace local uploads)
- [ ] Add admin panel for managing officers and zones
- [ ] Set up monitoring (Sentry, Datadog)
