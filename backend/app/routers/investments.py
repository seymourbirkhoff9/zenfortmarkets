"""
app/routers/investments.py — Phase 4: Investment Plans & User Investments
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Wallet, InvestmentPlan, UserInvestment, Transaction
from app.schemas import InvestmentPlanResponse, InvestRequest, UserInvestmentResponse
from app.security import get_current_user
from app.services.referral_service import process_referral_milestone

router = APIRouter(prefix="/api/investments", tags=["Investments"])


# ──────────────────────────────────────────────
# GET /api/investments/plans — List active plans (user-facing)
# ──────────────────────────────────────────────
@router.get("/plans", response_model=List[InvestmentPlanResponse])
def list_active_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all currently active investment plans visible to authenticated users."""
    return (
        db.query(InvestmentPlan)
        .filter(InvestmentPlan.is_active.is_(True))
        .order_by(InvestmentPlan.created_at.asc())
        .all()
    )


# ──────────────────────────────────────────────
# POST /api/investments/ — Subscribe to a plan (wallet-first)
# ──────────────────────────────────────────────
@router.post("/", response_model=UserInvestmentResponse, status_code=status.HTTP_201_CREATED)
def create_investment(
    payload: InvestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Subscribe to an investment plan, debiting the user's Main Wallet.

    Guards (in order):
    1. User must not be blocked.
    2. Plan must exist and be active.
    3. Amount must be within plan min/max range.
    4. Main Wallet balance must be sufficient.
    All mutations are committed atomically.
    """
    # Guard 1 — blocked user
    if current_user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is blocked. Contact support.",
        )

    # Guard 2 — plan exists and is active
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == payload.plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment plan not found.")
    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This investment plan is currently inactive.",
        )

    amount = Decimal(str(payload.amount))

    # Guard 3 — amount within plan bounds
    if amount < plan.min_amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Minimum investment for this plan is {plan.min_amount}.",
        )
    if amount > plan.max_amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum investment for this plan is {plan.max_amount}.",
        )

    # Guard 4 — sufficient Main Wallet balance
    main_wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == current_user.id, Wallet.wallet_type == "main")
        .first()
    )
    if not main_wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Main wallet not found.")
    if main_wallet.balance < amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient balance in your Main Wallet.",
        )

    # Atomic: debit wallet, create investment, record ledger entry
    now = datetime.now(timezone.utc)
    maturity = now + timedelta(days=plan.duration_days)

    main_wallet.balance -= amount

    investment = UserInvestment(
        user_id=current_user.id,
        plan_id=plan.id,
        amount_invested=amount,
        daily_roi_percent=plan.daily_roi_percent,   # snapshot
        duration_days=plan.duration_days,           # snapshot
        total_earned=Decimal("0.0"),
        status="active",
        start_date=now,
        maturity_date=maturity,
    )
    db.add(investment)

    tx = Transaction(
        sender_wallet_id=main_wallet.id,
        amount=amount,
        currency=main_wallet.currency,
        tx_type="investment",
        description=f"Investment in plan: {plan.name}",
        status="completed",
    )
    db.add(tx)

    db.commit()
    db.refresh(investment)

    # Process referral milestone (first investment)
    process_referral_milestone(db, current_user, "first_investment", amount)

    return investment


# ──────────────────────────────────────────────
# GET /api/investments/my-investments — List caller's investments
# ──────────────────────────────────────────────
@router.get("/my-investments", response_model=List[UserInvestmentResponse])
def my_investments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all investments (active & historical) for the authenticated user."""
    return (
        db.query(UserInvestment)
        .filter(UserInvestment.user_id == current_user.id)
        .order_by(UserInvestment.created_at.desc())
        .all()
    )
