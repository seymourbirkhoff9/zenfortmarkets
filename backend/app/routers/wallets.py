"""
app/routers/wallets.py — Wallet balance, exchange, and P2P transfer endpoints
"""
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Wallet, Transaction
from app.schemas import (
    WalletOut,
    ExchangeRequest,
    P2PTransferRequest,
    TransactionOut,
    DepositCreateRequest,
)
from app.security import get_current_user
from app.services.email import send_p2p_transfer_notification

router = APIRouter(prefix="/api/wallets", tags=["Wallets"])


def _get_wallet(db: Session, user_id, wallet_type: str) -> Wallet:
    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == user_id, Wallet.wallet_type == wallet_type)
        .first()
    )
    if not wallet:
        raise HTTPException(status_code=404, detail=f"{wallet_type.title()} wallet not found.")
    return wallet


# ──────────────────────────────────────────────
# GET /api/wallets/
# ──────────────────────────────────────────────
@router.get("/", response_model=List[WalletOut])
def list_wallets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all wallets belonging to the current user."""
    return db.query(Wallet).filter(Wallet.user_id == current_user.id).all()


# ──────────────────────────────────────────────
# POST /api/wallets/exchange
# ──────────────────────────────────────────────
@router.post("/exchange", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def exchange_between_wallets(
    payload: ExchangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atomically move funds between the user's own Main ↔ Profit wallets."""
    source = _get_wallet(db, current_user.id, payload.source_wallet_type)
    destination = _get_wallet(db, current_user.id, payload.destination_wallet_type)

    if source.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient balance in source wallet.",
        )

    source.balance -= payload.amount
    destination.balance += payload.amount

    tx = Transaction(
        sender_wallet_id=source.id,
        receiver_wallet_id=destination.id,
        amount=payload.amount,
        currency=source.currency,
        tx_type="transfer",
        description=f"Internal exchange: {payload.source_wallet_type} → {payload.destination_wallet_type}",
        status="completed",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


# ──────────────────────────────────────────────
# POST /api/wallets/p2p-transfer
# ──────────────────────────────────────────────
@router.post("/p2p-transfer", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def p2p_transfer(
    payload: P2PTransferRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send funds from the current user's Main wallet to another user identified by email."""
    if payload.recipient_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot transfer funds to yourself.",
        )

    recipient = db.query(User).filter(User.email == payload.recipient_email).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found.")
    if not recipient.is_active:
        raise HTTPException(status_code=403, detail="Recipient account is inactive.")

    sender_wallet = _get_wallet(db, current_user.id, "main")
    recipient_wallet = _get_wallet(db, recipient.id, "main")

    if sender_wallet.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient balance.",
        )

    sender_wallet.balance -= payload.amount
    recipient_wallet.balance += payload.amount

    tx = Transaction(
        sender_wallet_id=sender_wallet.id,
        receiver_wallet_id=recipient_wallet.id,
        amount=payload.amount,
        currency=sender_wallet.currency,
        tx_type="p2p",
        description=payload.description or f"P2P transfer to {recipient.email}",
        status="completed",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    background_tasks.add_task(
        send_p2p_transfer_notification,
        sender_name=current_user.full_name,
        recipient_email=recipient.email,
        recipient_name=recipient.full_name,
        amount=str(payload.amount),
        currency=sender_wallet.currency,
    )
    return tx


# ──────────────────────────────────────────────
# GET /api/wallets/transactions
# ──────────────────────────────────────────────
@router.get("/transactions", response_model=List[TransactionOut])
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all transactions for the current user (sent or received)."""
    wallet_ids = [w.id for w in db.query(Wallet).filter(Wallet.user_id == current_user.id).all()]
    txs = (
        db.query(Transaction)
        .filter(
            (Transaction.sender_wallet_id.in_(wallet_ids))
            | (Transaction.receiver_wallet_id.in_(wallet_ids))
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return txs


# ──────────────────────────────────────────────
# POST /api/deposits/ — Manual Deposit Submission
# ──────────────────────────────────────────────
@router.post("/deposits/", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_deposit(
    payload: DepositCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a manual deposit request for admin review.

    Checks if user is not blocked and can_deposit is True.
    Creates a pending transaction with gateway details.
    """
    # Verify user account status
    if current_user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is blocked. Contact support.",
        )
    if not current_user.can_deposit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deposits are disabled for this account.",
        )

    # Get user's main wallet
    main_wallet = _get_wallet(db, current_user.id, "main")

    # Create pending deposit transaction
    tx = Transaction(
        receiver_wallet_id=main_wallet.id,
        amount=payload.amount,
        currency=payload.currency,
        tx_type="deposit",
        description=f"Manual deposit via {payload.gateway_name}",
        status="pending",
        gateway_name=payload.gateway_name,
        tx_hash=payload.tx_hash,
        proof_image_url=payload.proof_image_url,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
