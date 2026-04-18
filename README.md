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

### Authentication (Firebase)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /api/auth/sync-user | Register or login citizen via Firebase ID token | Firebase JWT |
| POST | /api/auth/sync-officer | Register or login officer via Firebase ID token | Firebase JWT |
| PUT | /api/auth/fcm-token | Update FCM push notification token | Bearer |

### Complaints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /api/complaints/submit | Submit complaint with image + GPS | Bearer |
| GET | /api/complaints/my | Get authenticated citizen's complaints | Bearer |
| GET | /api/complaints/{id}/status | Poll complaint analysis status | Bearer |
| GET | /api/complaints/nearby | Complaints within radius (meters) | Bearer |
| GET | /api/complaints/ | List all complaints (officer view) | Officer |
| PATCH | /api/complaints/{id}/status | Update repair status | Officer |
| POST | /api/complaints/{id}/resolve | Close complaint with proof photo | Officer |

### Maps & Analytics

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /api/map/heatmap | Clustered complaint heatmap data | None |
| GET | /api/map/hotspots | Top damage hotspots ranked by severity | Officer |
| GET | /api/map/timeline | Daily complaint counts (7/30/90 days) | None |

### Admin

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /api/admin/stats | System-wide statistics | Admin |
| GET | /api/admin/officers | List all field officers | Admin |
| POST | /api/admin/officers | Register new officer | Admin |
| GET | /api/admin/sla/dashboard | SLA compliance overview | Admin |
| GET | /api/admin/audit/complaint/{id} | Full audit trail | Admin |

Full interactive docs: http://localhost:8000/docs

---

## Environment Variables

### Core

| Variable | Description | Required |
|----------|-------------|----------|
| APP_ENV | `development` or `production` | Yes |
| APP_VERSION | App version string e.g. `1.0.0` | Yes |
| CORS_ORIGINS | Comma-separated allowed frontend origins | Yes |

### Database (Supabase)

| Variable | Description | Required |
|----------|-------------|----------|
| DATABASE_URL | `postgresql://postgres:[pw]@db.xxxx.supabase.co:5432/postgres` | Yes |
| SUPABASE_URL | `https://xxxx.supabase.co` | Yes |
| SUPABASE_SERVICE_KEY | Service role secret key | Yes |
| SUPABASE_ANON_KEY | Public anon key | Yes |

### Authentication (Firebase)

| Variable | Description | Required |
|----------|-------------|----------|
| FIREBASE_PROJECT_ID | Firebase project ID | Yes |
| FIREBASE_SERVICE_ACCOUNT_JSON | Base64-encoded service account JSON | Yes |

### AI Model

| Variable | Description | Required |
|----------|-------------|----------|
| YOLO_MODEL_PATH | Path to trained model e.g. `ai_model/best.pt` | Yes |
| YOLO_CONFIDENCE_THRESHOLD | Minimum detection confidence (default: `0.60`) | No |

### Cache (Upstash Redis)

| Variable | Description | Required |
|----------|-------------|----------|
| REDIS_URL | Redis connection URL (supports `rediss://`) | No |
| MAX_UPLOAD_SIZE_MB | Max photo upload size in MB (default: `10`) | No |

### Notifications

| Variable | Description | Required |
|----------|-------------|----------|
| RESEND_API_KEY | Resend email API key | No |

### Observability

| Variable | Description | Required |
|----------|-------------|----------|
| SENTRY_DSN | Sentry backend DSN | No |

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
