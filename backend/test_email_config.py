from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Mock logger for the test
import logging
logging.basicConfig(level=logging.INFO)

from app.services.notification_service import send_email, _base

to = "studentofficial2002@gmail.com"
subject = "TEST EMAIL - RoadWatch"
body = "<p>This is a test to verify email configuration.</p>"
html = _base("Verification Test", body)

print(f"Attempting to send email to {to}...")
success = send_email(to, subject, html)

if success:
    print("SUCCESS: Email sent!")
else:
    print("FAILED: Check the logs above for errors.")
