"""
RoadWatch — Email Templates (AUTH-3)
All styles are inline so Gmail renders them correctly.
Each function returns (subject: str, html: str).
"""
from __future__ import annotations


# ── Shared layout ─────────────────────────────────────────────────────────────

def _wrap(body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#f4f4f4;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;
                    border:1px solid #e0e0e0;max-width:600px;">
        <tr>
          <td style="background:#1a1a2e;padding:20px 32px;">
            <span style="color:#ffffff;font-size:18px;font-weight:600;
                         letter-spacing:0.3px;">Road Damage Reporter</span>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px 20px;font-size:15px;
                     color:#333333;line-height:1.65;">
            {body_html}
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px 24px;font-size:12px;
                     color:#999999;border-top:1px solid #eeeeee;">
            You received this because you use Road Damage Reporter.<br>
            Please do not reply to this email.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _severity_badge(severity: str) -> str:
    colours = {
        "critical": ("#fff5f5", "#993C1D", "#FAECE7"),
        "high":     ("#fff8f0", "#BA7517", "#FAEEDA"),
        "medium":   ("#f0f4ff", "#534AB7", "#EEEDFE"),
        "low":      ("#f0faf6", "#0F6E56", "#E1F5EE"),
    }
    text_c, border_c, bg_c = colours.get(severity.lower(), ("#333", "#888", "#f0f0f0"))
    return (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:20px;'
        f'font-size:12px;font-weight:600;background:{bg_c};color:{text_c};'
        f'border:1px solid {border_c};">{severity.upper()}</span>'
    )


def _status_timeline(current: str) -> str:
    steps = ["Received", "In Review", "Repair Scheduled", "Fixed"]
    cells = ""
    for step in steps:
        active = step.lower().replace(" ", "_") == current.lower().replace(" ", "_")
        colour = "#534AB7" if active else "#cccccc"
        weight = "700" if active else "400"
        cells += (
            f'<td align="center" style="padding:0 8px;">'
            f'<div style="width:12px;height:12px;border-radius:50%;'
            f'background:{colour};margin:0 auto 4px;"></div>'
            f'<span style="font-size:11px;color:{colour};font-weight:{weight};">{step}</span></td>'
        )
    return (
        '<table cellpadding="0" cellspacing="0" style="margin:20px 0;">'
        f'<tr>{cells}</tr></table>'
    )


# ── 1. Welcome ────────────────────────────────────────────────────────────────

def welcome_email(name: str, email: str) -> tuple[str, str]:
    first = name.split()[0] if name else "there"
    subject = f"Welcome to Road Damage Reporter, {first}!"
    body = _wrap(f"""
        <p style="font-size:20px;font-weight:600;margin:0 0 12px;">Welcome, {first}! 👋</p>
        <p>Your account is set up and ready. Here's how to get started:</p>
        <table cellpadding="0" cellspacing="0" style="margin:16px 0;">
          <tr><td style="padding:8px 0;font-size:14px;color:#555;">
            📸 &nbsp; Take a photo of road damage</td></tr>
          <tr><td style="padding:8px 0;font-size:14px;color:#555;">
            📍 &nbsp; Your GPS location is captured automatically</td></tr>
          <tr><td style="padding:8px 0;font-size:14px;color:#555;">
            🤖 &nbsp; Our AI analyses the damage type and severity</td></tr>
          <tr><td style="padding:8px 0;font-size:14px;color:#555;">
            🔔 &nbsp; You'll get email updates as the repair progresses</td></tr>
        </table>
        <p style="color:#777;font-size:13px;">Signed in with: {email}</p>
    """)
    return subject, body


# ── 2. Complaint received ─────────────────────────────────────────────────────

def complaint_received_email(
    name: str, complaint_id: str, location: str
) -> tuple[str, str]:
    first = name.split()[0] if name else "there"
    subject = f"Complaint #{complaint_id} received — we're on it"
    body = _wrap(f"""
        <p>Hi {first},</p>
        <p>We've received your road damage report. Our AI is analysing your photo now.</p>
        <table cellpadding="0" cellspacing="0"
               style="background:#f8f8f8;border-radius:8px;padding:16px 20px;margin:16px 0;width:100%;">
          <tr><td style="font-size:13px;color:#777;padding-bottom:4px;">Complaint ID</td></tr>
          <tr><td style="font-size:22px;font-weight:700;color:#1a1a2e;">#{complaint_id}</td></tr>
          <tr><td style="font-size:13px;color:#777;padding-top:12px;">Location</td></tr>
          <tr><td style="font-size:14px;color:#333;">{location}</td></tr>
        </table>
        <p style="color:#777;font-size:13px;">
          You'll receive another email once the AI analysis is complete.
        </p>
    """)
    return subject, body


# ── 3. AI result ──────────────────────────────────────────────────────────────

def ai_result_email(
    name: str,
    complaint_id: str,
    damage_class: str,
    severity: str,
    confidence: float,
) -> tuple[str, str]:
    first = name.split()[0] if name else "there"
    subject = f"AI analysis complete for complaint #{complaint_id}"
    conf_pct = round(confidence * 100, 1)
    body = _wrap(f"""
        <p>Hi {first},</p>
        <p>Our AI has finished analysing your photo for complaint <strong>#{complaint_id}</strong>.</p>
        <table cellpadding="0" cellspacing="0"
               style="background:#f8f8f8;border-radius:8px;padding:16px 20px;margin:16px 0;width:100%;">
          <tr><td style="font-size:13px;color:#777;padding-bottom:4px;">Damage type</td></tr>
          <tr><td style="font-size:18px;font-weight:600;color:#1a1a2e;
                         text-transform:capitalize;padding-bottom:12px;">
            {damage_class.replace("_", " ")}
          </td></tr>
          <tr><td style="font-size:13px;color:#777;padding-bottom:6px;">Severity</td></tr>
          <tr><td style="padding-bottom:12px;">{_severity_badge(severity)}</td></tr>
          <tr><td style="font-size:13px;color:#777;padding-bottom:4px;">AI confidence</td></tr>
          <tr><td>
            <div style="background:#e0e0e0;border-radius:4px;height:8px;width:100%;max-width:300px;">
              <div style="background:#534AB7;border-radius:4px;height:8px;width:{conf_pct}%;"></div>
            </div>
            <span style="font-size:13px;color:#555;margin-top:4px;display:inline-block;">{conf_pct}%</span>
          </td></tr>
        </table>
        <p style="color:#777;font-size:13px;">
          A municipal officer has been notified and will schedule a repair.
        </p>
    """)
    return subject, body


# ── 4. Status update ──────────────────────────────────────────────────────────

def status_update_email(
    name: str,
    complaint_id: str,
    old_status: str,
    new_status: str,
    officer_note: str,
) -> tuple[str, str]:
    first = name.split()[0] if name else "there"
    subject = f"Update on your complaint #{complaint_id}"
    note_block = (
        f'<p style="background:#f0f4ff;border-left:3px solid #534AB7;'
        f'padding:10px 14px;border-radius:0 6px 6px 0;font-size:14px;color:#333;margin:16px 0;">'
        f'<strong>Officer note:</strong> {officer_note}</p>'
        if officer_note else ""
    )
    body = _wrap(f"""
        <p>Hi {first},</p>
        <p>There's an update on your complaint <strong>#{complaint_id}</strong>.</p>
        <p>Status changed from
           <strong>{old_status.replace("_", " ").title()}</strong> to
           <strong>{new_status.replace("_", " ").title()}</strong>.</p>
        {_status_timeline(new_status)}
        {note_block}
        <p style="color:#777;font-size:13px;">
          We'll notify you again when the next stage is reached.
        </p>
    """)
    return subject, body


# ── 5. Officer critical alert ─────────────────────────────────────────────────

def officer_alert_email(
    officer_email: str,
    complaint_id: str,
    severity: str,
    location: str,
    damage_class: str,
    lat: float,
    lng: float,
    image_url: str = "",
) -> tuple[str, str]:
    maps_url = f"https://www.google.com/maps?q={lat},{lng}"
    img_block = (
        f'<img src="{image_url}" alt="Damage photo" '
        f'style="width:100%;max-width:536px;border-radius:6px;margin:12px 0;display:block;">'
        if image_url else ""
    )
    subject = f"[{severity.upper()}] Road damage reported — complaint #{complaint_id}"
    body = _wrap(f"""
        <p style="font-size:18px;font-weight:700;color:#993C1D;margin:0 0 12px;">Action required</p>
        <p>A new complaint has been submitted with {_severity_badge(severity)} severity.</p>
        <table cellpadding="0" cellspacing="0"
               style="background:#f8f8f8;border-radius:8px;padding:16px 20px;margin:16px 0;width:100%;">
          <tr><td style="font-size:13px;color:#777;padding-bottom:2px;">Complaint</td></tr>
          <tr><td style="font-size:18px;font-weight:700;color:#1a1a2e;padding-bottom:10px;">#{complaint_id}</td></tr>
          <tr><td style="font-size:13px;color:#777;padding-bottom:2px;">Type</td></tr>
          <tr><td style="font-size:14px;color:#333;padding-bottom:10px;text-transform:capitalize;">
            {damage_class.replace("_", " ")}
          </td></tr>
          <tr><td style="font-size:13px;color:#777;padding-bottom:2px;">Location</td></tr>
          <tr><td style="font-size:14px;color:#333;">{location}</td></tr>
        </table>
        {img_block}
        <table cellpadding="0" cellspacing="0" style="margin:20px 0;">
          <tr>
            <td style="padding-right:12px;">
              <a href="{maps_url}"
                 style="display:inline-block;padding:10px 20px;background:#1a1a2e;color:#ffffff;
                        border-radius:6px;font-size:14px;font-weight:600;text-decoration:none;">
                View on map
              </a>
            </td>
          </tr>
        </table>
    """)
    return subject, body


# ── 6. Suspicious login alert ─────────────────────────────────────────────────

def suspicious_login_email(
    name: str,
    ip: str,
    location: str,
    device: str,
    timestamp: str,
    revoke_url: str,
) -> tuple[str, str]:
    first = name.split()[0] if name else "there"
    subject = "New sign-in to your Road Damage Reporter account"
    body = _wrap(f"""
        <p>Hi {first},</p>
        <p>We detected a sign-in to your account from a new location.</p>
        <table cellpadding="0" cellspacing="0"
               style="background:#f8f8f8;border-radius:8px;padding:16px 20px;margin:16px 0;width:100%;">
          <tr>
            <td style="font-size:13px;color:#777;width:120px;">IP address</td>
            <td style="font-size:14px;color:#333;">{ip}</td>
          </tr>
          <tr>
            <td style="font-size:13px;color:#777;padding-top:8px;">Location</td>
            <td style="font-size:14px;color:#333;padding-top:8px;">{location}</td>
          </tr>
          <tr>
            <td style="font-size:13px;color:#777;padding-top:8px;">Device</td>
            <td style="font-size:14px;color:#333;padding-top:8px;">{device}</td>
          </tr>
          <tr>
            <td style="font-size:13px;color:#777;padding-top:8px;">Time</td>
            <td style="font-size:14px;color:#333;padding-top:8px;">{timestamp}</td>
          </tr>
        </table>
        <p>If this was you, no action is needed.</p>
        <p>If this wasn't you, secure your account immediately:</p>
        <table cellpadding="0" cellspacing="0" style="margin:16px 0;">
          <tr>
            <td>
              <a href="{revoke_url}"
                 style="display:inline-block;padding:10px 20px;background:#993C1D;color:#ffffff;
                        border-radius:6px;font-size:14px;font-weight:600;text-decoration:none;">
                Sign out all devices
              </a>
            </td>
          </tr>
        </table>
        <p style="color:#999;font-size:12px;">This link expires in 1 hour.</p>
    """)
    return subject, body
