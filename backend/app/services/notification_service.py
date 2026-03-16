"""
Emergency Notification Service
- AI detects HIGH severity → email admin immediately
- Admin assigns officer from dashboard
- Officer gets email when assigned
- Citizen gets email at every status change
"""
import os, smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "kaviselvakumar2005@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "uxkigeywrqirdcwv")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", SMTP_USER)  # Admin receives emergency alerts

def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(EMAIL_FROM, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"Email failed: {e}")
        return False

def _sev_color(sev): 
    return {"high":"#ef4444","medium":"#f59e0b","low":"#10b981"}.get(str(sev).lower(),"#6b7280")

def _sev_icon(sev):
    return {"high":"🔴","medium":"🟡","low":"🟢"}.get(str(sev).lower(),"⚪")

# ── 1. CITIZEN SUBMITS → ADMIN gets emergency alert if HIGH ──
def notify_admin_emergency(complaint, citizen_name: str):
    """Send emergency alert to admin when HIGH severity complaint is submitted."""
    sev = str(complaint.severity.value if hasattr(complaint.severity,'value') else complaint.severity)
    dmg = str(complaint.damage_type.value if hasattr(complaint.damage_type,'value') else complaint.damage_type)
    priority = getattr(complaint, 'priority_score', 0) or 0
    area = getattr(complaint, 'area_type', 'unknown') or 'unknown'
    address = complaint.address or f"{complaint.latitude:.4f}, {complaint.longitude:.4f}"
    
    if sev != "high":
        return  # Only emergency for HIGH severity
    
    subject = f"🚨 EMERGENCY ALERT — HIGH Severity Road Damage | {complaint.complaint_id}"
    
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto">
      
      <!-- Emergency Banner -->
      <div style="background:#ef4444;padding:20px 24px;border-radius:12px 12px 0 0">
        <h1 style="margin:0;color:#fff;font-size:24px">🚨 EMERGENCY ROAD DAMAGE ALERT</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,0.9);font-size:14px">
          Immediate action required — HIGH severity damage reported
        </p>
      </div>

      <!-- Body -->
      <div style="background:#0f172a;padding:24px;border:1px solid #1e293b">
        
        <!-- Alert Box -->
        <div style="background:#7f1d1d;border:1px solid #ef4444;border-radius:8px;padding:14px;margin-bottom:20px">
          <p style="margin:0;color:#fca5a5;font-size:14px;font-weight:700">
            ⚠ AI has detected a HIGH severity road damage. A field officer must be assigned immediately.
          </p>
        </div>

        <!-- Details Table -->
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px;width:160px">Complaint ID</td>
            <td style="padding:10px 0;font-weight:700;color:#f59e0b;font-size:15px">{complaint.complaint_id}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Reported By</td>
            <td style="padding:10px 0;color:#e2e8f0">{citizen_name}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Damage Type</td>
            <td style="padding:10px 0;color:#e2e8f0;text-transform:capitalize">{dmg.replace('_',' ')}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Severity</td>
            <td style="padding:10px 0">
              <span style="background:#ef444422;color:#ef4444;padding:4px 12px;border-radius:20px;font-weight:700;font-size:13px">
                🔴 HIGH — IMMEDIATE ACTION REQUIRED
              </span>
            </td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Priority Score</td>
            <td style="padding:10px 0;font-weight:700;color:#ef4444;font-size:16px">{priority}/100</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Area Type</td>
            <td style="padding:10px 0;color:#f59e0b;font-weight:700;text-transform:uppercase">{area}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Location</td>
            <td style="padding:10px 0;color:#e2e8f0">{address}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">GPS Coordinates</td>
            <td style="padding:10px 0;color:#60a5fa">{complaint.latitude:.5f}, {complaint.longitude:.5f}</td>
          </tr>
          <tr>
            <td style="padding:10px 0;color:#64748b;font-size:13px">Reported At</td>
            <td style="padding:10px 0;color:#e2e8f0">{datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}</td>
          </tr>
        </table>

        <!-- AI Description -->
        <div style="background:#1e293b;border-left:4px solid #ef4444;border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:20px">
          <p style="margin:0 0 4px;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:0.05em">AI Detection Result</p>
          <p style="margin:0;color:#e2e8f0;font-size:14px">{getattr(complaint,'description','Road damage detected.')}</p>
        </div>

        <!-- Action Buttons -->
        <div style="text-align:center;margin-bottom:20px">
          <a href="http://localhost:8000/admin" 
             style="display:inline-block;background:#ef4444;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;margin-right:10px">
            🛡 Open Admin Panel → Assign Officer
          </a>
        </div>
        <div style="text-align:center">
          <a href="https://maps.google.com/maps?q={complaint.latitude},{complaint.longitude}" 
             style="display:inline-block;background:#1e293b;color:#60a5fa;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:13px">
            📍 View on Google Maps
          </a>
        </div>

        <!-- Footer -->
        <div style="margin-top:24px;padding-top:16px;border-top:1px solid #1e293b;text-align:center">
          <p style="margin:0;color:#475569;font-size:12px">
            RoadWatch Admin Alert System · {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}
          </p>
        </div>
      </div>
    </div>"""
    
    _send_email(ADMIN_EMAIL, subject, html)
    logger.info(f"Emergency alert sent to admin for {complaint.complaint_id}")

# ── 2. ADMIN ASSIGNS OFFICER → OFFICER gets email ────────────
def notify_officer_assigned(officer, complaint):
    """Email officer when admin assigns them to a complaint."""
    sev = str(complaint.severity.value if hasattr(complaint.severity,'value') else complaint.severity)
    dmg = str(complaint.damage_type.value if hasattr(complaint.damage_type,'value') else complaint.damage_type)
    color = _sev_color(sev)
    icon = _sev_icon(sev)
    priority = getattr(complaint, 'priority_score', 0) or 0
    area = getattr(complaint, 'area_type', 'unknown') or 'unknown'
    address = complaint.address or f"{complaint.latitude:.4f}, {complaint.longitude:.4f}"
    
    is_emergency = sev == "high"
    subject = f"{'🚨 URGENT: ' if is_emergency else ''}New Complaint Assigned — {complaint.complaint_id}"
    
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto">
      <div style="background:{color};padding:20px 24px;border-radius:12px 12px 0 0">
        <h1 style="margin:0;color:#fff;font-size:22px">{icon} Complaint Assigned to You</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,0.9);font-size:14px">
          Officer {officer.name} — RoadWatch Field Assignment
        </p>
      </div>
      <div style="background:#0f172a;padding:24px;border:1px solid #1e293b">
        {'<div style="background:#7f1d1d;border:1px solid #ef4444;border-radius:8px;padding:12px;margin-bottom:16px"><p style="margin:0;color:#fca5a5;font-size:13px">⚠ HIGH SEVERITY — Please inspect and repair immediately.</p></div>' if is_emergency else ''}
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px;width:150px">Complaint ID</td>
            <td style="padding:10px 0;font-weight:700;color:#f59e0b">{complaint.complaint_id}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Damage Type</td>
            <td style="padding:10px 0;color:#e2e8f0;text-transform:capitalize">{dmg.replace('_',' ')}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Severity</td>
            <td style="padding:10px 0">
              <span style="background:{color}22;color:{color};padding:3px 10px;border-radius:20px;font-weight:700">{icon} {sev.upper()}</span>
            </td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Priority Score</td>
            <td style="padding:10px 0;font-weight:700;color:{color}">{priority}/100</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Area</td>
            <td style="padding:10px 0;color:#f59e0b;font-weight:700;text-transform:uppercase">{area}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Location</td>
            <td style="padding:10px 0;color:#e2e8f0">{address}</td>
          </tr>
          <tr>
            <td style="padding:10px 0;color:#64748b;font-size:13px">GPS</td>
            <td style="padding:10px 0;color:#60a5fa">{complaint.latitude:.5f}, {complaint.longitude:.5f}</td>
          </tr>
        </table>
        <div style="background:#1e293b;border-left:4px solid {color};border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:20px">
          <p style="margin:0;color:#e2e8f0;font-size:14px">{getattr(complaint,'description','Road damage detected.')}</p>
        </div>
        <div style="text-align:center;margin-bottom:12px">
          <a href="http://localhost:8000/static/dashboard.html"
             style="display:inline-block;background:{color};color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px">
            Open Officer Dashboard →
          </a>
        </div>
        <div style="text-align:center">
          <a href="https://maps.google.com/maps?q={complaint.latitude},{complaint.longitude}"
             style="display:inline-block;background:#1e293b;color:#60a5fa;padding:10px 24px;border-radius:8px;text-decoration:none;font-size:13px">
            📍 Navigate to Location
          </a>
        </div>
      </div>
    </div>"""
    
    _send_email(officer.email, subject, html)

