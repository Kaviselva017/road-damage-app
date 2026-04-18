# RoadWatch — AI Road Damage Reporting System

[![CI](https://github.com/Kaviselva017/road-damage-app/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Kaviselva017/road-damage-app/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688.svg)
![Flutter](https://img.shields.io/badge/Flutter-3.19.0-02569B.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## What It Does
RoadWatch is an end-to-end infrastructure monitoring solution designed to bridge the gap between citizens and municipal authorities. The system enables citizens to capture road damage photos through a mobile application, which are then analyzed in real-time by a YOLOv8-powered AI engine to classify damage types, assess severity, and calculate priority scores based on local context, weather patterns, and proximity to sensitive areas like hospitals or schools.

The platform provides a centralized command center for government officials, offering a real-time heatmap of damage clusters, automated officer assignment, and a secure audit trail for every report. By automating the identification and prioritization process, RoadWatch ensures that critical infrastructure repairs are fast-tracked, budget allocations are data-driven, and citizens are kept informed through instant status updates and push notifications.

## Architecture Diagram
```text
┌─────────────────┐      ┌────────────────────┐      ┌─────────────────┐
│  Flutter App    │─────▶│  FastAPI Backend   │─────▶│  PostgreSQL/GIS │
│  (Citizen iOS/Ad)│◀────▶│  + YOLOv8 Engine   │◀────▶│  (Persistent)   │
└─────────────────┘      └────────────────────┘      └─────────────────┘
         ▲                          │                         ▲
         │                  ┌───────▼───────┐                 │
         │                  │ Redis Cache   │                 │
         │                  │ (Queue/PubSub)│                 │
         │                  └───────┬───────┘                 │
         │                          │                         │
┌────────▼────────┐         ┌───────▼───────┐         ┌───────▼───────┐
│ React Dashboard │◀───────▶│ WebSocket     │◀───────▶│ S3 Object     │
│ (Officer/Admin) │         │ (Live Feed)   │         │ (Images/PDFs) │
└─────────────────┘         └───────────────┘         └───────────────┘
```

## Project Structure
```text
road-damage-app/
├── backend/               # Python 3.11 FastAPI server
│   ├── app/               # Core application logic
│   ├── tests/             # Pytest suite with 90%+ coverage
│   ├── Dockerfile         # Production container config
│   └── requirements.txt   # Backend dependencies
├── frontend/              # React + Vite officer dashboard
│   ├── src/               # UI components and pages
│   └── package.json       # Frontend dependencies
├── mobile/                # Flutter citizen mobile app
│   ├── lib/               # BLoC/Service-based architecture
│   └── pubspec.yaml       # Mobile dependencies
├── ai_model/              # YOLOv8 weights and training notebooks
└── .github/               # CI/CD (GitHub Actions) workflows
```

## Quickstart (Docker)
```bash
git clone https://github.com/Kaviselva017/road-damage-app
cd road-damage-app
cp backend/.env.example backend/.env
docker-compose up --build
```

## Environment Variables

| Group | Variable | Description |
| :--- | :--- | :--- |
| **Core** | `APP_ENV` | `development` or `production` |
| | `CORS_ORIGINS` | Comma-separated allowed origins |
| | `BASE_URL` | Public API URL for PDF external links |
| **Database** | `DATABASE_URL` | PostgreSQL + PostGIS connection string |
| | `SUPABASE_URL` | Supabase project URL |
| | `SUPABASE_SERVICE_KEY` | Supabase service role key |
| **AI Model** | `YOLO_MODEL_PATH` | Path to `best.pt` file |
| | `YOLO_CONFIDENCE_THRESHOLD` | Detection sensitivity (0.0 - 1.0) |
| **Storage** | `S3_BUCKET_NAME` | Bucket name for damage photos |
| | `S3_ACCESS_KEY_ID` | Access key for S3/R2 storage |
| | `S3_SECRET_ACCESS_KEY` | Secret key for S3/R2 storage |
| **Notifications** | `RESEND_API_KEY` | Email service API key |
| | `FIREBASE_SENDER_ID` | FCM project sender ID |
| **Monitoring** | `SENTRY_DSN` | Sentry error tracking URL |
| | `ENABLE_METRICS` | Expose `/metrics` for Prometheus (`true`/`false`) |
| **Realtime** | `REDIS_URL` | Connection string for Redis cache & PubSub |

## API Reference

| Category | Endpoint | Description | Auth |
| :--- | :--- | :--- | :--- |
| **Reporting** | `POST /api/complaints/submit` | Submit damage with AI analysis & GPS | Citizen |
| | `GET /api/complaints/{id}/status` | Poll real-time analysis status | Bearer |
| **Maps** | `GET /api/map/heatmap` | Clustered hotspots & spatial density | Public |
| | `GET /api/map/hotspots` | Ranked high-priority damage areas | Officer |
| **Management** | `PATCH /api/complaints/{id}/status` | Update repair state (assigned/resolved) | Officer |
| | `GET /api/admin/stats` | Global analytics & performance KPIs | Admin |
| **Official** | `GET /api/complaints/{id}/export/pdf` | Generate legal PDF report | Officer |
| | `GET /api/complaints/export/bulk` | Export CSV/PDF for date range | Admin |
| **Realtime** | `ws:///ws/admin/feed` | Live WebSocket stream of all activities | Admin |
| | `ws:///ws/officers/location` | Real-time GPS tracking for field teams | Officer |

## Deployment (Render)
1. **Fork this repository** to your personal GitHub account.
2. **Connect to Render**: Create a New Web Service (Backend) and a New Static Site (Frontend).
3. **Environment Setup**: Add all variables from `backend/.env.example` to the Render Dashboard.
4. **CI Integration**: Add `RENDER_DEPLOY_HOOK_URL`, `SUPABASE_URL`, and `FIREBASE_SERVICE_ACCOUNT_JSON` to GitHub Secrets.
5. **Initial Deploy**: Push a commit or trigger the manual deploy hook from the Render dashboard.

## Training the AI Model
The AI engine uses the YOLOv8 architecture trained on the RDD2022 (Road Damage Dataset). You can retrain the model with your own regional data by following the instructions in `ai_model/train_rdd2022.ipynb`. For high-performance training, it is recommended to run this notebook in Google Colab with a GPU-accelerated runtime.

## Contributing
We welcome contributions to RoadWatch! Please ensure that all Python code follows the Ruff standards, Flutter code passes `flutter analyze`, and all React code is lint-free before submitting a pull request. Refer to `CONTRIBUTING.md` for detailed coding standards.

