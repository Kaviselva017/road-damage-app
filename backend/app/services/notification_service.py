"""
RoadWatch — Notification Service
Primary:  Gmail SMTP (add SMTP_USER + SMTP_PASS to Render env)
Fallback: Resend API (add RESEND_API_KEY to Render env)

If neither is configured, emails are silently skipped — the app still works.
"""
import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

SMTP_SERVER    = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER      = os.getenv("SMTP_USER", "")
SMTP_PASS      = os.getenv("SMTP_PASS", "")
EMAIL_FROM     = os.getenv("EMAIL_FROM", SMTP_USER)
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL", SMTP_USER)
BASE_URL       = os.getenv("BASE_URL", "https://road-damage-appsystem.onrender.com")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# Log config at startup
if SMTP_USER and SMTP_PASS:
    logger.info(f"[Email] Gmail SMTP ready: {SMTP_USER}")
elif RESEND_API_KEY:
    logger.info(f"[Email] Resend API ready: from={EMAIL_FROM}")
else:
    logger.warning("[Email] No email provider configured — emails disabled. "
                   "Add SMTP_USER + SMTP_PASS to Render env vars.")


# ── Send engines ───────────────────────────────────────────────

def _smtp(to: str, subject: str, html: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"RoadWatch <{EMAIL_FROM}>"
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as s:
            s.ehlo(); s.starttls(); s.ehlo()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(EMAIL_FROM, [to], msg.as_string())
        logger.info(f"[Email SMTP] ✅ '{subject}' → {to}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("[Email SMTP] ❌ Auth failed. SMTP_PASS must be a Gmail App Password "
                     "(16 chars, no spaces). Get one at: myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        logger.error(f"[Email SMTP] ❌ {type(e).__name__}: {e}")
        return False


def _resend(to: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        return False
    try:
        payload = json.dumps({"from": EMAIL_FROM, "to": [to],
                              "subject": subject, "html": html}).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails", data=payload,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                     "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        logger.info(f"[Email Resend] ✅ '{subject}' → {to} id={resp.get('id')}")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"[Email Resend] ❌ HTTP {e.code}: {body}")
        if e.code == 422:
            logger.error("[Email Resend] ⚠ 422 = domain not verified. "
                         "Use Gmail SMTP instead: add SMTP_USER + SMTP_PASS.")
        return False
    except Exception as e:
        logger.error(f"[Email Resend] ❌ {e}")
        return False


def send_email(to: str, subject: str, html: str) -> bool:
    if not to or "@" not in to:
        return False
    # Gmail first (most reliable on Render)
    if SMTP_USER and SMTP_PASS:
        if _smtp(to, subject, html):
            return True
        logger.warning("[Email] SMTP failed, trying Resend...")
    if RESEND_API_KEY:
        return _resend(to, subject, html)
    logger.info(f"[Email] No provider — '{subject}' to {to} skipped")
    return False


# ── Templates ──────────────────────────────────────────────────

def _row(label: str, value: str, color: str = "#e8eaf0") -> str:
    return (f'<div style="display:flex;justify-content:space-between;padding:7px 0;'
            f'border-bottom:1px solid #1e2535">'
            f'<span style="color:#6b7694;font-size:13px">{label}</span>'
            f'<span style="color:{color};font-size:13px;font-weight:600">{value}</span>'
            f'</div>')


def _base(title: str, body: str, cta_url: str = "", cta_text: str = "") -> str:
    cta = (f'<div style="text-align:center;margin:24px 0">'
           f'<a href="{cta_url}" style="background:#f5a623;color:#000;padding:11px 26px;'
           f'border-radius:8px;text-decoration:none;font-weight:700;font-size:14px;'
           f'display:inline-block">{cta_text}</a></div>') if cta_url else ""
    return (f'<!DOCTYPE html><html><head><meta charset="UTF-8"/></head>'
            f'<body style="margin:0;padding:0;background:#0a0c10;font-family:Arial,sans-serif">'
            f'<div style="max-width:540px;margin:32px auto;background:#12151c;'
            f'border-radius:14px;border:1px solid #232a38;overflow:hidden">'
            f'<div style="background:#0d1117;padding:20px 28px;border-bottom:1px solid #232a38">'
            f'<div style="font-size:19px;font-weight:900;color:#f5a623">🛣 RoadWatch</div>'
            f'<div style="font-size:11px;color:#6b7694;margin-top:2px">AI Road Damage Reporting</div>'
            f'</div>'
            f'<div style="padding:24px 28px;color:#e8eaf0">'
            f'<h2 style="margin:0 0 16px;font-size:17px;color:#f5a623">{title}</h2>'
            f'{body}{cta}'
            f'</div>'
            f'<div style="padding:12px 28px;border-top:1px solid #232a38;font-size:11px;'
            f'color:#4a5568;text-align:center">{BASE_URL}</div>'
            f'</div></body></html>')


def _sev_color(sev: str) -> str:
    return {"high": "#e05c5c", "medium": "#f5a623", "low": "#3ecfb2"}.get(sev.lower(), "#f5a623")


# ── Public functions ───────────────────────────────────────────

def notify_welcome(to_email: str, citizen_name: str) -> bool:
    body = (f'<p style="color:#9ca3af;margin:0 0 16px">Hi <strong style="color:#e8eaf0">'
            f'{citizen_name}</strong>,<br><br>Welcome to RoadWatch! You can now report road '
            f'damage and track repairs in real time.</p>'
            f'<div style="background:#0d1117;border-radius:8px;padding:14px;border:1px solid #232a38">'
            f'{_row("Account", to_email)}{_row("Status", "Active", "#3ecfb2")}'
            f'{_row("Reward Points", "0 pts (earn 10 per report!)", "#f5a623")}</div>')
    return send_email(to_email, "Welcome to RoadWatch!", _base(
        "Account Created!", body, f"{BASE_URL}/citizen", "Start Reporting"))


def notify_complaint_submitted(
    to_email: str, citizen_name: str, complaint_id: str,
    damage_type: str, severity: str,
    priority_score: float = 0.0, area_type: str = "residential",
) -> bool:
    sc   = _sev_color(severity)
    body = (f'<p style="color:#9ca3af;margin:0 0 16px">Hi <strong style="color:#e8eaf0">'
            f'{citizen_name}</strong>,<br>Your complaint has been '
            f'<strong style="color:#3ecfb2">registered and assigned</strong> to a field officer.</p>'
            f'<div style="background:#0d1117;border-radius:8px;padding:14px;border:1px solid #232a38">'
            f'{_row("Complaint ID", complaint_id, "#f5a623")}'
            f'{_row("Damage Type", damage_type.replace("_"," ").title())}'
            f'{_row("Severity", severity.upper(), sc)}'
            f'{_row("Area", area_type.replace("_"," ").title())}'
            f'{_row("Priority Score", f"P{priority_score:.0f}")}'
            f'{_row("Status", "Assigned to Officer", "#3ecfb2")}</div>'
            f'<p style="color:#6b7694;font-size:12px;margin:12px 0 0">'
            f'Track progress in the RoadWatch Citizen Portal.</p>')
    return send_email(to_email, f"Complaint {complaint_id} Received - RoadWatch",
                      _base("Complaint Registered!", body,
                            f"{BASE_URL}/citizen", "Track My Complaint"))


def notify_status_update(
    to_email: str, citizen_name: str, complaint_id: str,
    new_status: str, officer_notes: str = "", officer_name: str = "",
) -> bool:
    labels = {
        "assigned":    ("Officer Assigned",   "#f5a623", "A field officer has been assigned."),
        "in_progress": ("Repair In Progress", "#3b82f6", "Repair work has started."),
        "completed":   ("Repair Completed!",  "#3ecfb2", "The road damage has been repaired!"),
        "rejected":    ("Complaint Closed",   "#e05c5c", "Your complaint has been reviewed and closed."),
    }
    label, color, msg = labels.get(
        new_status, (new_status.replace("_"," ").title(), "#f5a623", "Status updated."))
    notes_html = ""
    if officer_notes:
        by = f" — {officer_name}" if officer_name else ""
        notes_html = (f'<div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.3);'
                      f'border-radius:8px;padding:10px;margin:12px 0">'
                      f'<div style="font-size:11px;color:#60a5fa;font-weight:700;margin-bottom:4px">'
                      f'Officer Notes{by}</div>'
                      f'<div style="font-size:13px">{officer_notes}</div></div>')
    body = (f'<p style="color:#9ca3af;margin:0 0 14px">Hi <strong style="color:#e8eaf0">'
            f'{citizen_name}</strong>,</p>'
            f'<div style="text-align:center;margin:16px 0">'
            f'<span style="border:2px solid {color};color:{color};padding:8px 18px;'
            f'border-radius:8px;font-size:15px;font-weight:700;display:inline-block">'
            f'{label}</span></div>'
            f'<div style="background:#0d1117;border-radius:8px;padding:14px;border:1px solid #232a38">'
            f'{_row("Complaint ID", complaint_id, "#f5a623")}'
            f'{_row("Status", label, color)}</div>'
            f'{notes_html}'
            f'<p style="color:#9ca3af;font-size:13px;margin:10px 0 0">{msg}</p>')
    return send_email(to_email, f"RoadWatch Update: {complaint_id} - {label}",
                      _base("Status Updated", body, f"{BASE_URL}/citizen", "View Complaint"))


def notify_fund_allocated(
    to_email: str, citizen_name: str, complaint_id: str,
    amount: float, note: str = "",
) -> bool:
    note_html = (f'<p style="color:#9ca3af;font-size:13px;margin:10px 0 0">{note}</p>') if note else ""
    body = (f'<p style="color:#9ca3af;margin:0 0 14px">Hi <strong style="color:#e8eaf0">'
            f'{citizen_name}</strong>,<br>Budget has been allocated for your complaint.</p>'
            f'<div style="background:#0d1117;border-radius:8px;padding:14px;border:1px solid #232a38">'
            f'{_row("Complaint ID", complaint_id, "#f5a623")}'
            f'{_row("Amount Allocated", f"Rs. {amount:,.0f}", "#3ecfb2")}</div>{note_html}')
    return send_email(to_email, f"RoadWatch: Budget Allocated for {complaint_id}",
                      _base("Budget Allocated 💰", body, f"{BASE_URL}/citizen", "Track Progress"))


def notify_admin_emergency(
    complaint_id: str, severity: str, damage_type: str,
    address: str, priority_score: float, latitude: float, longitude: float,
) -> bool:
    if not ADMIN_EMAIL:
        return False
    maps = f"https://maps.google.com/?q={latitude},{longitude}"
    body = (f'<div style="background:rgba(224,92,92,0.12);border:1px solid #e05c5c;'
            f'border-radius:8px;padding:12px;margin-bottom:14px">'
            f'<div style="color:#e05c5c;font-weight:700">HIGH SEVERITY COMPLAINT REPORTED</div></div>'
            f'<div style="background:#0d1117;border-radius:8px;padding:14px;border:1px solid #232a38">'
            f'{_row("Complaint ID", complaint_id, "#f5a623")}'
            f'{_row("Damage Type", damage_type.replace("_"," ").title())}'
            f'{_row("Severity", severity.upper(), "#e05c5c")}'
            f'{_row("Priority Score", f"P{priority_score:.0f}", "#e05c5c")}'
            f'{_row("Location", (address or f"{latitude:.5f},{longitude:.5f}")[:60])}</div>')
    return send_email(ADMIN_EMAIL, f"URGENT: High Severity {complaint_id} - RoadWatch",
                      _base("Emergency Alert", body, maps, "View on Maps"))