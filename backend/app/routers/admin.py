"""
app/routers/admin.py — Admin-only management endpoints
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Wallet, Transaction, KYCStatus, InvestmentPlan, UserInvestment, AuditLog
from app.schemas import (
    UserOut, AdminCreditRequest, AdminDebitRequest, AdminUserStatusUpdate,
    AdminKYCReviewRequest, TransactionOut, AdminDepositReviewRequest,
    AdminWithdrawalReviewRequest,
    InvestmentPlanCreate, InvestmentPlanUpdate, InvestmentPlanResponse,
    AuditLogResponse,
)
from app.services.notification_service import send_notification_and_email
from app.security import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _create_audit_log(
    db: Session,
    admin_id: str,
    action: str,
    target_user_id: str = None,
    details: str = None,
):
    """Helper function to create an audit log entry."""
    audit_log = AuditLog(
        admin_id=admin_id,
        action=action,
        target_user_id=target_user_id,
        details=details,
    )
    db.add(audit_log)
    db.commit()


# ──────────────────────────────────────────────
# GET /api/admin/users — List all users
# ──────────────────────────────────────────────
@router.get("/users", response_model=List[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 50,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return db.query(User).offset(skip).limit(limit).all()


# ──────────────────────────────────────────────
# PATCH /api/admin/users/{user_id}/activate
# ──────────────────────────────────────────────
@router.patch("/users/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: str,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


# ──────────────────────────────────────────────
# PATCH /api/admin/users/{user_id}/deactivate
# ──────────────────────────────────────────────
@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: str,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


# ──────────────────────────────────────────────
# PATCH /api/admin/users/{user_id}/status — Update compliance flags
# ──────────────────────────────────────────────
@router.patch("/users/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: str,
    payload: AdminUserStatusUpdate,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Update user compliance and governance flags (is_blocked, can_withdraw, can_deposit, is_active)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Track changes for notifications
    was_blocked = user.is_blocked
    could_withdraw = user.can_withdraw
    could_deposit = user.can_deposit

    # Update only provided fields
    if payload.is_blocked is not None:
        user.is_blocked = payload.is_blocked
    if payload.can_withdraw is not None:
        user.can_withdraw = payload.can_withdraw
    if payload.can_deposit is not None:
        user.can_deposit = payload.can_deposit
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

    # Audit log for block/unblock
    if payload.is_blocked is not None and user.is_blocked != was_blocked:
        action = "BLOCK_USER" if user.is_blocked else "UNBLOCK_USER"
        _create_audit_log(
            db=db,
            admin_id=admin.id,
            action=action,
            target_user_id=user_id,
            details=f"User account {'blocked' if user.is_blocked else 'unblocked'}",
        )

    # Send notifications for status changes
    if payload.is_blocked is not None and user.is_blocked != was_blocked:
        if user.is_blocked:
            send_notification_and_email(
                db=db,
                user=user,
                title="Account Blocked",
                message="Your account has been blocked. Please contact support for assistance.",
                notification_type="account",
                email_subject="Account Blocked - Zenfort Markets",
                email_html=f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
                  <h2 style="color:#1a1a3e;">Account Blocked</h2>
                  <p>Hi {user.full_name},</p>
                  <p>Your account has been blocked.</p>
                  <p>Please contact support if you have any questions or believe this is an error.</p>
                  <hr/>
                  <small style="color:#888;">Zenfort Markets</small>
                </div>
                """,
            )
        else:
            send_notification_and_email(
                db=db,
                user=user,
                title="Account Unblocked",
                message="Your account has been unblocked. You can now access all platform features.",
                notification_type="account",
                email_subject="Account Unblocked - Zenfort Markets",
                email_html=f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
                  <h2 style="color:#1a1a3e;">Account Unblocked</h2>
                  <p>Hi {user.full_name},</p>
                  <p>Your account has been unblocked.</p>
                  <p>You can now access all platform features.</p>
                  <hr/>
                  <small style="color:#888;">Zenfort Markets</small>
                </div>
                """,
            )

    if payload.can_withdraw is not None and user.can_withdraw != could_withdraw and not user.can_withdraw:
        send_notification_and_email(
            db=db,
            user=user,
            title="Withdrawals Disabled",
            message="Your withdrawal privileges have been temporarily disabled. Please contact support for assistance.",
            notification_type="account",
            email_subject="Withdrawals Disabled - Zenfort Markets",
            email_html=f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
              <h2 style="color:#1a1a3e;">Withdrawals Disabled</h2>
              <p>Hi {user.full_name},</p>
              <p>Your withdrawal privileges have been temporarily disabled.</p>
              <p>Please contact support if you have any questions.</p>
              <hr/>
              <small style="color:#888;">Zenfort Markets</small>
            </div>
            """,
        )

    if payload.can_deposit is not None and user.can_deposit != could_deposit and not user.can_deposit:
        send_notification_and_email(
            db=db,
            user=user,
            title="Deposits Disabled",
            message="Your deposit privileges have been temporarily disabled. Please contact support for assistance.",
            notification_type="account",
            email_subject="Deposits Disabled - Zenfort Markets",
            email_html=f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
              <h2 style="color:#1a1a3e;">Deposits Disabled</h2>
              <p>Hi {user.full_name},</p>
              <p>Your deposit privileges have been temporarily disabled.</p>
              <p>Please contact support if you have any questions.</p>
              <hr/>
              <small style="color:#888;">Zenfort Markets</small>
            </div>
            """,
        )

    return user


# ──────────────────────────────────────────────
# POST /api/admin/credit — Credit a user's wallet
# ──────────────────────────────────────────────
@router.post("/credit", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def credit_user_wallet(
    payload: AdminCreditRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin can credit any user's main or profit wallet (e.g. for deposits)."""
    user = db.query(User).filter(User.email == payload.user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == user.id, Wallet.wallet_type == payload.wallet_type)
        .first()
    )
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    wallet.balance += payload.amount

    tx = Transaction(
        receiver_wallet_id=wallet.id,
        amount=payload.amount,
        currency=wallet.currency,
        tx_type="deposit",
        description=payload.description or f"Admin credit to {payload.wallet_type} wallet",
        status="completed",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    # Audit log
    _create_audit_log(
        db=db,
        admin_id=admin.id,
        action="CREDIT_WALLET",
        target_user_id=str(user.id),
        details=f"Credited {payload.amount} {wallet.currency} to {payload.wallet_type} wallet",
    )

    return tx


# ──────────────────────────────────────────────
# GET /api/admin/transactions — All platform transactions
# ──────────────────────────────────────────────
@router.get("/transactions", response_model=List[TransactionOut])
def list_all_transactions(
    skip: int = 0,
    limit: int = 100,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(Transaction)
        .order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ──────────────────────────────────────────────
# POST /api/admin/wallets/debit — Debit a user's wallet
# ──────────────────────────────────────────────
@router.post("/wallets/debit", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def debit_user_wallet(
    payload: AdminDebitRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin can debit any user's main or profit wallet (e.g., for withdrawals or penalties)."""
    user = db.query(User).filter(User.email == payload.user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == user.id, Wallet.wallet_type == payload.wallet_type)
        .first()
    )
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    if wallet.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient balance in wallet.",
        )

    wallet.balance -= payload.amount

    tx = Transaction(
        sender_wallet_id=wallet.id,
        amount=payload.amount,
        currency=wallet.currency,
        tx_type="admin_debit",
        description=payload.description or f"Admin debit from {payload.wallet_type} wallet",
        status="completed",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    # Audit log
    _create_audit_log(
        db=db,
        admin_id=admin.id,
        action="DEBIT_WALLET",
        target_user_id=str(user.id),
        details=f"Debited {payload.amount} {wallet.currency} from {payload.wallet_type} wallet",
    )

    return tx


# ──────────────────────────────────────────────
# PATCH /api/admin/kyc/{user_id}/review — Review KYC
# ──────────────────────────────────────────────
@router.patch("/kyc/{user_id}/review", response_model=UserOut)
def review_kyc(
    user_id: str,
    payload: AdminKYCReviewRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Review and approve/reject a user's KYC verification."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Update KYC status
    user.kyc_status = payload.status

    # Set is_verified based on approval/rejection
    if payload.status.value == "VERIFIED":
        user.is_verified = True
    elif payload.status.value == "REJECTED":
        user.is_verified = False

    # Store rejection reason if provided
    if payload.rejection_reason:
        # For now, we could store this in kyc_document_url or add a new field
        # Storing it in kyc_document_url temporarily as a workaround
        user.kyc_document_url = f"REJECTED: {payload.rejection_reason}"

    db.commit()
    db.refresh(user)

    # Audit log
    _create_audit_log(
        db=db,
        admin_id=admin.id,
        action="REVIEW_KYC",
        target_user_id=user_id,
        details=f"KYC review: {payload.status.value}" + (f" - {payload.rejection_reason}" if payload.rejection_reason else ""),
    )

    # Send notification and email
    if payload.status.value == "VERIFIED":
        send_notification_and_email(
            db=db,
            user=user,
            title="KYC Verification Approved",
            message="Your KYC verification has been approved. You can now access all platform features.",
            notification_type="kyc",
            email_subject="KYC Verification Approved - Zenfort Markets",
            email_html=f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
              <h2 style="color:#1a1a3e;">KYC Verification Approved</h2>
              <p>Hi {user.full_name},</p>
              <p>Your KYC verification has been successfully approved.</p>
              <p>You can now access all platform features including deposits, withdrawals, and investments.</p>
              <hr/>
              <small style="color:#888;">Zenfort Markets</small>
            </div>
            """,
        )
    elif payload.status.value == "REJECTED":
        reason = payload.rejection_reason or "Please resubmit your documents."
        send_notification_and_email(
            db=db,
            user=user,
            title="KYC Verification Rejected",
            message=f"Your KYC verification was rejected. Reason: {reason}",
            notification_type="kyc",
            email_subject="KYC Verification Rejected - Zenfort Markets",
            email_html=f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
              <h2 style="color:#1a1a3e;">KYC Verification Rejected</h2>
              <p>Hi {user.full_name},</p>
              <p>Your KYC verification was rejected.</p>
              <p><strong>Reason:</strong> {reason}</p>
              <p>Please review the requirements and resubmit your documents.</p>
              <hr/>
              <small style="color:#888;">Zenfort Markets</small>
            </div>
            """,
        )

    return user


# ──────────────────────────────────────────────
# GET /api/admin/deposits/pending — List pending deposits
# ──────────────────────────────────────────────
@router.get("/deposits/pending", response_model=List[TransactionOut])
def list_pending_deposits(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all pending deposit transactions ordered by created_at descending."""
    return (
        db.query(Transaction)
        .filter(Transaction.tx_type == "deposit", Transaction.status == "pending")
        .order_by(Transaction.created_at.desc())
        .all()
    )


# ──────────────────────────────────────────────
# PATCH /api/admin/deposits/{transaction_id}/review — Review deposit
# ──────────────────────────────────────────────
@router.patch("/deposits/{transaction_id}/review", response_model=TransactionOut)
def review_deposit(
    transaction_id: str,
    payload: AdminDepositReviewRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Review and approve/reject a pending deposit transaction.

    If approved: Update transaction to "completed" and credit user's main wallet.
    If rejected: Update transaction to "rejected" with rejection reason.
    """
    # Fetch the pending transaction
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if tx.tx_type != "deposit":
        raise HTTPException(status_code=400, detail="Transaction is not a deposit.")
    if tx.status != "pending":
        raise HTTPException(status_code=400, detail=f"Transaction is not pending. Current status: {tx.status}")

    # Process based on review status
    if payload.status in ["approved", "completed"]:
        # Get the wallet to credit
        wallet = db.query(Wallet).filter(Wallet.id == tx.receiver_wallet_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Associated wallet not found.")

        # Get the user
        user = db.query(User).filter(User.id == wallet.user_id).first()

        # Credit the wallet
        wallet.balance += tx.amount
        tx.status = "completed"

        db.commit()
        db.refresh(tx)

        # Audit log
        _create_audit_log(
            db=db,
            admin_id=admin.id,
            action="APPROVE_DEPOSIT",
            target_user_id=str(user.id) if user else None,
            details=f"Approved deposit {tx.id}: {tx.amount} {tx.currency}",
        )

        # Send notification and email
        if user:
            send_notification_and_email(
                db=db,
                user=user,
                title="Deposit Approved",
                message=f"Your deposit of {tx.amount} {tx.currency} has been approved and credited to your wallet.",
                notification_type="deposit",
                email_subject=f"Deposit Approved - {tx.amount} {tx.currency}",
                email_html=f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
                  <h2 style="color:#1a1a3e;">Deposit Approved</h2>
                  <p>Hi {user.full_name},</p>
                  <p>Your deposit of <strong>{tx.amount} {tx.currency}</strong> has been approved.</p>
                  <p>The funds have been credited to your wallet.</p>
                  <hr/>
                  <small style="color:#888;">Zenfort Markets</small>
                </div>
                """,
            )

    elif payload.status == "rejected":
        tx.status = "rejected"
        if payload.rejection_reason:
            tx.rejection_reason = payload.rejection_reason

        # Get the user
        wallet = db.query(Wallet).filter(Wallet.id == tx.receiver_wallet_id).first()
        user = db.query(User).filter(User.id == wallet.user_id).first() if wallet else None

        db.commit()
        db.refresh(tx)

        # Audit log
        _create_audit_log(
            db=db,
            admin_id=admin.id,
            action="REJECT_DEPOSIT",
            target_user_id=str(user.id) if user else None,
            details=f"Rejected deposit {tx.id}: {tx.amount} {tx.currency} - {payload.rejection_reason or 'No reason'}",
        )

        # Send notification and email
        if user:
            reason = payload.rejection_reason or "Please contact support for details."
            send_notification_and_email(
                db=db,
                user=user,
                title="Deposit Rejected",
                message=f"Your deposit of {tx.amount} {tx.currency} was rejected. Reason: {reason}",
                notification_type="deposit",
                email_subject=f"Deposit Rejected - {tx.amount} {tx.currency}",
                email_html=f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
                  <h2 style="color:#1a1a3e;">Deposit Rejected</h2>
                  <p>Hi {user.full_name},</p>
                  <p>Your deposit of <strong>{tx.amount} {tx.currency}</strong> was rejected.</p>
                  <p><strong>Reason:</strong> {reason}</p>
                  <p>Please contact support if you have any questions.</p>
                  <hr/>
                  <small style="color:#888;">Zenfort Markets</small>
                </div>
                """,
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'approved', 'completed', or 'rejected'.")

    return tx


# ──────────────────────────────────────────────
# GET /api/admin/withdrawals/pending — List pending withdrawals
# ──────────────────────────────────────────────
@router.get("/withdrawals/pending", response_model=List[TransactionOut])
def list_pending_withdrawals(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all pending withdrawal transactions ordered by created_at descending."""
    return (
        db.query(Transaction)
        .filter(Transaction.tx_type == "withdrawal", Transaction.status == "pending")
        .order_by(Transaction.created_at.desc())
        .all()
    )


# ──────────────────────────────────────────────
# PATCH /api/admin/withdrawals/{transaction_id}/review — Review withdrawal
# ──────────────────────────────────────────────
@router.patch("/withdrawals/{transaction_id}/review", response_model=TransactionOut)
def review_withdrawal(
    transaction_id: str,
    payload: AdminWithdrawalReviewRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Review and approve/reject a pending withdrawal transaction.

    If approved: Update transaction to "completed" and save payout_tx_hash.
    If rejected: Update transaction to "rejected", attach rejection_reason, and refund the amount to user's Main Wallet.
    """
    # Fetch the pending transaction
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if tx.tx_type != "withdrawal":
        raise HTTPException(status_code=400, detail="Transaction is not a withdrawal.")
    if tx.status != "pending":
        raise HTTPException(status_code=400, detail=f"Transaction is not pending. Current status: {tx.status}")

    # Get the wallet that was debited
    wallet = db.query(Wallet).filter(Wallet.id == tx.sender_wallet_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Associated wallet not found.")

    # Get the user
    user = db.query(User).filter(User.id == wallet.user_id).first()

    # Process based on review status
    if payload.status in ["approved", "completed"]:
        # Approve: Mark as completed and save payout reference
        tx.status = "completed"
        if payload.payout_tx_hash:
            tx.payout_tx_hash = payload.payout_tx_hash

        db.commit()
        db.refresh(tx)

        # Audit log
        _create_audit_log(
            db=db,
            admin_id=admin.id,
            action="APPROVE_WITHDRAWAL",
            target_user_id=str(user.id) if user else None,
            details=f"Approved withdrawal {tx.id}: {tx.amount} {tx.currency}",
        )

        # Send notification and email
        if user:
            send_notification_and_email(
                db=db,
                user=user,
                title="Withdrawal Approved",
                message=f"Your withdrawal of {tx.amount} {tx.currency} has been approved and processed.",
                notification_type="withdrawal",
                email_subject=f"Withdrawal Approved - {tx.amount} {tx.currency}",
                email_html=f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
                  <h2 style="color:#1a1a3e;">Withdrawal Approved</h2>
                  <p>Hi {user.full_name},</p>
                  <p>Your withdrawal of <strong>{tx.amount} {tx.currency}</strong> has been approved.</p>
                  <p>The funds have been sent to your withdrawal address.</p>
                  <hr/>
                  <small style="color:#888;">Zenfort Markets</small>
                </div>
                """,
            )

    elif payload.status == "rejected":
        # Reject: Refund the amount back to the wallet
        wallet.balance += tx.amount
        tx.status = "rejected"
        if payload.rejection_reason:
            tx.rejection_reason = payload.rejection_reason

        db.commit()
        db.refresh(tx)

        # Audit log
        _create_audit_log(
            db=db,
            admin_id=admin.id,
            action="REJECT_WITHDRAWAL",
            target_user_id=str(user.id) if user else None,
            details=f"Rejected withdrawal {tx.id}: {tx.amount} {tx.currency} - {payload.rejection_reason or 'No reason'}",
        )

        # Send notification and email
        if user:
            reason = payload.rejection_reason or "Please contact support for details."
            send_notification_and_email(
                db=db,
                user=user,
                title="Withdrawal Rejected",
                message=f"Your withdrawal of {tx.amount} {tx.currency} was rejected. Reason: {reason}. The amount has been refunded to your wallet.",
                notification_type="withdrawal",
                email_subject=f"Withdrawal Rejected - {tx.amount} {tx.currency}",
                email_html=f"""
                <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
                  <h2 style="color:#1a1a3e;">Withdrawal Rejected</h2>
                  <p>Hi {user.full_name},</p>
                  <p>Your withdrawal of <strong>{tx.amount} {tx.currency}</strong> was rejected.</p>
                  <p><strong>Reason:</strong> {reason}</p>
                  <p>The amount has been refunded to your wallet.</p>
                  <hr/>
                  <small style="color:#888;">Zenfort Markets</small>
                </div>
                """,
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'approved', 'completed', or 'rejected'.")

    return tx


# ──────────────────────────────────────────────
# POST /api/admin/plans/ — Create an investment plan
# ──────────────────────────────────────────────
@router.post("/plans/", response_model=InvestmentPlanResponse, status_code=status.HTTP_201_CREATED)
def create_investment_plan(
    payload: InvestmentPlanCreate,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Create a new investment plan template."""
    existing = db.query(InvestmentPlan).filter(InvestmentPlan.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An investment plan named '{payload.name}' already exists.",
        )
    plan = InvestmentPlan(
        name=payload.name,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        daily_roi_percent=payload.daily_roi_percent,
        duration_days=payload.duration_days,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


# ──────────────────────────────────────────────
# GET /api/admin/plans/ — List all investment plans
# ──────────────────────────────────────────────
@router.get("/plans/", response_model=List[InvestmentPlanResponse])
def list_all_plans(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List all investment plans (active and inactive)."""
    return (
        db.query(InvestmentPlan)
        .order_by(InvestmentPlan.created_at.asc())
        .all()
    )


# ──────────────────────────────────────────────
# PATCH /api/admin/plans/{plan_id} — Update plan / toggle is_active
# ──────────────────────────────────────────────
@router.patch("/plans/{plan_id}", response_model=InvestmentPlanResponse)
def update_investment_plan(
    plan_id: str,
    payload: InvestmentPlanUpdate,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Partially update an investment plan. Supports toggling is_active."""
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment plan not found.")

    # Check name uniqueness if name is being changed
    if payload.name is not None and payload.name != plan.name:
        conflict = db.query(InvestmentPlan).filter(InvestmentPlan.name == payload.name).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An investment plan named '{payload.name}' already exists.",
            )
        plan.name = payload.name

    if payload.min_amount is not None:
        plan.min_amount = payload.min_amount
    if payload.max_amount is not None:
        plan.max_amount = payload.max_amount
    if payload.daily_roi_percent is not None:
        plan.daily_roi_percent = payload.daily_roi_percent
    if payload.duration_days is not None:
        plan.duration_days = payload.duration_days
    if payload.is_active is not None:
        plan.is_active = payload.is_active

    db.commit()
    db.refresh(plan)
    return plan


# ──────────────────────────────────────────────
# POST /api/admin/investments/process-roi — ROI Staking Engine
# ──────────────────────────────────────────────
@router.post("/investments/process-roi", status_code=status.HTTP_200_OK)
def process_roi(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    ROI Staking Distribution Engine.

    For every active UserInvestment:
    1. Calculate daily_profit = amount_invested * (daily_roi_percent / 100).
    2. Credit the user's Profit Wallet.
    3. Increment total_earned on the investment.
    4. If maturity_date has been reached:
       a. Transition investment status to 'completed'.
       b. Return the principal (amount_invested) to the user's Main Wallet.

    All mutations are flushed and committed in a single transaction.
    Returns a summary dict with counts of processed and matured investments.
    """
    now = datetime.now(timezone.utc)
    active_investments = (
        db.query(UserInvestment)
        .filter(UserInvestment.status == "active")
        .all()
    )

    processed_count = 0
    matured_count = 0

    for inv in active_investments:
        # Fetch profit wallet
        profit_wallet = (
            db.query(Wallet)
            .filter(Wallet.user_id == inv.user_id, Wallet.wallet_type == "profit")
            .first()
        )
        if not profit_wallet:
            # Skip if wallet is missing (shouldn't happen in normal operation)
            continue

        daily_profit = Decimal(str(inv.amount_invested)) * (
            Decimal(str(inv.daily_roi_percent)) / Decimal("100")
        )

        # Credit daily ROI to Profit Wallet
        profit_wallet.balance += daily_profit
        inv.total_earned = Decimal(str(inv.total_earned)) + daily_profit

        # Record ROI credit transaction
        roi_tx = Transaction(
            receiver_wallet_id=profit_wallet.id,
            amount=daily_profit,
            currency=profit_wallet.currency,
            tx_type="roi_credit",
            description=f"Daily ROI for investment {inv.id}",
            status="completed",
        )
        db.add(roi_tx)
        processed_count += 1

        # Check maturity (make maturity_date timezone-aware for comparison)
        maturity = inv.maturity_date
        if maturity.tzinfo is None:
            maturity = maturity.replace(tzinfo=timezone.utc)

        if now >= maturity:
            # Mark investment as completed
            inv.status = "completed"
            matured_count += 1

            # Return principal to Main Wallet
            main_wallet = (
                db.query(Wallet)
                .filter(Wallet.user_id == inv.user_id, Wallet.wallet_type == "main")
                .first()
            )
            if main_wallet:
                main_wallet.balance += Decimal(str(inv.amount_invested))
                principal_tx = Transaction(
                    receiver_wallet_id=main_wallet.id,
                    amount=inv.amount_invested,
                    currency=main_wallet.currency,
                    tx_type="principal_return",
                    description=f"Principal returned for matured investment {inv.id}",
                    status="completed",
                )
                db.add(principal_tx)

    db.commit()
    return {
        "status": "ok",
        "processed": processed_count,
        "matured": matured_count,
        "timestamp": now.isoformat(),
    }


# ──────────────────────────────────────────────
# GET /api/admin/audit-logs — List system audit logs
# ──────────────────────────────────────────────
@router.get("/audit-logs", response_model=List[AuditLogResponse])
def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return system-wide administrative action logs ordered by latest first."""
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
