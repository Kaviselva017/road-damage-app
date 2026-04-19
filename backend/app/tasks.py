"""
backend/app/tasks.py
======================
Celery task definitions for RoadWatch.

Broker: redis://redis:6379/0
Backend: redis://redis:6379/1

Key task:
  run_inference(complaint_id, image_path)
    - Loads AI model singleton
    - Updates DB on completion (damage_type, severity, etc.)
    - Broadcasts result via WebSocket ConnectionManager
    - On failure: marks complaint as inference_failed
    - Retries up to 2 times with 5s countdown
"""

from __future__ import annotations

import logging
import os
import traceback
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from celery import Celery

logger = logging.getLogger(__name__)

# ── Celery app ────────────────────────────────────────────────────────────────

BROKER_URL  = os.getenv("CELERY_BROKER_URL",  "redis://redis:6379/0")
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

celery_app = Celery(
    "roadwatch",
    broker=BROKER_URL,
    backend=BACKEND_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry settings
    task_default_retry_delay=5,
    task_default_max_retries=2,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_db_session():
    """Create a fresh SQLAlchemy session for the Celery worker context."""
    from app.database import SessionLocal  # local import avoids app startup issues
    return SessionLocal()


def _area(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("hospital", "school", "temple", "mosque", "church", "market")):
        return "sensitive"
    if any(k in t for k in ("highway", "national", "express")):
        return "highway"
    if any(k in t for k in ("commercial", "mall", "office")):
        return "commercial"
    return "residential"


def _priority(severity: str, dtype: str, area: str, nearby: str) -> float:
    s = {"critical": 40, "high": 30, "medium": 20, "low": 10}.get(severity, 15)
    d = {"pothole": 15, "alligator_crack": 12, "longitudinal_crack": 8, "transverse_crack": 8}.get(dtype, 10)
    a = {"sensitive": 20, "highway": 15, "commercial": 10, "residential": 5}.get(area, 5)
    n = 10 if any(k in nearby.lower() for k in ("school", "hospital")) else 0
    return float(s + d + a + n)


# ── Main inference task ───────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="roadwatch.run_inference",
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def run_inference(self, complaint_id: str, image_path: str,
                  image_bytes_hex: str | None = None,
                  filename: str = "image.jpg",
                  content_type: str = "image/jpeg",
                  address: str | None = None,
                  nearby_sensitive: str | None = None,
                  user_id: int | None = None) -> dict:
    """
    Celery task: run AI inference on a complaint image.

    Args:
        complaint_id: Unique complaint ID (e.g. "RD-20260419-A1B2C3")
        image_path: Path to the temporary image file on disk
        image_bytes_hex: Optional hex-encoded image bytes (fallback if path missing)
        filename: Original filename
        content_type: MIME type
        address: Street address
        nearby_sensitive: Nearby landmarks
        user_id: Submitting user's ID

    Returns:
        dict with inference results
    """
    db = _get_db_session()

    try:
        from sqlalchemy import select
        from app.models.models import Complaint, Notification, User
        from app.services import ai_service, priority_service, sla_service, storage_service

        logger.info("[CeleryTask] Starting inference for %s", complaint_id)

        c = db.execute(select(Complaint).filter(Complaint.complaint_id == complaint_id)).scalars().first()
        if not c:
            logger.error("[CeleryTask] Complaint %s not found in DB", complaint_id)
            return {"status": "error", "detail": "complaint_not_found"}

        # ── Load image bytes ──────────────────────────────────────────────────
        fpath = Path(image_path)
        if fpath.exists():
            img_bytes = fpath.read_bytes()
        elif image_bytes_hex:
            img_bytes = bytes.fromhex(image_bytes_hex)
        else:
            raise FileNotFoundError(f"Image not found at {image_path}")

        # ── AI Inference ──────────────────────────────────────────────────────
        inf_start = time.perf_counter()

        ai = ai_service.analyze_image(image_path)

        inf_duration = time.perf_counter() - inf_start
        logger.info("[CeleryTask] Inference for %s took %.2fs", complaint_id, inf_duration)

        # ── Upload to storage ─────────────────────────────────────────────────
        image_url = storage_service.upload_file(img_bytes, filename, content_type)

        # ── Low confidence → undetected ───────────────────────────────────────
        if ai["ai_confidence"] < 0.10:
            c.detected_damage_type = None
            c.confidence_score = None
            c.analyzed_at = _now()
            c.damage_type = "unknown"
            c.severity = "low"
            c.ai_confidence = 0.0
            c.description = "No clear road damage surpassed the confidence threshold."
            c.priority_score = 0.0
            c.image_url = image_url
            c.area_type = _area(nearby_sensitive or address or "")
            c.status = "undetected"
            db.commit()

            result = {"status": "undetected", "complaint_id": complaint_id}

        else:
            # ── Detected → full scoring ───────────────────────────────────────
            area = _area(nearby_sensitive or address or "")
            priority = _priority(ai["severity"], ai["damage_type"], area, nearby_sensitive or "")

            c.detected_damage_type = ai["damage_type"]
            c.confidence_score = ai["ai_confidence"]
            c.analyzed_at = _now()
            c.damage_type = ai["damage_type"]
            c.severity = ai["severity"]
            c.ai_confidence = ai["ai_confidence"]
            c.description = ai["description"]
            c.priority_score = priority
            c.image_url = image_url
            c.area_type = area

            # SLA
            c.department_id = sla_service.get_department_for_damage(db, ai["damage_type"], area)

            # Advanced priority
            try:
                p_res = priority_service.calculate_priority_score(
                    damage_type=ai["damage_type"],
                    severity=ai["severity"],
                    confidence=ai["ai_confidence"],
                    area_type=area,
                    nearby_sensitive=nearby_sensitive or "",
                    report_count=c.report_count or 1,
                    latitude=c.latitude,
                    longitude=c.longitude,
                    weather_risk=0.0,
                    db=db,
                )
                c.priority_score = p_res["score"]
                c.urgency_label = p_res["urgency_label"]
                c.priority_breakdown = p_res["factors"]
                c.sla_deadline = _now() + timedelta(hours=p_res["recommended_sla_hours"])
            except Exception as exc:
                logger.warning("[CeleryTask] Priority scoring fallback: %s", exc)

            c.status = "analyzed"
            db.commit()

            result = {
                "status": "analyzed",
                "complaint_id": complaint_id,
                "damage_type": ai["damage_type"],
                "severity": ai["severity"],
                "confidence": ai["ai_confidence"],
                "priority_score": c.priority_score,
            }

        # ── DB Notification ───────────────────────────────────────────────────
        if user_id:
            db.add(Notification(
                user_id=user_id,
                complaint_id=c.complaint_id,
                message=f"Complaint {c.complaint_id} processed. Status: {c.status}",
                type="submitted",
                created_at=_now(),
            ))
            user_record = db.execute(select(User).filter(User.id == user_id)).scalars().first()
            if user_record:
                user_record.reward_points = (user_record.reward_points or 0) + 10
            db.commit()

        # ── WebSocket broadcast ───────────────────────────────────────────────
        try:
            from app.api.ws import build_inference_payload, manager as user_ws_manager
            import asyncio

            payload = build_inference_payload(
                complaint_id=c.complaint_id,
                damage_type=c.detected_damage_type or c.damage_type or "unknown",
                confidence=round(c.confidence_score or c.ai_confidence or 0.0, 4),
                severity=c.severity or "medium",
            )
            # Celery workers run in sync context — use asyncio.run for the async send
            if user_id:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(user_ws_manager.send(str(user_id), payload))
                    else:
                        asyncio.run(user_ws_manager.send(str(user_id), payload))
                except RuntimeError:
                    asyncio.run(user_ws_manager.send(str(user_id), payload))
        except Exception as ws_exc:
            logger.debug("[CeleryTask] WS broadcast skipped: %s", ws_exc)

        logger.info("[CeleryTask] ✓ Inference complete for %s → %s", complaint_id, c.status)
        return result

    except Exception as exc:
        logger.error(
            "[CeleryTask] Inference FAILED for %s: %s\n%s",
            complaint_id, exc, traceback.format_exc(),
        )

        # ── Mark as inference_failed ──────────────────────────────────────────
        try:
            from sqlalchemy import select
            from app.models.models import Complaint

            c = db.execute(select(Complaint).filter(Complaint.complaint_id == complaint_id)).scalars().first()
            if c:
                c.status = "inference_failed"
                c.officer_notes = f"Celery task error: {type(exc).__name__}: {exc}"
                db.commit()
        except Exception as db_exc:
            logger.error("[CeleryTask] DB update after failure also failed: %s", db_exc)

        # ── Retry ─────────────────────────────────────────────────────────────
        try:
            raise self.retry(exc=exc, countdown=5, max_retries=2)
        except self.MaxRetriesExceededError:
            logger.error("[CeleryTask] Max retries exceeded for %s", complaint_id)
            return {"status": "failed", "complaint_id": complaint_id, "error": str(exc)}

    finally:
        # ── Cleanup temp file ─────────────────────────────────────────────────
        try:
            fpath = Path(image_path)
            if fpath.exists():
                fpath.unlink()
        except Exception:
            pass
        db.close()


# ── Optional: periodic beat schedule ──────────────────────────────────────────

celery_app.conf.beat_schedule = {
    "escalation-check-every-10m": {
        "task": "roadwatch.check_escalations",
        "schedule": 600.0,  # 10 minutes
    },
}


@celery_app.task(name="roadwatch.check_escalations")
def check_escalations():
    """Periodic task to check SLA deadlines and escalate overdue complaints."""
    db = _get_db_session()
    try:
        from app.services.sla_service import run_escalation_check
        run_escalation_check(db)
        logger.info("[CeleryBeat] Escalation check complete")
    except Exception as exc:
        logger.error("[CeleryBeat] Escalation check failed: %s", exc)
    finally:
        db.close()
