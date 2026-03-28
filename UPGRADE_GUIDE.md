# Upgrade Guide

The old prototype assets (`citizen-web/`, `dashboard-v2/`, and the root-level HTML copies) are no longer part of the active application flow.

Use these maintained paths instead:

- `backend/app` for the FastAPI backend
- `backend/static` for the login, citizen, dashboard, and admin pages
- `dashboard/src` for the React dashboard source
- `backend/test_roadwatch.py` for the end-to-end integration test

For setup and startup commands, use the instructions in `README.md`.
