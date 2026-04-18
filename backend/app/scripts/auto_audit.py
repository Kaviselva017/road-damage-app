# ruff: noqa: E402, E712, B904, E722
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from app.database import SessionLocal
from app.models.models import Complaint, FieldOfficer
from app.services.notification_service import send_email


def run_audit():
    print(f"[{datetime.now()}] Starting automated audit...")
    db = SessionLocal()

    try:
        # 1. Detect Stale Complaints (Pending/Assigned for > 48 hours)
        threshold = datetime.now(timezone.utc) - timedelta(hours=48)
        stale = db.query(Complaint).filter(Complaint.status.in_(["pending", "assigned"]), Complaint.created_at <= threshold).all()

        if stale:
            print(f"Found {len(stale)} stale complaints.")
            # Notify Admin
            admin = db.query(FieldOfficer).filter(FieldOfficer.is_admin).first()
            if admin:
                subject = f"Audit Alert: {len(stale)} Complaints require attention"
                body = "<h2>Audit Report</h2><p>The following complaints have been pending/assigned for more than 48 hours without progress:</p><ul>"
                for c in stale:
                    body += f"<li><strong>{c.complaint_id}</strong> - Reported: {c.created_at.strftime('%Y-%m-%d')} - Severity: {c.severity.upper()}</li>"
                body += "</ul><br><p>Please check the admin portal for more details.</p>"

                # Check if notification service is ready
                success = send_email(admin.email, subject, body)
                if success:
                    print(f"Admin notified at {admin.email}")
        else:
            print("No stale complaints found.")

        # 2. Daily Summary for Admin
        # (Could be expanded to daily/weekly stats)

    except Exception as e:
        print(f"Audit failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    run_audit()
