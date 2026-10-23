"""
app/routers/wallets.py — balances, internal moves, P2P, deposits and withdrawals.

Money model: every wallet and ledger entry is in settings.BASE_CURRENCY (USD).
Crypto assets/networks are payment rails configured by the admin
(see PaymentMethod); the user states the USD value they sent or want paid out.
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import PaymentMethod, Transaction, User, Wallet
from app.schemas import (
    DepositCreateRequest, ExchangeRequest, P2PTransferRequest, PaymentMethodOut,
    TransactionOut, WalletOut, WalletTransferRequest, WithdrawalCreateRequest,
    AdminTransactionOut,
)
from app.security import get_current_user
from app.services.admin_alerts import notify_admins
from app.services.ledger import credit, debit, lock_wallet, money
from app.services.notification_service import queue_email
from app.services.email_templates import render_email, usd
from app.services import storage
from app.services.serializers import tx_view
from app.utils.uploads import IMAGE_TYPES, validate_data_url

router = APIRouter(prefix="/api/wallets", tags=["Wallets"])
CUR = settings.BASE_CURRENCY


def _own_wallet_ids(db: Session, user_id) -> list:
    return [w for (w,) in db.query(Wallet.id).filter(Wallet.user_id == user_id).all()]


def _require_not_blocked(user: User) -> None:
    if user.is_blocked:
        raise HTTPException(status_code=403, detail="Your account is restricted. Contact support.")


# ── Balances ──────────────────────────────────
@router.get("", response_model=List[WalletOut])
@router.get("/", response_model=List[WalletOut], include_in_schema=False)
def list_wallets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (db.query(Wallet).filter(Wallet.user_id == current_user.id)
            .order_by(Wallet.wallet_type.asc()).all())


@router.get("/payment-methods", response_model=List[PaymentMethodOut])
def list_payment_methods(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Active crypto rails the user can deposit with or withdraw to."""
    return (db.query(PaymentMethod).filter(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.asset, PaymentMethod.network).all())


