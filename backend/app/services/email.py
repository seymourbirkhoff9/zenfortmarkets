from __future__ import annotations
"""
app/services/email.py — Resend transactional email service
"""
import logging
import resend
from app.config import settings
from app.services.email_templates import render_email
from app.services.email_translations import get_string

logger = logging.getLogger("zenfort.email")

# Set API key once at import time
resend.api_key = settings.RESEND_API_KEY


def _api_key_present() -> bool:
    """Return True only when a real Resend API key is configured."""
    key = (settings.RESEND_API_KEY or "").strip()
    return bool(key) and not key.startswith("re_XXXX")


def send_welcome_email(to_email: str, full_name: str, lang: str = "en") -> None:
    """Send a welcome email to newly registered users in their preferred language."""
    if not _api_key_present():
        logger.info(
            "[Mock Email] send_welcome_email → to=%s  lang=%s  subject='Welcome to Zenfort Markets'",
            to_email,
            lang,
        )
        return

    try:
        title = get_string("welcome_title", lang=lang)
        p1 = get_string("welcome_p1", lang=lang)
        html_body = render_email(
            title,
            full_name,
            [p1],
            cta=(get_string("open_account", lang=lang), f"{settings.FRONTEND_URL.rstrip('/')}/login.html"),
            lang=lang,
        )
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": f"{title} — Zenfort Markets",
            "html": html_body,
        })
        logger.info("Welcome email sent → %s (%s)", to_email, lang)
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

