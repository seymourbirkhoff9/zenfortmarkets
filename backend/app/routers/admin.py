"""
app/routers/admin.py — Admin-only management endpoints
"""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Wallet, Transaction
from app.schemas import UserOut, AdminCreditRequest, TransactionOut
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
