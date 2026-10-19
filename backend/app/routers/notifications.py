"""
app/routers/notifications.py — User notification center endpoints
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Notification
from app.schemas import NotificationResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# ──────────────────────────────────────────────
# GET /api/notifications/ — List user notifications
# ──────────────────────────────────────────────
@router.get("/", response_model=List[NotificationResponse])
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all notifications for the authenticated user, sorted by latest first."""
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


# ──────────────────────────────────────────────
# PATCH /api/notifications/{id}/read — Mark as read
# ──────────────────────────────────────────────
@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a specific notification as read."""
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


# ──────────────────────────────────────────────
# PATCH /api/notifications/read-all — Mark all as read
# ──────────────────────────────────────────────
@router.patch("/read-all", status_code=status.HTTP_200_OK)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications for the authenticated user as read."""
    (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return {"status": "ok", "message": "All notifications marked as read"}
