"""
app/services/notification_service.py — Notification & Email Service

Creates in-app notifications and sends transactional emails via Resend.
Email failures are logged but never crash the primary transaction.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from app.models import User, Notification
from app.config import settings
from app.services import mailer

logger = logging.getLogger("zenfort.notification")

# Email delivery runs off the request thread so a slow or failing provider never
# delays (or breaks) the API response.
_email_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="email")


def queue_email(to: str, subject: str, html: str, reply_to: str | None = None) -> None:
    """Send in the background; failures are logged by the mailer (and never break the request)."""
    _email_pool.submit(mailer.send, to, subject, html, reply_to)


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

    # 2. Send email in the background (failures are logged only)
    queue_email(user.email, email_subject, email_html)
    return notification