# ── Main ↔ Profit ─────────────────────────────
def _move_between_own_wallets(db: Session, user: User, src: str, dst: str, amount: Decimal) -> Transaction:
    _require_not_blocked(user)
    amount = money(amount)
    # Lock in a stable order (main before profit) so concurrent moves can't deadlock.
    first, second = sorted([src, dst])
    locked = {first: lock_wallet(db, user.id, first), second: lock_wallet(db, user.id, second)}
    debit(locked[src], amount, f"Not enough funds in your {src.title()} wallet.")
    credit(locked[dst], amount)
    tx = Transaction(
        sender_wallet_id=locked[src].id, receiver_wallet_id=locked[dst].id,
        amount=amount, currency=CUR, tx_type="transfer", status="completed",
        description=f"{src.title()} wallet → {dst.title()} wallet",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.post("/transfer", response_model=TransactionOut, status_code=201)
def transfer_between_wallets(payload: WalletTransferRequest,
                             current_user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    tx = _move_between_own_wallets(db, current_user, payload.from_wallet, payload.to_wallet, payload.amount)
    return tx_view(tx)


@router.post("/exchange", response_model=TransactionOut, status_code=201, deprecated=True)
def exchange_between_wallets(payload: ExchangeRequest,
                             current_user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """Deprecated alias of /transfer, kept for older clients."""
    tx = _move_between_own_wallets(db, current_user, payload.source_wallet_type,
                                   payload.destination_wallet_type, payload.amount)
    return tx_view(tx)


# ── P2P ───────────────────────────────────────
@router.post("/p2p-transfer", response_model=TransactionOut, status_code=201)
def p2p_transfer(payload: P2PTransferRequest,
                 current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Send funds from your Main wallet to another user's Main wallet."""
    _require_not_blocked(current_user)
    if payload.recipient_email.lower() == current_user.email.lower():
        raise HTTPException(status_code=400, detail="You can't send funds to yourself.")
    recipient = db.query(User).filter(User.email == payload.recipient_email).first()
    if not recipient or not recipient.is_active:
        raise HTTPException(status_code=404, detail="No active account uses that email.")

    # Handle currency conversion if input_currency is provided
    input_amount = None
    input_currency = None
    fx_rate = None

    if payload.input_currency and payload.input_currency.upper() != "USD":
        from app.services.fx_service import to_usd
        input_amount = payload.amount
        input_currency = payload.input_currency.upper().strip()
        amount, fx_rate = to_usd(db, input_amount, input_currency)
    else:
        amount = money(payload.amount)

    sender_w = db.query(Wallet).filter(Wallet.user_id == current_user.id, Wallet.wallet_type == "main").first()
    recip_w = db.query(Wallet).filter(Wallet.user_id == recipient.id, Wallet.wallet_type == "main").first()
    if not sender_w or not recip_w:
        raise HTTPException(status_code=404, detail="Main wallet not found.")
    # Lock both rows in id order to avoid deadlocks between opposite transfers.
    for w in sorted([sender_w, recip_w], key=lambda w: str(w.id)):
        db.query(Wallet).filter(Wallet.id == w.id).with_for_update().populate_existing().one()

    debit(sender_w, amount, "Not enough funds in your Main wallet.")
    credit(recip_w, amount)
    tx = Transaction(
        sender_wallet_id=sender_w.id, receiver_wallet_id=recip_w.id, amount=amount,
        currency=CUR, tx_type="p2p", status="completed",
        description=(payload.description or "").strip()[:200] or f"Transfer to {recipient.email}",
        input_amount=input_amount, input_currency=input_currency, fx_rate=fx_rate,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    # Format amount with currency if input_currency is set
    amount_text = usd(amount)
    if tx.input_currency and tx.input_amount:
        amount_text = f"{tx.input_amount:,.2f} {tx.input_currency} (~{usd(amount)})"
    queue_email(recipient.email, f"You received {usd(amount)}",
                render_email("Funds received", recipient.full_name,
                             [f"{current_user.full_name} sent you {amount_text}.",
                              "It is already in your Main wallet."]))
    return tx_view(tx, [sender_w.id])


# ── History ───────────────────────────────────
@router.get("/transactions", response_model=List[TransactionOut])
def list_transactions(
    tx_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ids = _own_wallet_ids(db, current_user.id)
    q = db.query(Transaction).filter(
        Transaction.sender_wallet_id.in_(ids) | Transaction.receiver_wallet_id.in_(ids))
    if tx_type:
        q = q.filter(Transaction.tx_type == tx_type)
    if status:
        q = q.filter(Transaction.status == status)
    if start_date:
        q = q.filter(Transaction.created_at >= start_date)
    if end_date:
        q = q.filter(Transaction.created_at <= end_date)
    rows = q.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()
    return [tx_view(t, ids) for t in rows]


@router.get("/transactions/{tx_id}", response_model=AdminTransactionOut)
def get_transaction(tx_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = _own_wallet_ids(db, current_user.id)
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx or (tx.sender_wallet_id not in ids and tx.receiver_wallet_id not in ids):
        raise HTTPException(status_code=404, detail="Transaction not found.")
    data = tx_view(tx, ids)
    data["proof_image_url"] = storage.url_for(tx.proof_image_url)     # short-lived link for private files
    return data


# ── Deposits ──────────────────────────────────
def _get_method(db: Session, method_id) -> PaymentMethod:
    m = db.query(PaymentMethod).filter(PaymentMethod.id == method_id,
                                       PaymentMethod.is_active.is_(True)).first()
    if not m:
        raise HTTPException(status_code=404, detail="That payment method is not available.")
    return m


@router.post("/deposits", response_model=TransactionOut, status_code=201)
@router.post("/deposits/", response_model=TransactionOut, status_code=201, include_in_schema=False)
def create_deposit(payload: DepositCreateRequest,
                   current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Record a deposit the user has already sent. It stays pending until an admin reviews it."""
    _require_not_blocked(current_user)
    if not current_user.can_deposit:
        raise HTTPException(status_code=403, detail="Deposits are turned off for your account.")
    method = _get_method(db, payload.payment_method_id)
    if not method.deposit_enabled:
        raise HTTPException(status_code=400, detail=f"Deposits via {method.asset} ({method.network}) are paused.")

    # Handle currency conversion if input_currency is provided
    input_amount = None
    input_currency = None
    fx_rate = None

    if payload.input_currency and payload.input_currency.upper() != "USD":
        from app.services.fx_service import to_usd
        input_amount = payload.amount
        input_currency = payload.input_currency.upper().strip()
        amount, fx_rate = to_usd(db, input_amount, input_currency)
    else:
        amount = money(payload.amount)

    if amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive.")
    if amount < money(method.min_deposit):
        raise HTTPException(status_code=422, detail=f"The minimum deposit for this method is {usd(method.min_deposit)}.")

    tx_hash = (payload.tx_hash or "").strip() or None
    if tx_hash:
        dup = db.query(Transaction.id).filter(
            Transaction.tx_type == "deposit", Transaction.tx_hash == tx_hash,
            Transaction.status != "rejected").first()
        if dup:
            raise HTTPException(status_code=409, detail="A deposit with this transaction hash was already submitted.")
    proof = None
    if payload.proof_image_url:
        valid = validate_data_url(payload.proof_image_url, IMAGE_TYPES, "Payment screenshot")
        proof = storage.store(valid, f"proofs/{current_user.id}", private=True)

    main = db.query(Wallet).filter(Wallet.user_id == current_user.id, Wallet.wallet_type == "main").first()
    if not main:
        raise HTTPException(status_code=404, detail="Main wallet not found.")

    label = f"{method.asset} ({method.network})"
    tx = Transaction(
        receiver_wallet_id=main.id, amount=amount, currency=CUR, tx_type="deposit", status="pending",
        description=f"Deposit via {label}", gateway_name=label, asset=method.asset,
        network=method.network, payment_method_id=method.id, tx_hash=tx_hash, proof_image_url=proof,
        input_amount=input_amount, input_currency=input_currency, fx_rate=fx_rate,
    )
    db.add(tx)
    notify_admins(db, "Deposit awaiting review",
                  f"{current_user.email} reported a {usd(amount)} deposit via {label}.", "deposit")
    db.commit()
    db.refresh(tx)
    return tx_view(tx, [main.id])


# ── Withdrawals ───────────────────────────────
@router.post("/withdrawals", response_model=TransactionOut, status_code=201)
@router.post("/withdrawals/", response_model=TransactionOut, status_code=201, include_in_schema=False)
def create_withdrawal(payload: WithdrawalCreateRequest,
                      current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """
    Request a payout to an external crypto address.

    The full amount is held (debited) from the Main wallet immediately so it
    can't be spent twice; it is returned if the admin rejects the request.
    The admin sends (amount − fee) worth of the chosen asset.
    """
    _require_not_blocked(current_user)
    if not current_user.can_withdraw:
        raise HTTPException(status_code=403, detail="Withdrawals are turned off for your account.")
    if settings.REQUIRE_KYC_FOR_WITHDRAWAL and current_user.kyc_status.value != "VERIFIED":
        raise HTTPException(status_code=403, detail="Verify your identity before withdrawing.")
    method = _get_method(db, payload.payment_method_id)
    if not method.withdraw_enabled:
        raise HTTPException(status_code=400, detail=f"Withdrawals via {method.asset} ({method.network}) are paused.")

    # Validate withdrawal_address based on method type
    # Default to crypto if method_type is not set
    method_type = getattr(method, 'method_type', None) or 'crypto'
    if method_type == 'crypto':
        if not payload.withdrawal_address:
            raise HTTPException(status_code=422, detail="Wallet address is required for crypto withdrawals.")
        addr = payload.withdrawal_address.strip()
        if not (10 <= len(addr) <= 128) or any(c.isspace() for c in addr):
            raise HTTPException(status_code=422, detail="Enter a valid wallet address (10-128 characters, no spaces).")
    elif method_type == 'bank':
        # Bank transfers use withdrawal_details for bank account info
        if not payload.withdrawal_details:
            raise HTTPException(status_code=422, detail="Bank account details are required for bank withdrawals.")

    # Handle currency conversion if input_currency is provided
    input_amount = None
    input_currency = None
    fx_rate = None

    if payload.input_currency and payload.input_currency.upper() != "USD":
        from app.services.fx_service import to_usd
        input_amount = payload.amount
        input_currency = payload.input_currency.upper().strip()
        amount, fx_rate = to_usd(db, input_amount, input_currency)
    else:
        amount = money(payload.amount)

    fee = money(method.withdrawal_fee)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive.")
    if amount < money(method.min_withdrawal):
        raise HTTPException(status_code=422, detail=f"The minimum withdrawal for this method is {usd(method.min_withdrawal)}.")
    if amount <= fee:
        raise HTTPException(status_code=422, detail=f"Amount must be more than the {usd(fee)} network fee.")

    main = lock_wallet(db, current_user.id, "main")
    debit(main, amount, "Not enough funds in your Main wallet.")

    label = f"{method.asset} ({method.network})"
    tx = Transaction(
        sender_wallet_id=main.id, amount=amount, fee=fee, currency=CUR, tx_type="withdrawal",
        status="pending", description=f"Withdrawal to {label}", gateway_name=label,
        asset=method.asset, network=method.network, payment_method_id=method.id,
        withdrawal_address=payload.withdrawal_address,
        withdrawal_details=(payload.withdrawal_details or "").strip()[:500] or None,
        input_amount=input_amount, input_currency=input_currency, fx_rate=fx_rate,
    )
    db.add(tx)
    notify_admins(db, "Withdrawal awaiting payout",
                  f"{current_user.email} requested {usd(amount)} to {label}.", "withdrawal")
    db.commit()
    db.refresh(tx)
    return tx_view(tx, [main.id])
