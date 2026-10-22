"""
app/routers/fx.py — FX rate management endpoints.

- GET /api/fx/rates (logged-in users): list of enabled currencies with effective rates
"""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database import get_db
from app.models import FxRate, User
from app.security import get_current_user
from app.services.fx_service import ensure_fresh, effective_rate, is_rate_usable, seed_default_rates
from sqlalchemy.orm import Session
from sqlalchemy import select


router = APIRouter(prefix="/api/fx", tags=["FX"])


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────
class FxRateOut(BaseModel):
    currency: str
    effective_rate: Optional[Decimal]  # The rate used for conversion (override or API)
    updated_at: Optional[str] = None


class FxRatesResponse(BaseModel):
    rates: List[FxRateOut]
    attribution: dict


# ──────────────────────────────────────────────
# User endpoint
# ──────────────────────────────────────────────
@router.get("/rates", response_model=FxRatesResponse)
def get_rates(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    List enabled currencies with their effective rates.
    Refreshes rates if they're stale (older than 12 hours).
    """
    # Seed default currencies if table is empty
    seed_default_rates(db)

    # Ensure rates are fresh
    ensure_fresh(db)

    # Fetch enabled currencies
    rows = db.execute(
        select(FxRate).where(FxRate.is_enabled == True)
    ).scalars().all()

    rates = []
    for row in rows:
        if is_rate_usable(row):
            rate = effective_rate(row)
            rates.append(FxRateOut(
                currency=row.currency,
                effective_rate=rate,
                updated_at=row.updated_at.isoformat() if row.updated_at else None
            ))

    return FxRatesResponse(
        rates=rates,
        attribution={
            "text": "Rates By Exchange Rate API",
            "url": "https://www.exchangerate-api.com"
        }
    )


