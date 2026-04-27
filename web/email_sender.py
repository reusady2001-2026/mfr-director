"""Email sending via SMTP. Configure via env vars."""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)
APP_NAME = "MFR Director"


def send_login_code(to_email: str, code: str) -> None:
    now = datetime.utcnow()
    month_label = now.strftime("%B %Y")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; background: #F4F6F9; margin: 0; padding: 40px 20px; }}
  .card {{ background: #fff; border-radius: 10px; max-width: 480px; margin: 0 auto;
           box-shadow: 0 2px 12px rgba(0,0,0,0.08); overflow: hidden; }}
  .header {{ background: #0F1C2E; padding: 24px 32px; }}
  .header-title {{ color: #fff; font-size: 20px; font-weight: 700; letter-spacing: 1px; }}
  .header-sub {{ color: #5B7FA6; font-size: 13px; margin-top: 4px; }}
  .body {{ padding: 32px; }}
  .code-box {{ background: #EFF6FF; border: 2px solid #1E3A5F; border-radius: 8px;
               text-align: center; padding: 20px; margin: 24px 0; }}
  .code {{ font-family: monospace; font-size: 28px; font-weight: 700; letter-spacing: 8px;
           color: #1E3A5F; }}
  .note {{ font-size: 12px; color: #9AAABB; margin-top: 8px; }}
  p {{ color: #374151; font-size: 14px; line-height: 1.6; }}
  .footer {{ padding: 16px 32px; background: #F4F6F9; font-size: 11px; color: #9AAABB; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="header-title">MFR Director</div>
    <div class="header-sub">Institutional Portfolio Intelligence</div>
  </div>
  <div class="body">
    <p>Here is your login code for <strong>{month_label}</strong>:</p>
    <div class="code-box">
      <div class="code">{code}</div>
      <div class="note">Valid for {month_label} only</div>
    </div>
    <p>Enter this code on the login page to access your dashboard.<br>
    This code is unique to your account and rotates monthly with your subscription.</p>
  </div>
  <div class="footer">
    This email was sent to {to_email}. If you did not request this code, ignore this email.
  </div>
</div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{APP_NAME}] Your {month_label} Login Code: {code}"
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
