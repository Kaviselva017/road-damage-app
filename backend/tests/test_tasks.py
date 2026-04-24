"""
backend/tests/test_tasks.py
==============================
pytest tests for Celery inference task (run with CELERY_TASK_ALWAYS_EAGER=True).

  test_inference_task    — mock AI + storage, assert DB updated to 'analyzed'
  test_task_retry        — mock AI to raise, assert complaint marked 'failed'
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# Force eager mode so tasks run synchronously in-process
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "True"
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")

# ── Test DB setup ─────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, event as sa_event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base

TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


# Reuse the geo stub registration from conftest
from tests.conftest import register_sqlite_geo_stubs

sa_event.listen(_engine, "connect", register_sqlite_geo_stubs)

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


def _make_test_image_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Inference task — mock AI, assert DB updated
# ─────────────────────────────────────────────────────────────────────────────


def test_inference_task(db):
    """run_inference should update the complaint status to 'analyzed'."""
    cid = "RD-CELERY-001"
    _create_complaint(db, cid)

    img_bytes = _make_test_image_bytes()
    img_hex = img_bytes.hex()

    # Create a mock DamageResult
    mock_result = MagicMock()
    mock_result.class_name = "pothole"
    mock_result.severity = "high"
    mock_result.confidence = 0.85
    mock_result.description = "Pothole detected with high confidence."

    with (
        patch("app.database.SessionLocal", return_value=db),
        patch("app.services.ai_service.analyze_image", return_value=mock_result),
        patch("app.services.ai_service.is_road_image", return_value=(True, 0.95)),
        patch("app.services.storage_service.upload_file", return_value="https://storage.example.com/test.jpg"),
        patch("app.services.fcm_service.send_status_update", return_value=None),
    ):
        from app.celery_app import celery_app

        celery_app.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
        )

        from app.tasks.inference_task import run_inference

        result = run_inference(
            complaint_id=cid,
            fpath_str="/tmp/fake.jpg",
            img_bytes_hex=img_hex,
            filename="test.jpg",
            content_type="image/jpeg",
            address="123 Main St",
            nearby_sensitive=None,
            user_id=1,
        )

    assert result is not None
    assert result["status"] == "analyzed"
    assert result["complaint_id"] == cid

    # Verify DB was updated
    from sqlalchemy import select
    from app.models.models import Complaint

    c = db.execute(
        select(Complaint).filter(Complaint.complaint_id == cid)
    ).scalars().first()
    assert c is not None
    assert c.status == "analyzed"
    assert c.damage_type == "pothole"
    assert c.severity == "high"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Task retry — mock AI to raise, verify failure is recorded
# ─────────────────────────────────────────────────────────────────────────────


def test_task_retry(db):
    """
    When AI inference raises, the task should mark the complaint as
    'failed' and record the error.
    """
    cid = "RD-RETRY-001"
    _create_complaint(db, cid)

    img_bytes = _make_test_image_bytes()
    img_hex = img_bytes.hex()

    with (
        patch("app.database.SessionLocal", return_value=db),
        patch(
            "app.services.ai_service.analyze_image",
            side_effect=RuntimeError("Transient AI failure"),
        ),
        patch("app.services.ai_service.is_road_image", return_value=(True, 0.9)),
        patch("app.services.storage_service.upload_file", return_value="url"),
        patch("app.services.fcm_service.send_status_update", return_value=None),
    ):
        from app.celery_app import celery_app

        celery_app.conf.update(
            task_always_eager=True,
            task_eager_propagates=False,
        )

        from app.tasks.inference_task import run_inference

        # In eager mode with propagates=False, the task catches the exception
        # internally and returns an error dict or re-raises.
        try:
            run_inference(
                complaint_id=cid,
                fpath_str="/tmp/fake.jpg",
                img_bytes_hex=img_hex,
                filename="test.jpg",
                content_type="image/jpeg",
                address="Test",
                nearby_sensitive=None,
                user_id=1,
            )
        except Exception:
            pass  # Expected in eager mode

    # Verify the complaint was marked as failed
    from sqlalchemy import select
    from app.models.models import Complaint

    c = db.execute(
        select(Complaint).filter(Complaint.complaint_id == cid)
    ).scalars().first()
    assert c is not None
    assert c.status == "failed", f"Expected 'failed', got '{c.status}'"
    assert "error" in (c.officer_notes or "").lower() or "System error" in (c.officer_notes or ""), \
        f"officer_notes should contain error info, got: {c.officer_notes}"
