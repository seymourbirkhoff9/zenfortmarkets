"""
app/routers/investments.py — plans the admin publishes, and user subscriptions.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import InvestmentPlan, Transaction, User, UserInvestment
from app.schemas import InvestmentPlanResponse, InvestRequest, UserInvestmentResponse
from app.security import get_current_user
from app.services.email_templates import usd
from app.services.ledger import debit, lock_wallet, money
from app.services.referral_service import process_referral_milestone

router = APIRouter(prefix="/api/investments", tags=["Investments"])


def _view(inv: UserInvestment, plan_name: str | None) -> dict:
    data = {c: getattr(inv, c) for c in ("id", "plan_id", "amount_invested", "daily_roi_percent",
                                         "duration_days", "total_earned", "status", "start_date",
                                         "maturity_date", "created_at", "days_paid")}
    data["plan_name"] = plan_name
    return data


@router.get("/plans", response_model=List[InvestmentPlanResponse])
def list_active_plans(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (db.query(InvestmentPlan).filter(InvestmentPlan.is_active.is_(True))
            .order_by(InvestmentPlan.min_amount.asc()).all())


@router.post("/", response_model=UserInvestmentResponse, status_code=201)
def create_investment(payload: InvestRequest, current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    if current_user.is_blocked:
        raise HTTPException(status_code=403, detail="Your account is restricted. Contact support.")
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == payload.plan_id).first()
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="This plan isn't available.")
    amount = money(payload.amount)
    if amount < plan.min_amount or amount > plan.max_amount:
        raise HTTPException(status_code=422,
                            detail=f"Enter between {usd(plan.min_amount)} and {usd(plan.max_amount)}.")

    main = lock_wallet(db, current_user.id, "main")
    debit(main, amount, "Not enough funds in your Main wallet.")
    now = datetime.now(timezone.utc)
    inv = UserInvestment(
        user_id=current_user.id, plan_id=plan.id, amount_invested=amount,
        daily_roi_percent=plan.daily_roi_percent, duration_days=plan.duration_days,  # snapshot
        total_earned=Decimal("0"), status="active", start_date=now,
        maturity_date=now + timedelta(days=plan.duration_days), days_paid=0,
    )
    db.add(inv)
    db.add(Transaction(sender_wallet_id=main.id, amount=amount, currency=settings.BASE_CURRENCY,
                       tx_type="investment", status="completed", description=f"Invested in {plan.name}"))
    db.commit()
    db.refresh(inv)
    process_referral_milestone(db, current_user, "first_investment", amount)
    return _view(inv, plan.name)


@router.get("/my-investments", response_model=List[UserInvestmentResponse])
def my_investments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(UserInvestment, InvestmentPlan.name)
            .join(InvestmentPlan, InvestmentPlan.id == UserInvestment.plan_id)
            .filter(UserInvestment.user_id == current_user.id)
            .order_by(UserInvestment.created_at.desc()).all())
    return [_view(i, name) for i, name in rows]
