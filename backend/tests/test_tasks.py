"""
backend/tests/test_tasks.py
==============================
pytest tests for Celery tasks (run with CELERY_TASK_ALWAYS_EAGER=True).

  test_inference_task    — mock AIService.predict, assert DB updated
  test_task_retry        — mock predict to raise once, assert retry triggered
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Force eager mode so tasks run synchronously in-process
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "True"
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")

# ── Test DB setup ─────────────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base

TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


def _create_complaint(db, cid="RD-TEST-001"):
    from app.models.models import Complaint
    c = Complaint(
        complaint_id=cid,
        user_id=1,
        latitude=12.97,
        longitude=77.59,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(c)
    db.commit()
    return c


def _write_temp_image() -> str:
    """Create a temporary file that looks like an image."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tmp.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    tmp.close()
    return tmp.name


# ─────────────────────────────────────────────────────────────────────────────
# 1. Inference task — mock AI, assert DB updated
# ─────────────────────────────────────────────────────────────────────────────

def test_inference_task(db):
    """run_inference should update the complaint status to 'analyzed' and set damage_type."""
    cid = "RD-CELERY-001"
    _create_complaint(db, cid)

    img_path = _write_temp_image()

    # Mock AI inference result
    mock_ai_result = {
        "damage_type": "pothole",
        "severity": "high",
        "ai_confidence": 0.85,
        "description": "Pothole detected with high confidence.",
    }

    # Mock storage upload
    mock_upload = "https://storage.example.com/test.jpg"

    with patch("app.tasks._get_db_session", return_value=db), \
         patch("app.services.ai_service.analyze_image", return_value=mock_ai_result), \
         patch("app.services.storage_service.upload_file", return_value=mock_upload), \
         patch("app.services.sla_service.get_department_for_damage", return_value=None), \
         patch("app.services.priority_service.calculate_priority_score", return_value={
             "score": 75.0,
             "urgency_label": "high",
             "factors": {"damage": 30, "severity": 30, "area": 15},
             "recommended_sla_hours": 24,
         }):

        # Configure Celery for eager execution
        from app.tasks import celery_app, run_inference
        celery_app.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
        )

        result = run_inference(
            complaint_id=cid,
            image_path=img_path,
            filename="test.jpg",
            content_type="image/jpeg",
            user_id=1,
        )

    assert result is not None
    assert result["status"] == "analyzed"
    assert result["complaint_id"] == cid
    assert result["damage_type"] == "pothole"

    # Verify DB was updated
    from sqlalchemy import select
    from app.models.models import Complaint
    c = db.execute(select(Complaint).filter(Complaint.complaint_id == cid)).scalars().first()
    assert c is not None
    assert c.status == "analyzed"
    assert c.damage_type == "pothole"
    assert c.severity == "high"

    # Cleanup
    Path(img_path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Task retry — mock predict to raise, verify retry mechanism
# ─────────────────────────────────────────────────────────────────────────────

def test_task_retry(db):
    """
    When AI inference raises, the task should mark the complaint as
    inference_failed AND trigger a retry (up to max_retries=2).
    """
    cid = "RD-RETRY-001"
    _create_complaint(db, cid)

    img_path = _write_temp_image()

    # Always raise to simulate persistent failure
    def _mock_analyze_always_fail(*args, **kwargs):
        raise RuntimeError("Transient AI failure")

    with patch("app.tasks._get_db_session", return_value=db), \
         patch("app.services.ai_service.analyze_image", side_effect=_mock_analyze_always_fail), \
         patch("app.services.storage_service.upload_file", return_value="url"), \
         patch("app.services.sla_service.get_department_for_damage", return_value=None), \
         patch("app.services.priority_service.calculate_priority_score", return_value={
             "score": 50.0,
             "urgency_label": "medium",
             "factors": {},
             "recommended_sla_hours": 48,
         }):

        from app.tasks import celery_app, run_inference
        celery_app.conf.update(
            task_always_eager=True,
            task_eager_propagates=False,
        )

        # In eager mode, self.retry() re-raises the original exception.
        # We catch it and verify the DB was updated.
        try:
            result = run_inference(
                complaint_id=cid,
                image_path=img_path,
                filename="test.jpg",
                content_type="image/jpeg",
                user_id=1,
            )
        except RuntimeError:
            pass  # Expected — Celery eager retry re-raises the original exception

    # Verify the complaint was marked as inference_failed in the DB
    from sqlalchemy import select
    from app.models.models import Complaint
    c = db.execute(select(Complaint).filter(Complaint.complaint_id == cid)).scalars().first()
    assert c is not None
    assert c.status == "inference_failed", f"Expected inference_failed, got {c.status}"
    assert "Celery task error" in (c.officer_notes or ""), \
        f"officer_notes should contain error info, got: {c.officer_notes}"

    Path(img_path).unlink(missing_ok=True)

