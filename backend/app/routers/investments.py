"""
app/routers/investments.py — Investment plan creation and management
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Investment, Wallet, Transaction
from app.schemas import InvestmentCreateRequest, InvestmentOut
from app.security import get_current_user

router = APIRouter(prefix="/api/investments", tags=["Investments"])


@router.post("/", response_model=InvestmentOut, status_code=status.HTTP_201_CREATED)
def create_investment(
    payload: InvestmentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Debit the user's Main wallet and open a new investment position.
    Funds are locked until maturity.
    """
    main_wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == current_user.id, Wallet.wallet_type == "main")
        .first()
    )
    if not main_wallet:
        raise HTTPException(status_code=404, detail="Main wallet not found.")
    if main_wallet.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient balance in Main wallet.",
        )

    # Debit main wallet
    main_wallet.balance -= payload.amount

    matures_at = datetime.now(timezone.utc) + timedelta(days=payload.duration_days)
    investment = Investment(
        user_id=current_user.id,
        plan_name=payload.plan_name,
        amount=payload.amount,
        currency=payload.currency,
        roi_percent=payload.roi_percent,
        status="active",
        matures_at=matures_at,
    )
    db.add(investment)

    # Record ledger entry (debit from main wallet, no receiver — locked)
    tx = Transaction(
        sender_wallet_id=main_wallet.id,
        amount=payload.amount,
        currency=payload.currency,
        tx_type="deposit",
        description=f"Investment: {payload.plan_name}",
        status="completed",
    )
    db.add(tx)
    db.commit()
    db.refresh(investment)
    return investment


@router.get("/", response_model=List[InvestmentOut])
def list_investments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Investment)
        .filter(Investment.user_id == current_user.id)
        .order_by(Investment.started_at.desc())
        .all()
    )


@router.get("/{investment_id}", response_model=InvestmentOut)
def get_investment(
    investment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = (
        db.query(Investment)
        .filter(
            Investment.id == investment_id,
            Investment.user_id == current_user.id,
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Investment not found.")
    return inv
