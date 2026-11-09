"""Email confirmation architecture.

If SMTP_HOST is configured in .env a real email is sent; otherwise the message is
written to the application log ("console mailer") so the feature can be demonstrated
without any mail server.  Failures never break a registration.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_confirmation(event, reg, to_email, name):
    body = (f"Hi {name},\n\nYou are registered for {event['title']}.\n"
            f"Registration ID: {reg['reg_code']}\nDate: {event['date']} {event['time']}\n"
            f"Venue: {event['venue']}\n\nPlease keep this ID for check-in.\n")
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        current_app.logger.info("[console mailer] to=%s subject=Registration confirmed (%s)",
                                to_email, reg["reg_code"])
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Registration confirmed: {event['title']}"
        msg["From"] = cfg["MAIL_FROM"]
        msg["To"] = to_email
        msg.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as s:
            s.starttls()
            if cfg.get("SMTP_USER"):
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 - mail problems must not fail the registration
        current_app.logger.warning("Email send failed: %s", exc)
        return False
