import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Complaint, Department, Notification, SLAConfig, User
from app.services import audit_service

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def calculate_deadline(db: Session, severity: str) -> datetime | None:
    """Calculate deadline based on SLA config."""
    config = db.execute(select(SLAConfig).filter(SLAConfig.severity == severity.lower())).scalars().first()
    if not config:
        # Default fallback
        return _now() + timedelta(days=3)
    return _now() + timedelta(hours=config.resolution_hours)


def get_department_for_damage(db: Session, damage_type: str, area_type: str) -> int | None:
    """Route damage to specific departments."""
    name = "Roads"  # Default
    dt = damage_type.lower()

    if "bridge" in dt:
        name = "Bridges"
    elif any(x in dt for x in ["utility", "pipe", "water", "cable"]):
        name = "Utilities"
    elif "emergency" in area_type.lower() or "hospital" in area_type.lower():
        name = "Emergency"

    dept = db.execute(select(Department).filter(Department.name == name)).scalars().first()
    return dept.id if dept else None


def check_and_escalate(db: Session):
    """Hourly task to escalate overdue complaints."""
    now = _now()
    overdue = (
        db.execute(
            select(Complaint).filter(
                Complaint.status.in_(["pending", "assigned", "in_progress"]),
                Complaint.sla_deadline < now,
                Complaint.escalation_level < 2,  # Max director level
            )
        )
        .scalars()
        .all()
    )

    if not overdue:
        return

    for c in overdue:
        # Check if it has been long enough since last escalation (or since deadline)
        # We can use escalation_after_hours from SLA config
        config = db.execute(select(SLAConfig).filter(SLAConfig.severity == (c.severity or "low"))).scalars().first()
        esc_hours = config.escalation_after_hours if config else 24

        last_mark = c.escalated_at or c.sla_deadline
        if now > (last_mark + timedelta(hours=esc_hours)):
            c.escalation_level += 1
            c.escalated_at = now

            level_name = "Supervisor" if c.escalation_level == 1 else "Director"
            logger.warning(f"Escalating {c.complaint_id} to {level_name} level.")

            # Log notification
            db.add(Notification(user_id=1, complaint_id=c.complaint_id, message=f"Urgent: SLA for {c.complaint_id} breached. Escalated to {level_name}.", type="escalation", created_at=now))

            # AUDIT: Escalation
            audit_service.log_event(db, "complaint", c.complaint_id, "escalated", actor_id=None, actor_role="system", old_value={"level": c.escalation_level - 1}, new_value={"level": c.escalation_level})

            # Notify citizen via Push
            if c.user_id:
                try:
                    user = db.execute(select(User).filter(User.id == c.user_id)).scalar_one_or_none()
                    if user and user.fcm_token:
                        # We use StatusUpdate since we have 'escalated' message in STATUS_MESSAGES
                        import asyncio

                        from app.services.fcm_service import send_push

                        asyncio.create_task(send_push(fcm_token=user.fcm_token, title="Escalation Update", body=f"Your report {c.complaint_id} has been escalated to {level_name} for priority resolution.", data={"complaint_id": c.complaint_id, "screen": "complaint_detail", "status": "escalated"}))
                except Exception as e:
                    logger.warning(f"FCM escalation failed: {e}")

            # TODO: Send real emails here using notification_service

    db.commit()
