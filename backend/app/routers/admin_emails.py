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
from app.config import settings
from app.models import Notification
from app.services import mailer
from app.services.email_templates import render_email
from app.database import SessionLocal

logger = logging.getLogger("zenfort.admin_emails")

router = APIRouter(prefix="/api/admin/emails", tags=["Admin Emails"])


def _admin_html(user: User, subject: str, body: str) -> str:
    # Admin text is rendered as escaped paragraphs, never as raw HTML.
    return render_email(subject, user.full_name, [p.strip() for p in body.split("\n\n") if p.strip()],
                        cta=("Open your account", f"{settings.FRONTEND_URL.rstrip('/')}/app.html"))


def _in_app(db: Session, user: User, title: str, body: str) -> None:
    db.add(Notification(user_id=user.id, title=title, message=body[:2000], type="general", is_read=False))


def _broadcast_emails_task(subject: str, body: str, target_filter: str, broadcast_log_id: str):
    """Background: in-app notice for everyone, then email in batches of 100; records delivered/failed."""
    db = SessionLocal()
    try:
        query = db.query(User).filter(User.is_admin.is_(False), User.is_active.is_(True))
        if target_filter == "verified_kyc":
            query = query.filter(User.kyc_status == KYCStatus.VERIFIED)
        elif target_filter == "unverified_kyc":
            query = query.filter(User.kyc_status == KYCStatus.UNVERIFIED)
        elif target_filter == "active_investors":
            query = query.join(UserInvestment).filter(UserInvestment.status == "active").distinct()
        users = query.all()
        for u in users:
            _in_app(db, u, "New announcement", body)
        db.commit()

        results = mailer.send_batch([{"to": u.email, "subject": subject, "html": _admin_html(u, subject, body)} for u in users])
        failed = [r for r in results if not r.ok]
        log = db.query(BroadcastLog).filter(BroadcastLog.id == broadcast_log_id).first()
        if log:
            log.recipient_count = len(users)
            log.delivered_count = len(results) - len(failed)
            log.failed_count = len(failed)
            log.last_error = failed[-1].reason if failed else None
            db.commit()
        logger.info("Broadcast finished: %d recipients, %d failed", len(users), len(failed))
    except Exception as e:
        logger.exception("Broadcast task failed")
        # Record the failure so the admin's "Sent" list doesn't stay on "Sending…" forever.
        db.rollback()
        log = db.query(BroadcastLog).filter(BroadcastLog.id == broadcast_log_id).first()
        if log:
            log.delivered_count = 0
            log.failed_count = max(log.recipient_count, 1)
            log.last_error = f"Sending stopped: {e}"[:500]
            db.commit()
    finally:
        db.close()


# ──────────────────────────────────────────────
# POST /api/admin/emails/send-user — one customer, delivered while you wait
# ──────────────────────────────────────────────
@router.post("/send-user", status_code=status.HTTP_200_OK)
def send_email_to_user(payload: AdminSendUserEmailRequest, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    Adds an in-app message and sends the email immediately, reporting whether the email
    service accepted it, so the admin knows if it actually went out.
    """
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Admins can’t be emailed from here.")
    _in_app(db, user, "Message from support", payload.body)
    db.commit()
    result = mailer.send(user.email, payload.subject, _admin_html(user, payload.subject, payload.body))
    return {"in_app": True, "email_sent": result.ok, "email_error": result.reason,
            "message": "Delivered to their inbox and their notifications." if result.ok
            else "Added to their notifications, but the email wasn’t delivered."}


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
