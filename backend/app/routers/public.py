"""
app/routers/public.py — read-only data for the public website (no sign-in).

Only fields that are safe to publish: no deposit addresses, no customer data.
Responses are cached in memory for a minute, so public traffic barely touches
the database, and changes made in the console appear within a minute.
"""
import time
from typing import Callable

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import InvestmentPlan, PaymentMethod

router = APIRouter(prefix="/api/public", tags=["Public"])
_TTL = 60
_cache: dict = {}


def _cached(key: str, db: Session, build: Callable[[Session], list]) -> list:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    value = build(db)
    _cache[key] = (time.monotonic(), value)
    return value


def clear_public_cache() -> None:
    _cache.clear()


@router.get("/payment-methods")
def public_payment_methods(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = f"public, max-age={_TTL}"
    return _cached("methods", db, lambda d: [{
        "asset": m.asset, "network": m.network,
        "deposits": bool(m.deposit_enabled), "withdrawals": bool(m.withdraw_enabled),
        "min_deposit": str(m.min_deposit), "min_withdrawal": str(m.min_withdrawal),
        "withdrawal_fee": str(m.withdrawal_fee),
    } for m in d.query(PaymentMethod).filter(PaymentMethod.is_active.is_(True))
        .order_by(PaymentMethod.asset, PaymentMethod.network).all()])


@router.get("/plans")
def public_plans(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = f"public, max-age={_TTL}"
    return _cached("plans", db, lambda d: [{
        "name": p.name, "description": p.description,
        "daily_roi_percent": str(p.daily_roi_percent), "duration_days": p.duration_days,
        "min_amount": str(p.min_amount), "max_amount": str(p.max_amount),
    } for p in d.query(InvestmentPlan).filter(InvestmentPlan.is_active.is_(True))
        .order_by(InvestmentPlan.min_amount).all()])


@router.get("/info")
def public_info():
    return {"base_currency": settings.BASE_CURRENCY}
