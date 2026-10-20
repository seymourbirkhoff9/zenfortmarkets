from __future__ import annotations
"""
app/services/ledger.py — helpers for safe balance mutations.

Every balance change must happen on a row locked with SELECT ... FOR UPDATE,
otherwise two concurrent requests (double-click, two tabs, retry) can both read
the same balance and overdraw it.
"""
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Wallet

CENT = Decimal("0.01")


def money(value) -> Decimal:
    """Normalise to 2dp, the precision of the USD ledger."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def lock_wallet(db: Session, user_id, wallet_type: str) -> Wallet:
    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == user_id, Wallet.wallet_type == wallet_type)
        .with_for_update()
        .populate_existing()   # re-read the row even if it is already in the session
        .first()
    )
    if not wallet:
        raise HTTPException(status_code=404, detail=f"{wallet_type.title()} wallet not found.")
    return wallet


def lock_wallet_by_id(db: Session, wallet_id) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).with_for_update().populate_existing().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")
    return wallet


def debit(wallet: Wallet, amount: Decimal, message: str = "Insufficient balance.") -> None:
    if wallet.balance < amount:
        raise HTTPException(status_code=422, detail=message)
    wallet.balance = wallet.balance - amount


def credit(wallet: Wallet, amount: Decimal) -> None:
    wallet.balance = wallet.balance + amount
