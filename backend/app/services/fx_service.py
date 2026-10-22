"""
app/services/fx_service.py — currency conversion and FX rate management.

Users enter amounts in their chosen currency; the server converts to USD for the ledger.
Wallet.currency and Transaction.currency remain "USD" always.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

import requests
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import FxRate
from app.services.ledger import money

logger = logging.getLogger(__name__)

# Default enabled currencies to seed when table is empty
DEFAULT_CURRENCIES = ["USD", "EUR", "GBP", "NGN", "ARS", "GHS", "KES", "ZAR", "CAD", "AUD", "USDT"]

# Rate refresh threshold: refresh if newest rate is older than 12 hours
REFRESH_THRESHOLD_HOURS = 12

# Rate expiry threshold: reject conversion if rate is older than 72 hours (unless override)
EXPIRY_THRESHOLD_HOURS = 72

# HTTP timeout for external API
HTTP_TIMEOUT_SECONDS = 10

# Failure backoff: skip refresh attempts within this time after a failure
FAILURE_BACKOFF_MINUTES = 15

# Module-level timestamp of last failed refresh attempt
_last_failure_time: Optional[datetime] = None

# External API endpoint
RATE_API_URL = "https://open.er-api.com/v6/latest/USD"


def seed_default_rates(db: Session) -> None:
    """Seed default currencies when the fx_rates table is empty.
    
    Returns immediately if the table already has any row.
    Race-safe using INSERT ... ON CONFLICT DO NOTHING.
    Never raises on duplicate key errors.
    """
    existing = db.execute(select(func.count()).select_from(FxRate)).scalar()
    if existing > 0:
        return

    logger.info("Seeding default FX rates...")
    stmt = insert(FxRate).values([
        {
            "currency": currency,
            "rate_per_usd": None,  # Will be filled by refresh_rates
            "is_enabled": True,
            "source": None,
            "updated_at": None
        }
        for currency in DEFAULT_CURRENCIES
    ])
    stmt = stmt.on_conflict_do_nothing(index_elements=["currency"])
    db.execute(stmt)
    db.commit()
    logger.info(f"Seeded {len(DEFAULT_CURRENCIES)} default currencies.")


def refresh_rates(db: Session) -> bool:
    """
    Fetch rates from open.er-api.com and update the database.

    Returns True on success, False on failure. On failure, old values are kept.
    Only updates currencies we have rows for; ignores non-positive rates.
    """
    try:
        response = requests.get(RATE_API_URL, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()

        if data.get("result") != "success" or "rates" not in data:
            logger.warning(f"FX API returned unexpected response: {data}")
            return False

        rates = data["rates"]
        updated_count = 0

        # Get all currencies we have rows for
        our_currencies = db.execute(select(FxRate.currency)).scalars().all()

        for currency in our_currencies:
            if currency in rates:
                rate = rates[currency]
                if rate is not None and rate > 0:
                    # Update rate_per_usd (units of this currency per 1 USD)
                    db.execute(
                        FxRate.__table__.update()
                        .where(FxRate.currency == currency)
                        .values(
                            rate_per_usd=Decimal(str(rate)),
                            source="open.er-api.com",
                            updated_at=datetime.now(timezone.utc)
                        )
                    )
                    updated_count += 1

        db.commit()
        logger.info(f"Refreshed {updated_count} FX rates from open.er-api.com")
        return True

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch FX rates: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error refreshing FX rates: {e}")
        return False


def ensure_fresh(db: Session) -> None:
    """
    Refresh rates if the newest updated_at is older than REFRESH_THRESHOLD_HOURS or missing.

    Uses a lock to prevent concurrent requests from all fetching. Never blocks for more
    than HTTP_TIMEOUT_SECONDS. Never raises from here.

    If the lock is not acquired, returns immediately without fetching.
    Skips refresh attempts within 15 minutes of a failure.
    Rolls back the session if it enters a failed state.
    Manages failure bookkeeping: sets _last_failure_time on failure, clears on success.
    """
    global _last_failure_time
    try:
        # Check failure backoff: skip if we failed recently
        if _last_failure_time:
            backoff_elapsed = datetime.now(timezone.utc) - _last_failure_time
            if backoff_elapsed < timedelta(minutes=FAILURE_BACKOFF_MINUTES):
                return  # Too soon to retry after failure

        # Check if we need a refresh
        newest = db.execute(
            select(FxRate.updated_at)
            .where(FxRate.updated_at.isnot(None))
            .order_by(FxRate.updated_at.desc())
            .limit(1)
        ).scalar()

        if newest:
            age = datetime.now(timezone.utc) - newest
            if age < timedelta(hours=REFRESH_THRESHOLD_HOURS):
                return  # Fresh enough

        # Use a simple advisory lock to prevent concurrent refreshes
        # PostgreSQL-specific: pg_try_advisory_xact_lock
        # Returns True if lock acquired, False if not
        lock_acquired = db.execute(select(func.pg_try_advisory_xact_lock(123456789))).scalar()
        if not lock_acquired:
            return  # Another request is refreshing

        # Double-check after acquiring lock
        newest = db.execute(
            select(FxRate.updated_at)
            .where(FxRate.updated_at.isnot(None))
            .order_by(FxRate.updated_at.desc())
            .limit(1)
        ).scalar()

        if newest:
            age = datetime.now(timezone.utc) - newest
            if age < timedelta(hours=REFRESH_THRESHOLD_HOURS):
                return  # Another request refreshed while we waited

        success = refresh_rates(db)
        if success:
            _last_failure_time = None  # Clear failure timestamp on success
        else:
            _last_failure_time = datetime.now(timezone.utc)  # Record failure

    except Exception as e:
        logger.warning(f"Error in ensure_fresh: {e}")
        # Record failure timestamp on exception
        _last_failure_time = datetime.now(timezone.utc)
        # Rollback if session is in a failed state
        try:
            db.rollback()
        except Exception:
            pass  # Ignore rollback errors
        # Never raise; this is a best-effort background operation


def effective_rate(row: Optional[FxRate]) -> Optional[Decimal]:
    """
    Return the effective rate for conversion.

    - If override_rate is set, use it.
    - For USD, USDT, USDC: return 1.0 (even if no rate in DB).
    - Otherwise, use rate_per_usd if available.
    - Return None if unavailable.

    NEVER fall back to 1.0 for any other currency.
    """
    if row is None:
        return None

    if row.override_rate is not None:
        return row.override_rate

    # Stablecoins and USD are 1:1
    if row.currency in ("USD", "USDT", "USDC"):
        return Decimal("1.0")

    if row.rate_per_usd is not None:
        return row.rate_per_usd

    return None


def is_rate_usable(row: Optional[FxRate]) -> bool:
    """
    Return True if the FX rate row is usable for conversion.

    A row is usable when:
    - It is enabled
    - effective_rate(row) is not None
    - AND (override_rate is set OR currency is USD/USDT/USDC OR updated_at is within EXPIRY_THRESHOLD_HOURS)
    """
    if row is None:
        return False

    if not row.is_enabled:
        return False

    rate = effective_rate(row)
    if rate is None:
        return False

    # Overrides don't expire
    if row.override_rate is not None:
        return True

    # Stablecoins and USD don't expire
    if row.currency in ("USD", "USDT", "USDC"):
        return True

    # Check expiry for regular rates
    if row.updated_at is None:
        return False

    age = datetime.now(timezone.utc) - row.updated_at
    return age <= timedelta(hours=EXPIRY_THRESHOLD_HOURS)


def to_usd(db: Session, amount: Decimal, currency: str) -> Tuple[Decimal, Decimal]:
    """
    Convert an amount from a foreign currency to USD.

    Returns (usd_amount, rate_used).

    Raises HTTPException 422 if:
    - Currency is unknown or disabled
    - No rate is available
    - Amount <= 0
    - USD result <= 0
    - Rate is older than 72 hours (unless override_rate is set or USD/USDT/USDC)
    - Amount has more than 2 decimal places (non-USD currencies only)
    - Amount > 1,000,000,000 (non-USD currencies only)

    Uses the same rounding as ledger.money() (2 dp, ROUND_HALF_UP).
    """
    # Best-effort seeding and refresh - never raise
    try:
        seed_default_rates(db)
    except Exception:
        pass  # Continue anyway
    try:
        ensure_fresh(db)
    except Exception:
        pass  # Continue anyway

    # Reject non-finite amounts (NaN, Infinity)
    if not amount.is_finite():
        raise HTTPException(
            status_code=422,
            detail="Enter a valid amount."
        )

    if amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="Amount must be positive."
        )

    # Normalize currency code
    currency = currency.upper().strip()

    # USD is a no-op
    if currency == "USD":
        return money(amount), Decimal("1.0")

    # For non-USD currencies: validate decimal places and max amount
    # Check for more than 2 decimal places
    if amount.as_tuple().exponent < -2:
        raise HTTPException(
            status_code=422,
            detail="Enter an amount with at most 2 decimal places."
        )

    # Check for amount > 1,000,000,000
    if amount > Decimal("1000000000"):
        raise HTTPException(
            status_code=422,
            detail="That amount is too large."
        )

    # Look up the currency
    row = db.execute(
        select(FxRate).where(FxRate.currency == currency)
    ).scalar_one_or_none()

    if row is None or not is_rate_usable(row):
        raise HTTPException(
            status_code=422,
            detail=f"Currency {currency} isn't available right now. Choose USD or try again later."
        )

    rate = effective_rate(row)

    # Convert: usd = amount / rate (rate is units of currency per 1 USD)
    usd_amount = amount / rate
    usd_amount = money(usd_amount)  # Round to 2 dp

    if usd_amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="Converted amount must be positive."
        )

    return usd_amount, rate


def from_usd(db: Session, usd_amount: Decimal, currency: str) -> Tuple[Decimal, Decimal]:
    """
    Convert a USD amount to a foreign currency for display.

    Returns (foreign_amount, rate_used).

    Raises HTTPException 422 if currency is unavailable.
    """
    # Best-effort seeding and refresh - never raise
    try:
        seed_default_rates(db)
    except Exception:
        pass  # Continue anyway
    try:
        ensure_fresh(db)
    except Exception:
        pass  # Continue anyway

    currency = currency.upper().strip()

    if currency == "USD":
        return usd_amount, Decimal("1.0")

    row = db.execute(
        select(FxRate).where(FxRate.currency == currency)
    ).scalar_one_or_none()

    if row is None or not is_rate_usable(row):
        raise HTTPException(
            status_code=422,
            detail=f"Currency {currency} isn't available right now."
        )

    rate = effective_rate(row)

    # Convert: foreign = usd * rate
    foreign_amount = usd_amount * rate
    return foreign_amount, rate