# ── 3. STATUS CHANGES → CITIZEN gets email ───────────────────
def notify_citizen_status(citizen_email: str, citizen_name: str,
                           complaint_id: str, new_status: str,
                           address: str = "", officer_name: str = ""):
    """Email citizen when complaint status changes."""
    status_info = {
        "assigned":    ("👮 Officer Assigned", "#3b82f6", "A field officer has been assigned to your complaint and will inspect it soon."),
        "in_progress": ("🔧 Repair In Progress", "#f59e0b", "Road repair work has started at your reported location."),
        "completed":   ("✅ Repair Completed!", "#10b981", "The road damage has been repaired. Thank you for helping improve your community!"),
        "rejected":    ("❌ Report Rejected", "#ef4444", "Your complaint could not be processed. Please re-submit with a clearer photo and accurate location."),
    }
    title, color, msg = status_info.get(new_status, ("📋 Status Updated", "#6b7280", f"Your complaint status has been updated to: {new_status}"))
    subject = f"{title} — {complaint_id}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto">
      <div style="background:{color};padding:20px 24px;border-radius:12px 12px 0 0">
        <h1 style="margin:0;color:#fff;font-size:22px">{title}</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,0.9);font-size:14px">RoadWatch — Complaint Update for {citizen_name}</p>
      </div>
      <div style="background:#0f172a;padding:24px;border:1px solid #1e293b">
        <p style="color:#e2e8f0;font-size:15px">Hi <strong>{citizen_name}</strong>,</p>
        <p style="color:#94a3b8;font-size:14px;margin-bottom:20px">{msg}</p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px;width:150px">Complaint ID</td>
            <td style="padding:10px 0;font-weight:700;color:#f59e0b">{complaint_id}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">New Status</td>
            <td style="padding:10px 0">
              <span style="background:{color}22;color:{color};padding:4px 12px;border-radius:20px;font-weight:700">{new_status.replace('_',' ').upper()}</span>
            </td>
          </tr>
          {'<tr style="border-bottom:1px solid #1e293b"><td style="padding:10px 0;color:#64748b;font-size:13px">Assigned Officer</td><td style="padding:10px 0;color:#e2e8f0">'+officer_name+'</td></tr>' if officer_name else ''}
          {'<tr style="border-bottom:1px solid #1e293b"><td style="padding:10px 0;color:#64748b;font-size:13px">Location</td><td style="padding:10px 0;color:#e2e8f0">'+address+'</td></tr>' if address else ''}
          <tr>
            <td style="padding:10px 0;color:#64748b;font-size:13px">Updated At</td>
            <td style="padding:10px 0;color:#e2e8f0">{datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}</td>
          </tr>
        </table>
        <div style="text-align:center;margin-bottom:12px">
          <a href="http://localhost:8000/citizen"
             style="display:inline-block;background:{color};color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px">
            Track Your Complaint →
          </a>
        </div>
        <div style="margin-top:20px;padding-top:16px;border-top:1px solid #1e293b;text-align:center">
          <p style="margin:0;color:#475569;font-size:12px">RoadWatch Citizen Portal · Thank you for making roads safer</p>
        </div>
      </div>
    </div>"""
    _send_email(citizen_email, subject, html)

# ── 4. CITIZEN SUBMITS → confirmation email ──────────────────
def notify_citizen_submitted(citizen_email: str, citizen_name: str,
                              complaint_id: str, severity: str,
                              address: str = "", priority: float = 0):
    color = _sev_color(severity)
    icon = _sev_icon(severity)
    subject = f"✅ Complaint Registered — {complaint_id}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto">
      <div style="background:#10b981;padding:20px 24px;border-radius:12px 12px 0 0">
        <h1 style="margin:0;color:#fff;font-size:22px">✅ Complaint Registered</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,0.9);font-size:14px">RoadWatch — Thank you for reporting road damage</p>
      </div>
      <div style="background:#0f172a;padding:24px;border:1px solid #1e293b">
        <p style="color:#e2e8f0;font-size:15px">Hi <strong>{citizen_name}</strong>,</p>
        <p style="color:#94a3b8;font-size:14px;margin-bottom:20px">
          Your road damage report has been successfully registered. Our AI has analyzed the image and a field officer will be assigned shortly.
        </p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px;width:150px">Complaint ID</td>
            <td style="padding:10px 0;font-weight:700;color:#f59e0b;font-size:15px">{complaint_id}</td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Severity</td>
            <td style="padding:10px 0">
              <span style="background:{color}22;color:{color};padding:4px 12px;border-radius:20px;font-weight:700">{icon} {severity.upper()}</span>
            </td>
          </tr>
          <tr style="border-bottom:1px solid #1e293b">
            <td style="padding:10px 0;color:#64748b;font-size:13px">Priority Score</td>
            <td style="padding:10px 0;font-weight:700;color:{'#ef4444' if priority>=70 else '#f59e0b' if priority>=40 else '#10b981'}">{priority}/100</td>
          </tr>
          {'<tr style="border-bottom:1px solid #1e293b"><td style="padding:10px 0;color:#64748b;font-size:13px">Location</td><td style="padding:10px 0;color:#e2e8f0">'+address+'</td></tr>' if address else ''}
          <tr>
            <td style="padding:10px 0;color:#64748b;font-size:13px">Submitted At</td>
            <td style="padding:10px 0;color:#e2e8f0">{datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}</td>
          </tr>
        </table>
        <div style="background:#1e293b;border-radius:8px;padding:14px;margin-bottom:20px">
          <p style="margin:0;color:#94a3b8;font-size:13px;margin-bottom:8px">📋 What happens next?</p>
          <p style="margin:0;color:#e2e8f0;font-size:13px">1. Field officer will be assigned within 24 hours</p>
          <p style="margin:0;color:#e2e8f0;font-size:13px">2. You will receive updates at each stage</p>
          <p style="margin:0;color:#e2e8f0;font-size:13px">3. Track progress anytime in the citizen portal</p>
        </div>
        <div style="text-align:center">
          <a href="http://localhost:8000/citizen"
             style="display:inline-block;background:#f5a623;color:#000;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px">
            Track Your Complaint →
          </a>
        </div>
      </div>
    </div>"""
    _send_email(citizen_email, subject, html)

# Legacy compatibility
def notify_officer(officer, complaint):
    notify_officer_assigned(officer, complaint)
