from app.celery_app import celery_app

@celery_app.task(
    name="app.tasks.inference_task.run_inference",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_inference(
    self,
    complaint_id: str,
    fpath_str: str,
    img_bytes_hex: str,
    filename: str,
    content_type: str,
    address: str | None,
    nearby_sensitive: str | None,
    user_id: int,
) -> dict:
    """
    Celery task: run YOLOv8 inference + update complaint in DB.
    img_bytes passed as hex string (JSON-serializable).
    Returns dict with status and complaint_id.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    img_bytes = bytes.fromhex(img_bytes_hex)
    
    try:
        # Import here to avoid circular imports at module level
        from app.database import SessionLocal
        from app.services.ai_service import analyze_image
        from app.services.storage_service import upload_file
        from app.models.models import Complaint, User
        from app.services.fcm_service import send_status_update
        from sqlalchemy import select
        import asyncio
        from datetime import datetime, timezone
        from pathlib import Path
        import tempfile
        import os
        
        db = SessionLocal()
        try:
            c = db.execute(
                select(Complaint).where(Complaint.complaint_id == complaint_id)
            ).scalar_one_or_none()
            if not c:
                logger.error("Complaint %s not found", complaint_id)
                return {"status": "error", "complaint_id": complaint_id}
            
            # Save bytes to temp file for inference
            ext = Path(filename).suffix or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(img_bytes)
                fpath_str = tmp.name
            
            # Run road check
            from app.services.ai_service import is_road_image
            is_road, conf = is_road_image(fpath_str)
            if not is_road:
                c.status = "failed"
                c.officer_notes = f"AI: Not a valid road image (conf={conf:.2f})"
                db.commit()
                return {"status": "failed", "complaint_id": complaint_id}
            
            # Run inference
            ai = analyze_image(fpath_str)
            image_url = upload_file(img_bytes, filename, content_type)
            
            # Update complaint fields
            c.damage_type = ai.class_name
            c.detected_damage_type = ai.class_name
            c.ai_class = ai.class_name
            c.severity = ai.severity
            c.ai_severity = ai.severity
            c.ai_confidence = ai.confidence
            c.confidence_score = ai.confidence
            c.description = ai.description
            c.image_url = image_url
            c.analyzed_at = datetime.now(timezone.utc)
            c.status = "analyzed"
            db.commit()
            
            # FCM notification
            user = db.execute(
                select(User).where(User.id == user_id)
            ).scalar_one_or_none()
            if user and user.fcm_token:
                try:
                    loop2 = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop2)
                    loop2.run_until_complete(
                        send_status_update(user.fcm_token, complaint_id, "analyzed")
                    )
                    loop2.close()
                except Exception as fcm_err:
                    logger.warning("FCM failed: %s", fcm_err)
            
            logger.info("Inference complete for %s — %s (%.2f)",
                        complaint_id, ai.class_name, ai.confidence)
            return {"status": "analyzed", "complaint_id": complaint_id}
        
        except Exception as exc:
            logger.error("Inference task failed for %s: %s", complaint_id, exc,
                         exc_info=True)
            try:
                c = db.execute(
                    select(Complaint).where(Complaint.complaint_id == complaint_id)
                ).scalar_one_or_none()
                if c:
                    c.status = "failed"
                    c.officer_notes = f"System error: {type(exc).__name__}"
                    db.commit()
            except Exception:
                pass
            raise self.retry(exc=exc)
        
        finally:
            try:
                if os.path.exists(fpath_str):
                    os.unlink(fpath_str)
            except OSError:
                pass
            db.close()
    
    except Exception as exc:
        logger.error("Task setup failed: %s", exc, exc_info=True)
        return {"status": "error", "complaint_id": complaint_id}


@celery_app.task(name="app.tasks.inference_task.run_escalation")
def run_escalation() -> dict:
    """Hourly SLA escalation check."""
    from app.database import SessionLocal
    from app.services.sla_service import check_and_escalate
    db = SessionLocal()
    try:
        check_and_escalate(db)
        return {"status": "ok"}
    finally:
        db.close()
