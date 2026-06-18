"""Email delivery via stdlib smtplib (Microsoft 365 / Exchange SMTP).

DEFAULT OFF. send_email() is a safe no-op (logs a warning) whenever email is
disabled or the configuration is incomplete, so the app runs fine unconfigured
and callers never have to guard the call. When enabled it connects over
STARTTLS, authenticates, and sends a plain-text message with optional binary
attachments (e.g. the monthly .xlsx report).

To actually enable email, set in .env:
    SMTP_ENABLED=true
    SMTP_HOST=smtp.office365.com
    SMTP_PORT=587
    SMTP_USER=<mailbox@golden.com.fj>
    SMTP_PASSWORD=<app password / mailbox password>
    SMTP_FROM=<from address, usually = SMTP_USER>
    ALERT_EMAIL_TO=a@x,b@y      (for alerts)
    REPORT_EMAIL_TO=a@x,b@y     (for the scheduled report)
"""
import logging
import smtplib
from email.message import EmailMessage

from ..core.config import settings

logger = logging.getLogger("app.email")


def parse_recipients(raw: str | None) -> list[str]:
    """Split a comma-separated recipient string into a clean list."""
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def email_configured() -> bool:
    """True when email is enabled AND the minimum config is present."""
    if not settings.smtp_enabled:
        return False
    required = (settings.smtp_host, settings.smtp_from)
    if not all(required):
        return False
    return True


def send_email(
    subject: str,
    body: str,
    to: list[str] | str | None,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bool:
    """Send a plain-text email. Returns True if sent, False if skipped/failed.

    Never raises — a misconfigured or down SMTP server must not break the
    request/job that triggered the email. `attachments` is a list of
    (filename, bytes) tuples; they are attached as application/octet-stream.
    """
    recipients = parse_recipients(to) if isinstance(to, str) else (to or [])

    if not email_configured():
        logger.warning(
            "send_email skipped: email disabled or incomplete config "
            "(smtp_enabled=%s, host set=%s, from set=%s); subject=%r",
            settings.smtp_enabled,
            bool(settings.smtp_host),
            bool(settings.smtp_from),
            subject,
        )
        return False

    if not recipients:
        logger.warning("send_email skipped: no recipients; subject=%r", subject)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    for fname, data in attachments or []:
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=fname,
        )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            if settings.smtp_use_starttls:
                smtp.starttls()
                smtp.ehlo()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        logger.info(
            "email sent",
            extra={"subject": subject, "recipients": len(recipients)},
        )
        return True
    except Exception:
        logger.exception("send_email failed; subject=%r", subject)
        return False
