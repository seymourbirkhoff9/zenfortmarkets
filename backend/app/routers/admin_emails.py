from __future__ import annotations
"""
app/routers/admin_emails.py — Admin email broadcast and targeted messaging
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, BroadcastLog, UserInvestment, KYCStatus
from app.schemas import AdminSendUserEmailRequest, AdminBroadcastEmailRequest, BroadcastLogResponse
from app.security import get_current_admin
from app.services.notification_service import send_notification_and_email
from app.services.email_templates import render_email
from app.database import SessionLocal

logger = logging.getLogger("zenfort.admin_emails")

router = APIRouter(prefix="/api/admin/emails", tags=["Admin Emails"])


def _send_email_to_user(
    db: Session,
    user: User,
    subject: str,
    body: str,
    notification_title: str,
):
    """
    Helper function to send email and create notification for a single user.
    Used in both single-user send and broadcast background tasks.
    """
    try:
        send_notification_and_email(
            db=db,
            user=user,
            title=notification_title,
            message=body,
            notification_type="general",
            email_subject=subject,
            # Admin text is rendered as escaped paragraphs, never as raw HTML.
            email_html=render_email(subject, user.full_name,
                                    [p.strip() for p in body.split("\n\n") if p.strip()]),
        )
        logger.info("Email sent to %s: %s", user.email, subject)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", user.email, e)


def _broadcast_emails_task(
    _request_db: Session,
    admin_id: str,
    subject: str,
    body: str,
    target_filter: str,
    broadcast_log_id: str,
):
    """
    Background task to broadcast emails to filtered users.
    Updates recipient_count on the BroadcastLog after completion.
    """
    # The request's session is closed by the time a background task runs,
    # so the task owns a fresh one.
    db = SessionLocal()
    try:
        # Build query based on target_filter
        query = db.query(User).filter(User.is_admin == False)

        if target_filter == "verified_kyc":
            query = query.filter(User.kyc_status == KYCStatus.VERIFIED)
        elif target_filter == "unverified_kyc":
            query = query.filter(User.kyc_status == KYCStatus.UNVERIFIED)
        elif target_filter == "active_investors":
            # Users with at least one active investment
            query = query.join(UserInvestment).filter(
                UserInvestment.status == "active"
            ).distinct()
        # For "all", no additional filter

        users = query.all()
        recipient_count = 0

        for user in users:
            _send_email_to_user(
                db=db,
                user=user,
                subject=subject,
                body=body,
                notification_title="New Announcement",
            )
            recipient_count += 1

        # Update broadcast log with recipient count
        broadcast_log = db.query(BroadcastLog).filter(BroadcastLog.id == broadcast_log_id).first()
        if broadcast_log:
            broadcast_log.recipient_count = recipient_count
            db.commit()

        logger.info("Broadcast completed: %d recipients", recipient_count)

    except Exception as e:
        logger.error("Broadcast task failed: %s", e, exc_info=True)
    finally:
        db.close()


# ──────────────────────────────────────────────
# POST /api/admin/emails/send-user — Send to single user
# ──────────────────────────────────────────────
@router.post("/send-user", status_code=status.HTTP_200_OK)
def send_email_to_user(
    payload: AdminSendUserEmailRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Send a custom email and create an in-app notification for a specific user."""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot send emails to admin users.")

    _send_email_to_user(
        db=db,
        user=user,
        subject=payload.subject,
        body=payload.body,
        notification_title="Message from Admin",
    )

    return {"status": "ok", "message": "Email sent successfully"}


# ──────────────────────────────────────────────
# POST /api/admin/emails/broadcast — Broadcast to filtered users
# ──────────────────────────────────────────────
@router.post("/broadcast", response_model=BroadcastLogResponse, status_code=status.HTTP_201_CREATED)
def broadcast_email(
    payload: AdminBroadcastEmailRequest,
    background_tasks: BackgroundTasks,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Broadcast an email to users based on target filter.
    Uses background tasks to avoid HTTP timeout.
    """
    # Validate target_filter
    valid_filters = ["all", "verified_kyc", "unverified_kyc", "active_investors"]
    if payload.target_filter not in valid_filters:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target_filter. Must be one of: {', '.join(valid_filters)}"
        )

    # Create broadcast log
    broadcast_log = BroadcastLog(
        admin_id=admin.id,
        subject=payload.subject,
        body=payload.body,
        target_filter=payload.target_filter,
        recipient_count=0,  # Will be updated by background task
    )
    db.add(broadcast_log)
    db.commit()
    db.refresh(broadcast_log)

    # Add background task for async email dispatch
    background_tasks.add_task(
        _broadcast_emails_task,
        db=db,
        admin_id=str(admin.id),
        subject=payload.subject,
        body=payload.body,
        target_filter=payload.target_filter,
        broadcast_log_id=str(broadcast_log.id),
    )

    return broadcast_log


# ──────────────────────────────────────────────
# GET /api/admin/emails/history — List broadcast logs
# ──────────────────────────────────────────────
@router.get("/history", response_model=List[BroadcastLogResponse])
def list_broadcast_history(
    skip: int = 0,
    limit: int = 50,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return historical broadcast logs ordered by latest first."""
    return (
        db.query(BroadcastLog)
        .order_by(BroadcastLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
