from __future__ import annotations
"""
app/services/admin_alerts.py — in-app alerts for every admin when a user action
needs review (pending deposit, pending withdrawal, KYC submission).
"""
from sqlalchemy.orm import Session

from app.models import Notification, User


def notify_admins(db: Session, title: str, message: str, notification_type: str) -> int:
    """Queue one notification per active admin. Caller commits."""
    admins = db.query(User.id).filter(User.is_admin.is_(True), User.is_active.is_(True)).all()
    for (admin_id,) in admins:
        db.add(Notification(user_id=admin_id, title=title, message=message,
                            type=notification_type, is_read=False))
    return len(admins)
