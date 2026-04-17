import logging
from app.database import SessionLocal
from app.services import sla_service

logger = logging.getLogger(__name__)

def run_escalation_check():
    """Wrapper for the background scheduler."""
    logger.info("Starting hourly SLA escalation check...")
    db = SessionLocal()
    try:
        sla_service.check_and_escalate(db)
        logger.info("SLA escalation check completed.")
    except Exception as e:
        logger.error(f"SLA escalation task failed: {e}", exc_info=True)
    finally:
        db.close()
