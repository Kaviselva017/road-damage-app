git add backend/start.sh backend/app/dependencies.py backend/app/schemas/schemas.py
git commit -m "fix: add dependencies.py, schemas, run migrations on start"
git push origin main
```

**3 — Fix Render dashboard start command:**

Go to Render → your service → **Settings** → **Start Command** → change it to:
```
cd backend && bash start.sh
```

Click **Save** → it will auto-redeploy.

**4 — Watch logs for:**
```
==> Running Alembic migrations...
==> Migrations complete
==> Starting server on port 10000
Your service is live 🎉