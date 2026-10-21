from __future__ import annotations
"""
app/services/email.py — Resend transactional email service
"""
import logging
import resend
from app.config import settings

logger = logging.getLogger("zenfort.email")

# Set API key once at import time
resend.api_key = settings.RESEND_API_KEY


def _api_key_present() -> bool:
    """Return True only when a real Resend API key is configured."""
    key = (settings.RESEND_API_KEY or "").strip()
    return bool(key) and not key.startswith("re_XXXX")


def send_welcome_email(to_email: str, full_name: str) -> None:
    """Send a welcome email to newly registered users."""
    if not _api_key_present():
        logger.info(
            "[Mock Email] send_welcome_email → to=%s  subject='Welcome to Zenfort Markets'",
            to_email,
        )
        return

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": "Welcome to Zenfort Markets",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
              <h2 style="color:#1a1a3e;">Welcome to Zenfort Markets, {full_name}!</h2>
              <p>Your account has been created successfully. You can now log in and explore
                 our multi-currency crypto investment platform.</p>
              <p>If you have any questions, reach out to <a href="mailto:support@zenfortmarkets.com">
                 support@zenfortmarkets.com</a>.</p>
              <hr/>
              <small style="color:#888;">Zenfort Markets — Trade Smarter. Grow Stronger.</small>
            </div>
            """,
        })
        logger.info("Welcome email sent → %s", to_email)
    except Exception as e:
        logger.error("Failed to send welcome email to %s: %s", to_email, e)


def send_p2p_transfer_notification(
    sender_name: str,
    recipient_email: str,
    recipient_name: str,
    amount: str,
    currency: str,
) -> None:
    """Notify recipient of an incoming P2P transfer."""
    if not _api_key_present():
        logger.info(
            "[Mock Email] send_p2p_transfer_notification → to=%s  amount=%s %s  from=%s",
            recipient_email,
            amount,
            currency,
            sender_name,
        )
        return

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [recipient_email],
            "subject": f"You received {amount} {currency} on Zenfort Markets",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
              <h2 style="color:#1a1a3e;">Funds Received</h2>
              <p>Hi {recipient_name},</p>
              <p><strong>{sender_name}</strong> has sent you
                 <strong>{amount} {currency}</strong> via Zenfort Markets.</p>
              <p>The funds have been credited to your Main wallet.</p>
              <hr/>
              <small style="color:#888;">Zenfort Markets</small>
            </div>
            """,
        })
        logger.info("P2P notification sent → %s", recipient_email)
    except Exception as e:
        logger.error(
            "Failed to send P2P notification to %s: %s", recipient_email, e
        )

