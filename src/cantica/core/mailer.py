"""
Minimal SMTP mailer used for invite emails.

When ``CANTICA_SMTP_HOST`` is empty, ``send_invite`` is a no-op (the invite
link is still returned to the admin in the API response so they can share it
manually).
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_invite(
    *,
    to_email: str,
    invite_url: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_from: str,
    smtp_tls: bool,
    instance_name: str = "Cantica",
) -> bool:
    """Send an invite email.  Returns True on success, False if SMTP is unconfigured."""
    if not smtp_host:
        log.info("SMTP not configured — invite email not sent to %s", to_email)
        return False

    subject = f"You've been invited to {instance_name}"
    html = f"""\
<html><body style="font-family:sans-serif;max-width:480px;margin:40px auto;color:#18181b">
  <h2 style="color:#7c3aed">You're invited to {instance_name}</h2>
  <p>An admin has invited you to create an account.</p>
  <p>
    <a href="{invite_url}" style="display:inline-block;padding:10px 20px;background:#7c3aed;color:white;border-radius:8px;text-decoration:none;font-weight:600">
      Accept invitation
    </a>
  </p>
  <p style="color:#71717a;font-size:13px">
    Or copy this link into your browser:<br>
    <code style="font-size:12px">{invite_url}</code>
  </p>
  <p style="color:#71717a;font-size:12px">This link expires in 7 days and can only be used once.</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        if smtp_tls:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user:
                    server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [to_email], msg.as_string())
        log.info("Invite email sent to %s", to_email)
        return True
    except Exception:  # noqa: BLE001
        log.exception("Failed to send invite email to %s", to_email)
        return False
