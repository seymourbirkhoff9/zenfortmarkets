"""
app/routers/wallets.py — Wallet balance, exchange, and P2P transfer endpoints
"""
from decimal import Decimal
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Wallet, Transaction
from app.schemas import (
    WalletOut,
    ExchangeRequest,
    P2PTransferRequest,
    TransactionOut,
    DepositCreateRequest,
    WithdrawalCreateRequest,
    WalletTransferRequest,
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
    tx_type: Optional[str] = Query(None, description="Filter by transaction type"),
    status: Optional[str] = Query(None, description="Filter by transaction status"),
    start_date: Optional[datetime] = Query(None, description="Filter transactions from this date onwards"),
    end_date: Optional[datetime] = Query(None, description="Filter transactions up to this date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all transactions for the current user (sent or received) with optional filters."""
    wallet_ids = [w.id for w in db.query(Wallet).filter(Wallet.user_id == current_user.id).all()]
    query = (
        db.query(Transaction)
        .filter(
            (Transaction.sender_wallet_id.in_(wallet_ids))
            | (Transaction.receiver_wallet_id.in_(wallet_ids))
        )
    )

    # Apply optional filters
    if tx_type:
        query = query.filter(Transaction.tx_type == tx_type)
    if status:
        query = query.filter(Transaction.status == status)
    if start_date:
        query = query.filter(Transaction.created_at >= start_date)
    if end_date:
        query = query.filter(Transaction.created_at <= end_date)

    txs = query.order_by(Transaction.created_at.desc()).all()
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


# ──────────────────────────────────────────────
# POST /api/withdrawals/ — Manual Withdrawal Submission
# ──────────────────────────────────────────────
@router.post("/withdrawals/", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_withdrawal(
    payload: WithdrawalCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a manual withdrawal request for admin review.

    Checks if user is not blocked and can_withdraw is True.
    Verifies sufficient balance in Main Wallet.
    Atomically debits the wallet and creates a pending withdrawal transaction.
    """
    # Verify user account status
    if current_user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is blocked. Contact support.",
        )
    if not current_user.can_withdraw:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Withdrawals are disabled for this account.",
        )

    # Get user's main wallet
    main_wallet = _get_wallet(db, current_user.id, "main")

    # Verify sufficient balance
    if main_wallet.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance in Main Wallet.",
        )

    # Atomically debit wallet and create withdrawal transaction
    main_wallet.balance -= payload.amount

    tx = Transaction(
        sender_wallet_id=main_wallet.id,
        amount=payload.amount,
        currency=payload.currency,
        tx_type="withdrawal",
        description=f"Withdrawal via {payload.gateway_name}",
        status="pending",
        gateway_name=payload.gateway_name,
        withdrawal_address=payload.withdrawal_address,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


# ──────────────────────────────────────────────
# POST /api/wallets/transfer — Transfer between own wallets
# ──────────────────────────────────────────────
@router.post("/transfer", response_model=List[TransactionOut], status_code=status.HTTP_201_CREATED)
def transfer_between_wallets(
    payload: WalletTransferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Transfer funds between the user's own Main and Profit wallets.
    Creates two ledger transactions: transfer_out and transfer_in.
    """
    # Get source wallet
    source_wallet = _get_wallet(db, current_user.id, payload.from_wallet)
    if not source_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{payload.from_wallet.capitalize()} wallet not found.",
        )

    # Get destination wallet
    dest_wallet = _get_wallet(db, current_user.id, payload.to_wallet)
    if not dest_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{payload.to_wallet.capitalize()} wallet not found.",
        )

    # Verify sufficient balance
    if source_wallet.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance in {payload.from_wallet.capitalize()} Wallet.",
        )

    # Atomic transfer: debit source, credit destination
    source_wallet.balance -= payload.amount
    dest_wallet.balance += payload.amount

    # Create transfer_out transaction
    tx_out = Transaction(
        sender_wallet_id=source_wallet.id,
        amount=payload.amount,
        currency=source_wallet.currency,
        tx_type="transfer",
        description=f"Transfer to {payload.to_wallet} wallet",
        status="completed",
    )
    db.add(tx_out)

    # Create transfer_in transaction
    tx_in = Transaction(
        receiver_wallet_id=dest_wallet.id,
        amount=payload.amount,
        currency=dest_wallet.currency,
        tx_type="transfer",
        description=f"Transfer from {payload.from_wallet} wallet",
        status="completed",
    )
    db.add(tx_in)

    db.commit()
    db.refresh(tx_out)
    db.refresh(tx_in)

    return [tx_out, tx_in]
