"""
app/services/notification_service.py — Notification & Email Service

Creates in-app notifications and sends transactional emails via Resend.
Email failures are logged but never crash the primary transaction.
"""
import logging
from sqlalchemy.orm import Session
from app.models import User, Notification
from app.services.email import resend, settings, logger as email_logger

logger = logging.getLogger("zenfort.notification")


def _api_key_present() -> bool:
    """Return True only when a real Resend API key is configured."""
    key = (settings.RESEND_API_KEY or "").strip()
    return bool(key) and not key.startswith("re_XXXX")


def send_notification_and_email(
    db: Session,
    user: User,
    title: str,
    message: str,
    notification_type: str,
    email_subject: str,
    email_html: str,
) -> Notification:
    """
    Create an in-app notification and send a transactional email.

    This function is designed to be called from admin workflows (KYC review,
    deposit/withdrawal approval, account status changes). Email delivery failures
    are logged but do not affect the primary transaction commit.

    Args:
        db: SQLAlchemy database session
        user: The User model instance to notify
        title: Notification title (displayed in-app)
        message: Notification message (displayed in-app)
        notification_type: Type category ("kyc", "deposit", "withdrawal", "account", "general")
        email_subject: Subject line for the email
        email_html: HTML body for the email

    Returns:
        The created Notification model instance
    """
    # 1. Create in-app notification
    notification = Notification(
        user_id=user.id,
        title=title,
        message=message,
        type=notification_type,
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # 2. Send email (non-blocking - failures logged only)
    if not _api_key_present():
        logger.info(
            "[Mock Email] %s → to=%s  subject='%s'",
            notification_type,
            user.email,
            email_subject,
        )
        return notification

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": [user.email],
            "subject": email_subject,
            "html": email_html,
        })
        logger.info("Email sent → %s: %s", user.email, email_subject)
    except Exception as e:
        # Email failure should NOT crash the main transaction
        logger.error("Failed to send email to %s: %s", user.email, e, exc_info=True)

    return notification
