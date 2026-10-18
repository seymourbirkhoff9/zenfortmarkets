"""
app/routers/admin.py — Admin-only management endpoints
"""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Wallet, Transaction, KYCStatus
from app.schemas import UserOut, AdminCreditRequest, AdminDebitRequest, AdminUserStatusUpdate, AdminKYCReviewRequest, TransactionOut
from app.security import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"])


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
    return user
