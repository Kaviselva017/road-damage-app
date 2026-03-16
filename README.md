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
├── dashboard/             # React.js officer dashboard
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
- **API Docs:** http://localhost:8000/docs  ← Interactive Swagger UI
- **Officer Dashboard:** http://localhost:3000

---

## Backend Setup (Manual)

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Edit .env with your DB credentials

# Run database migrations
alembic upgrade head       # or let SQLAlchemy auto-create tables

# Start server
uvicorn app.main:app --reload --port 8000
```

---

## Flutter App Setup

```bash
cd mobile
flutter pub get

# Update API base URL in lib/services/api_service.dart:
# static const String baseUrl = 'http://YOUR_SERVER_IP:8000/api';

flutter run
```

**Required Android permissions** (AndroidManifest.xml):
```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.INTERNET" />
```

---

## Dashboard Setup (Manual)

```bash
cd dashboard
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
| POST | /api/auth/officer/register | Officer registration | No |
| POST | /api/auth/officer/login | Officer login | No |
| POST | /api/complaints/submit | Submit complaint + image | Citizen |
| GET | /api/complaints/my | Get my complaints | Citizen |
| GET | /api/complaints/ | List officer complaints | Officer |
| GET | /api/complaints/{id} | Get complaint details | Any |
| PATCH | /api/complaints/{id}/status | Update repair status | Officer |

Full interactive docs: http://localhost:8000/docs

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL connection string |
| SECRET_KEY | JWT signing secret (keep secret!) |
| YOLO_MODEL_PATH | Path to trained .pt model file |
| SENDGRID_API_KEY | For email notifications |
| FROM_EMAIL | Sender email address |
| FIREBASE_CREDENTIALS_PATH | For push notifications |

---

## Deployment (Production)

### AWS EC2 Recommended Setup
1. Launch Ubuntu 22.04 EC2 (t3.medium minimum, p3.xlarge for GPU inference)
2. Install Docker + Docker Compose
3. Clone repo, configure `.env`, run `docker-compose up -d`
4. Set up Nginx reverse proxy + SSL (Let's Encrypt)
5. Point domain DNS to EC2 IP

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
