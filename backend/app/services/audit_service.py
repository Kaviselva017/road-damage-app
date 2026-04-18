import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import AuditLog

logger = logging.getLogger(__name__)


def _hash_log(entity_id: str, action: str, old: dict | None, new: dict | None, created_at: str) -> str:
    """Computes SHA256 checksum for a log entry to prevent tampering."""
    payload = f"{entity_id}|{action}|{json.dumps(old, sort_keys=True)}|{json.dumps(new, sort_keys=True)}|{created_at}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_event(db: Session, entity_type: str, entity_id: str, action: str, actor_id: int | None = None, actor_role: str | None = None, old_value: dict | None = None, new_value: dict | None = None, request: Request | None = None):
    """
    Asynchronously write an audit log.
    Wrapped in try-except to ensure audit failures never crash the main application.
    """
    try:
        ip = None
        ua = None
        if request:
            # Handle Render/Proxy X-Forwarded-For
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else None
            ua = request.headers.get("User-Agent")

        created_at_dt = datetime.now(timezone.utc)
        created_at_str = created_at_dt.isoformat()

        checksum = _hash_log(entity_id, action, old_value, new_value, created_at_str)

        log = AuditLog(entity_type=entity_type, entity_id=str(entity_id), action=action, actor_id=actor_id, actor_role=actor_role, old_value=old_value, new_value=new_value, ip_address=ip, user_agent=ua, created_at=created_at_dt, checksum=checksum)
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"AUDIT CRITICAL: Failed to write audit log for {entity_type}/{entity_id} - {e}")
        db.rollback()


def verify_log_integrity(log: AuditLog) -> bool:
    """Recomputes hash and compares it against stored checksum."""
    try:
        if not log.created_at:
            return False
        # Match the precision/format used in _hash_log
        created_at_str = log.created_at.replace(tzinfo=timezone.utc).isoformat()
        expected = _hash_log(log.entity_id, log.action, log.old_value, log.new_value, created_at_str)
        return expected == log.checksum
    except Exception:
        return False


def export_complaint_history(db: Session, complaint_id: str) -> list[AuditLog]:
    """Retrieve full timeline for a complaint."""
    return db.execute(select(AuditLog).filter(AuditLog.entity_type == "complaint", AuditLog.entity_id == str(complaint_id)).order_by(AuditLog.created_at.asc())).scalars().all()
