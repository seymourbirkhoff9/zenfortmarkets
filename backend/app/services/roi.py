"""
app/services/roi.py — daily return accrual for active investments.

Idempotent by construction: each investment records `days_paid`. A run pays
only the whole days that have elapsed since `start_date` and have not been
paid yet, capped at `duration_days`. Running it twice in a day, or after the
server was down for a week, gives the same correct result.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models import InvestmentPlan, Transaction, UserInvestment
from app.services.ledger import credit, lock_wallet, money


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def run_roi_accrual(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    paid_days = matured = 0
    total_paid = Decimal("0")

    investments = (
        db.query(UserInvestment)
        .filter(UserInvestment.status == "active")
        .with_for_update(skip_locked=True)     # another worker may be processing some rows
        .all()
    )
    for inv in investments:
        elapsed = int((now - _aware(inv.start_date)).total_seconds() // 86400)
        due_days = min(elapsed, inv.duration_days) - (inv.days_paid or 0)
        plan_name = (db.query(InvestmentPlan.name).filter(InvestmentPlan.id == inv.plan_id).scalar()
                     or "plan")
        if due_days > 0:
            daily = money(Decimal(inv.amount_invested) * Decimal(inv.daily_roi_percent) / Decimal(100))
            amount = daily * due_days
            profit = lock_wallet(db, inv.user_id, "profit")
            credit(profit, amount)
            inv.total_earned = Decimal(inv.total_earned or 0) + amount
            inv.days_paid = (inv.days_paid or 0) + due_days
            db.add(Transaction(
                receiver_wallet_id=profit.id, amount=amount, currency=settings.BASE_CURRENCY,
                tx_type="roi_credit", status="completed",
                description=f"{plan_name}: {due_days} day(s) of returns",
            ))
            paid_days += due_days
            total_paid += amount

        if inv.days_paid >= inv.duration_days and now >= _aware(inv.maturity_date):
            inv.status = "completed"
            main = lock_wallet(db, inv.user_id, "main")
            credit(main, money(inv.amount_invested))
            db.add(Transaction(
                receiver_wallet_id=main.id, amount=money(inv.amount_invested),
                currency=settings.BASE_CURRENCY, tx_type="principal_return", status="completed",
                description=f"{plan_name}: principal returned at maturity",
            ))
            matured += 1

    db.commit()
    return {"status": "ok", "investments_checked": len(investments), "days_paid": paid_days,
            "amount_paid": str(total_paid), "matured": matured, "timestamp": now.isoformat()}
