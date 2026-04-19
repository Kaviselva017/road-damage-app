"""
RoadWatch — Async Email Service (AUTH-3)
Wraps Gmail SMTP in a thread-pool executor so FastAPI never blocks.
Falls back gracefully if GMAIL_SENDER / GMAIL_APP_PASSWORD are not set,
while also honouring the legacy SMTP_USER / SMTP_PASS variables.
"""

import asyncio
import logging
import os
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")


class EmailService:
    def __init__(self) -> None:
        # Prefer GMAIL_* vars; fall back to legacy SMTP_* vars
        self.sender   = os.getenv("GMAIL_SENDER")   or os.getenv("SMTP_USER", "")
        self.password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASS", "")
        self.bcc      = os.getenv("GMAIL_BCC", "")
        self.host     = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.port     = int(os.getenv("SMTP_PORT", "587"))
        self._conn: Optional[smtplib.SMTP] = None
        self._conn_at: float = 0.0
        self._conn_ttl: float = 60.0

    # ── SMTP connection pool (single reused connection per worker) ────────────

    def _get_conn(self) -> smtplib.SMTP:
        now = time.monotonic()
        if self._conn and (now - self._conn_at) < self._conn_ttl:
            try:
                self._conn.noop()
                return self._conn
            except Exception:
                self._conn = None

        conn = smtplib.SMTP(self.host, self.port, timeout=10)
        conn.ehlo()
        conn.starttls()
        conn.login(self.sender, self.password)
        self._conn = conn
        self._conn_at = now
        return conn

    def _send_sync(self, to: str, subject: str, html: str) -> bool:
        if not self.sender or not self.password:
            logger.debug("Email not configured — skipping '%s' → %s", subject, to)
            return False
        if not to or "@" not in to:
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"Road Damage Reporter <{self.sender}>"
            msg["To"]      = to
            if self.bcc:
                msg["Bcc"] = self.bcc
            msg.attach(MIMEText(html, "html", "utf-8"))
            conn = self._get_conn()
            recipients = [to] + ([self.bcc] if self.bcc else [])
            conn.sendmail(self.sender, recipients, msg.as_string())
            logger.info("Email sent ✓  '%s' → %s", subject, to)
            return True
        except Exception as exc:
            logger.error("Email failed → %s : %s", to, exc, exc_info=True)
            self._conn = None   # force reconnect on next attempt
            return False

    # ── Public async interface ────────────────────────────────────────────────

    async def send_email(self, to: str, subject: str, html: str) -> bool:
        """Non-blocking send via thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._send_sync, to, subject, html)

    def send_email_sync(self, to: str, subject: str, html: str) -> bool:
        """Synchronous send — for use inside BackgroundTasks callbacks."""
        return self._send_sync(to, subject, html)


email_service = EmailService()
