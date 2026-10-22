"""
app/routers/fx.py — FX rate management endpoints.

- GET /api/fx/rates (logged-in users): list of enabled currencies with effective rates
- Admin endpoints:
  - GET /api/admin/fx/rates (all rows, both raw and override)
  - PATCH /api/admin/fx/rates/{currency} (is_enabled, override_rate)
  - POST /api/admin/fx/refresh
"""
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.models import AuditLog, FxRate, User
from app.security import get_current_admin, get_current_user
from app.services.fx_service import ensure_fresh, effective_rate, seed_default_rates
from sqlalchemy.orm import Session
from sqlalchemy import select


router = APIRouter()


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


class AdminFxRateOut(BaseModel):
    currency: str
    rate_per_usd: Optional[Decimal]  # Raw API rate
    override_rate: Optional[Decimal]  # Admin override
    is_enabled: bool
    source: Optional[str]
    updated_at: Optional[str]


class AdminFxRateUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    override_rate: Optional[Decimal] = None

    @field_validator("override_rate")
    @classmethod
    def override_rate_valid(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None:
            if v.is_nan() or v.is_infinite():
                raise ValueError("Override rate must be a finite number.")
            if v <= 0:
                raise ValueError("Override rate must be positive.")
            if v > Decimal("1e9"):
                raise ValueError("Override rate must not exceed 1,000,000,000.")
        return v


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


# ──────────────────────────────────────────────
# Admin endpoints
# ──────────────────────────────────────────────
@router.get("/admin/fx/rates", response_model=List[AdminFxRateOut])
def get_admin_rates(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all FX rate rows (including disabled ones) with raw and override rates."""
    rows = db.execute(select(FxRate).order_by(FxRate.currency)).scalars().all()

    return [
        AdminFxRateOut(
            currency=row.currency,
            rate_per_usd=row.rate_per_usd,
            override_rate=row.override_rate,
            is_enabled=row.is_enabled,
            source=row.source,
            updated_at=row.updated_at.isoformat() if row.updated_at else None
        )
        for row in rows
    ]


@router.patch("/admin/fx/rates/{currency}", response_model=AdminFxRateOut)
def update_fx_rate(
    currency: str,
    payload: AdminFxRateUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update is_enabled or override_rate for a specific currency."""
    currency = currency.upper().strip()

    # Validate currency format
    if not (3 <= len(currency) <= 10) or not currency.isalpha():
        raise HTTPException(status_code=422, detail="Currency must be 3-10 uppercase letters.")

    row = db.execute(
        select(FxRate).where(FxRate.currency == currency)
    ).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail=f"Currency {currency} not found.")

    # Capture old values for audit log
    old_override = row.override_rate
    old_enabled = row.is_enabled

    if payload.is_enabled is not None:
        row.is_enabled = payload.is_enabled

    if payload.override_rate is not None:
        row.override_rate = payload.override_rate
    elif payload.override_rate is None and "override_rate" in payload.model_fields_set:
        # Explicitly set to None to clear override
        row.override_rate = None

    db.commit()
    db.refresh(row)

    # Log the change with old and new values
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="UPDATE_FX_RATE",
        details=f"Updated FX rate for {currency}: enabled={old_enabled}->{row.is_enabled}, override={old_override}->{row.override_rate}"
    ))
    db.commit()

    return AdminFxRateOut(
        currency=row.currency,
        rate_per_usd=row.rate_per_usd,
        override_rate=row.override_rate,
        is_enabled=row.is_enabled,
        source=row.source,
        updated_at=row.updated_at.isoformat() if row.updated_at else None
    )


@router.post("/admin/fx/refresh")
def refresh_fx_rates(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Manually trigger a rate refresh from the external API."""
    from app.services.fx_service import refresh_rates

    success = refresh_rates(db)

    # Log the refresh action
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="REFRESH_FX",
        details=f"Manual FX rate refresh: {'success' if success else 'failed'}"
    ))
    db.commit()

    if success:
        return {"status": "success", "message": "Rates refreshed successfully."}
    else:
        return {"status": "failed", "message": "Failed to refresh rates. Old values kept."}
