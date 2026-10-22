"""
tests/test_fx.py — FX rate conversion and multi-currency input tests.

Mocked HTTP fetch for external API calls.
"""
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app.models import FxRate, Transaction, User, Wallet
from app.config import settings


@pytest.fixture(scope="function", autouse=True)
def fx_db_cleanup(db_session):
    """Clear fx_rates table before and after each test. Depends on db_session so guard runs first."""
    import app.services.fx_service as fx_module
    
    # Reset failure timestamp
    fx_module._last_failure_time = None
    
    # Clear fx_rates before test
    db_session.query(FxRate).delete()
    db_session.commit()
    
    yield
    
    # Clear fx_rates after test
    db_session.query(FxRate).delete()
    db_session.commit()
    
    # Reset failure timestamp
    fx_module._last_failure_time = None


@pytest.fixture(scope="function", autouse=True)
def fx_isolation():
    """Set up FX service isolation for each test."""
    import app.services.fx_service as fx_module
    # Patch requests.get to raise ConnectionError by default
    with patch("app.services.fx_service.requests.get") as mock_get:
        mock_get.side_effect = Exception("Network blocked by test fixture")
        yield


@pytest.fixture()
def fx_rates(db_session):
    """Seed FX rates for testing."""
    db = db_session
    now = datetime.now(timezone.utc)
    # Add some test currencies
    db.add(FxRate(currency="USD", rate_per_usd=Decimal("1.0"), is_enabled=True, source="test", updated_at=now))
    db.add(FxRate(currency="EUR", rate_per_usd=Decimal("0.92"), is_enabled=True, source="test", updated_at=now))
    db.add(FxRate(currency="NGN", rate_per_usd=Decimal("1550.5"), is_enabled=True, source="test", updated_at=now))
    db.add(FxRate(currency="GBP", rate_per_usd=Decimal("0.79"), is_enabled=False, source="test", updated_at=None))  # Disabled
    db.add(FxRate(currency="JPY", rate_per_usd=None, is_enabled=True, source="test", updated_at=None))  # No rate
    db.commit()
    return db


@pytest.fixture()
def db_session():
    """Provide a database session for tests."""
    # Guard: refuse to run against non-local database
    from app.config import settings
    db_url = settings.DATABASE_URL
    if "localhost" not in db_url and "127.0.0.1" not in db_url:
        pytest.fail("Refusing to run: DATABASE_URL does not point at a local database")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def test_conversion_and_rounding(db_session, fx_rates):
    """Test currency conversion with proper rounding (2 dp, ROUND_HALF_UP)."""
    from app.services.fx_service import to_usd

    db = fx_rates

    # Test 3-decimal case: 100 EUR at 0.92 EUR/USD = 108.6956... USD -> 108.70 USD
    usd_amount, rate = to_usd(db, Decimal("100"), "EUR")
    assert usd_amount == Decimal("108.70")
    assert rate == Decimal("0.92")

    # Test 0-decimal case: 1000 NGN at 1550.5 NGN/USD = 0.6447... USD -> 0.64 USD
    usd_amount, rate = to_usd(db, Decimal("1000"), "NGN")
    assert usd_amount == Decimal("0.64")
    assert rate == Decimal("1550.5")

    # USD is a no-op
    usd_amount, rate = to_usd(db, Decimal("100"), "USD")
    assert usd_amount == Decimal("100.00")
    assert rate == Decimal("1.0")


def test_disabled_currency_rejection(db_session, fx_rates):
    """Test that disabled currencies are rejected."""
    from app.services.fx_service import to_usd
    from fastapi import HTTPException

    db = fx_rates

    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("100"), "GBP")
    assert "isn't available" in str(exc.value.detail)


def test_no_rate_rejection(db_session, fx_rates):
    """Test that currencies without rates are rejected (never 1:1 fallback)."""
    from app.services.fx_service import to_usd
    from fastapi import HTTPException

    db = fx_rates

    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("100"), "JPY")
    assert "isn't available" in str(exc.value.detail)


def test_admin_override_wins(db_session, fx_rates):
    """Test that admin override rate takes precedence over API rate."""
    from app.services.fx_service import effective_rate

    db = fx_rates

    # Set an override for EUR
    eur_row = db.query(FxRate).filter(FxRate.currency == "EUR").first()
    eur_row.override_rate = Decimal("0.95")
    db.commit()

    rate = effective_rate(eur_row)
    assert rate == Decimal("0.95")  # Override wins
    assert rate != eur_row.rate_per_usd  # Not the API rate


def test_deposit_with_input_currency(client, make_user, method, db_session, fx_rates):
    """Test deposit with input_currency stores input_* fields and USD ledger."""
    db = fx_rates
    user = make_user()

    # Create a deposit with EUR input
    r = client.post("/api/wallets/deposits/", headers=user["h"], json={
        "payment_method_id": method["id"],
        "amount": "100",  # 100 EUR
        "input_currency": "EUR",
        "tx_hash": f"tx-{uuid.uuid4().hex[:16]}",
    })
    assert r.status_code == 201, r.text
    tx = r.json()

    # Verify input_* fields are stored
    assert Decimal(tx["input_amount"]) == Decimal("100")
    assert tx["input_currency"] == "EUR"
    assert Decimal(tx["fx_rate"]) == Decimal("0.92")

    # Verify ledger amount is in USD (converted)
    assert tx["currency"] == "USD"
    assert Decimal(tx["amount"]) == Decimal("108.70")  # 100 EUR / 0.92 = 108.70 USD

    # Verify wallet balance is in USD
    wallets = client.get("/api/wallets/", headers=user["h"]).json()
    main_wallet = next(w for w in wallets if w["wallet_type"] == "main")
    assert main_wallet["currency"] == "USD"
    # Note: deposit is pending, so balance not yet credited


def test_deposit_without_input_currency(client, make_user, method, db_session, fx_rates):
    """Test deposit without input_currency behaves as before (USD only)."""
    db = fx_rates
    user = make_user()

    r = client.post("/api/wallets/deposits/", headers=user["h"], json={
        "payment_method_id": method["id"],
        "amount": "100",  # USD
        "tx_hash": f"tx-{uuid.uuid4().hex[:16]}",
    })
    assert r.status_code == 201, r.text
    tx = r.json()

    # Verify input_* fields are None
    assert tx["input_amount"] is None
    assert tx["input_currency"] is None
    assert tx["fx_rate"] is None

    # Verify ledger amount is in USD
    assert tx["currency"] == "USD"
    assert Decimal(tx["amount"]) == Decimal("100.00")


def test_withdrawal_with_input_currency(client, make_user, method, db_session, fx_rates, monkeypatch):
    """Test withdrawal with input_currency converts to USD before debit."""
    db = fx_rates
    user = make_user()

    # Bypass KYC requirement for test
    monkeypatch.setattr(settings, "REQUIRE_KYC_FOR_WITHDRAWAL", False)

    # Get user's main wallet
    wallets = client.get("/api/wallets/", headers=user["h"]).json()
    main_wallet_id = next(w["id"] for w in wallets if w["wallet_type"] == "main")

    # Credit the user's wallet directly for test
    db = SessionLocal()
    wallet = db.query(Wallet).filter(Wallet.id == main_wallet_id).first()
    wallet.balance = Decimal("200.00")
    db.commit()
    db.close()

    # Create withdrawal with EUR input
    r = client.post("/api/wallets/withdrawals/", headers=user["h"], json={
        "payment_method_id": method["id"],
        "amount": "50",  # 50 EUR
        "input_currency": "EUR",
        "withdrawal_address": "T" + "x" * 40,
    })
    assert r.status_code == 201, r.text
    tx = r.json()

    # Verify input_* fields are stored
    assert Decimal(tx["input_amount"]) == Decimal("50")
    assert tx["input_currency"] == "EUR"
    assert Decimal(tx["fx_rate"]) == Decimal("0.92")

    # Verify ledger amount is in USD (converted)
    assert tx["currency"] == "USD"
    assert Decimal(tx["amount"]) == Decimal("54.35")  # 50 EUR / 0.92 = 54.35 USD (rounded)

    # Verify wallet was debited in USD by re-reading from DB
    db = SessionLocal()
    wallet = db.query(Wallet).filter(Wallet.id == main_wallet_id).first()
    assert wallet.balance == Decimal("200.00") - Decimal("54.35")
    db.close()


def test_deposit_without_trailing_slash(client, make_user, method, db_session, fx_rates):
    """Test deposit route without trailing slash works."""
    user = make_user()

    # Create a deposit with EUR input (no trailing slash)
    r = client.post("/api/wallets/deposits", headers=user["h"], json={
        "payment_method_id": method["id"],
        "amount": "100",
        "input_currency": "EUR",
        "tx_hash": f"tx-{uuid.uuid4().hex[:16]}",
    })
    assert r.status_code == 201, r.text


def test_withdrawal_without_trailing_slash(client, make_user, method, db_session, fx_rates, monkeypatch):
    """Test withdrawal route without trailing slash works with USD only."""
    user = make_user()

    # Bypass KYC requirement for test
    monkeypatch.setattr(settings, "REQUIRE_KYC_FOR_WITHDRAWAL", False)

    # Get user's main wallet
    wallets = client.get("/api/wallets/", headers=user["h"]).json()
    main_wallet_id = next(w["id"] for w in wallets if w["wallet_type"] == "main")

    # Credit the user's wallet directly for test
    db = SessionLocal()
    wallet = db.query(Wallet).filter(Wallet.id == main_wallet_id).first()
    wallet.balance = Decimal("100.00")
    db.commit()
    db.close()

    # Create withdrawal with USD only (no input_currency, no trailing slash)
    r = client.post("/api/wallets/withdrawals", headers=user["h"], json={
        "payment_method_id": method["id"],
        "amount": "50",
        "withdrawal_address": "T" + "x" * 40,
    })
    assert r.status_code == 201, r.text


def test_signup_derives_display_currency(client, db_session):
    """Test signup derives display_currency from country if not provided."""
    email = f"user-{uuid.uuid4().hex[:8]}@test.dev"
    r = client.post("/api/auth/signup", json={
        "full_name": "Test User",
        "email": email,
        "password": "User-pass-1",
        "confirm_password": "User-pass-1",
        "country": "Nigeria",  # Should derive NGN
        "accept_terms": True
    })
    assert r.status_code == 201, r.text
    user_data = r.json()

    # Verify display_currency was derived from country
    assert user_data["display_currency"] == "NGN"


def test_signup_explicit_display_currency(client, db_session):
    """Test signup uses explicit display_currency if provided."""
    email = f"user-{uuid.uuid4().hex[:8]}@test.dev"
    r = client.post("/api/auth/signup", json={
        "full_name": "Test User",
        "email": email,
        "password": "User-pass-1",
        "confirm_password": "User-pass-1",
        "country": "Nigeria",
        "display_currency": "EUR",  # Explicit override
        "accept_terms": True
    })
    assert r.status_code == 201, r.text
    user_data = r.json()

    # Verify explicit display_currency was used
    assert user_data["display_currency"] == "EUR"


def test_wallets_remain_usd(client, make_user):
    """Test that wallets are always created with USD currency."""
    user = make_user()

    wallets = client.get("/api/wallets/", headers=user["h"]).json()
    assert len(wallets) == 2

    for wallet in wallets:
        assert wallet["currency"] == "USD"


def test_get_rates_endpoint(client, make_user, fx_rates):
    """Test GET /api/fx/rates returns enabled currencies with effective rates."""
    db = fx_rates
    user = make_user()

    r = client.get("/api/fx/rates", headers=user["h"])
    assert r.status_code == 200, r.text
    data = r.json()

    assert "rates" in data
    assert "attribution" in data
    assert data["attribution"]["text"] == "Rates By Exchange Rate API"
    assert data["attribution"]["url"] == "https://www.exchangerate-api.com"

    # Should return enabled currencies only (GBP is disabled)
    rate_currencies = [r["currency"] for r in data["rates"]]
    assert "USD" in rate_currencies
    assert "EUR" in rate_currencies
    assert "NGN" in rate_currencies
    assert "GBP" not in rate_currencies  # Disabled


@patch("app.services.fx_service.requests.get")
def test_refresh_rates_mocked(mock_get, db_session):
    """Test refresh_rates with mocked HTTP fetch."""
    from app.services.fx_service import refresh_rates, seed_default_rates

    db = db_session
    seed_default_rates(db)

    # Mock successful API response
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "result": "success",
        "rates": {
            "EUR": 0.93,
            "GBP": 0.80,
            "NGN": 1600.0,
            "USD": 1.0,
        }
    }

    success = refresh_rates(db)
    assert success is True

    # Verify rates were updated
    eur = db.query(FxRate).filter(FxRate.currency == "EUR").first()
    assert eur.rate_per_usd == Decimal("0.93")
    assert eur.source == "open.er-api.com"
    assert eur.updated_at is not None


@patch("app.services.fx_service.requests.get")
def test_refresh_rates_failure(mock_get, db_session):
    """Test refresh_rates handles API failure gracefully."""
    from app.services.fx_service import refresh_rates, seed_default_rates

    db = db_session
    seed_default_rates(db)

    # Set initial rate
    eur = db.query(FxRate).filter(FxRate.currency == "EUR").first()
    eur.rate_per_usd = Decimal("0.92")
    db.commit()

    # Mock API failure
    mock_get.side_effect = Exception("Network error")

    success = refresh_rates(db)
    assert success is False

    # Verify old rate is kept
    db.refresh(eur)
    assert eur.rate_per_usd == Decimal("0.92")


def test_admin_fx_routes_require_auth(client, fx_rates):
    """Test that admin FX routes require authentication."""
    # Unauthenticated request to GET /api/admin/fx/rates
    r = client.get("/api/admin/fx/rates")
    assert r.status_code == 401, r.text

    # Unauthenticated request to PATCH /api/admin/fx/rates/EUR
    r = client.patch("/api/admin/fx/rates/EUR", json={"is_enabled": False})
    assert r.status_code == 401, r.text

    # Unauthenticated request to POST /api/admin/fx/refresh
    r = client.post("/api/admin/fx/refresh")
    assert r.status_code == 401, r.text


def test_admin_fx_routes_require_admin_role(client, make_user, fx_rates):
    """Test that admin FX routes require admin role."""
    user = make_user()

    # Non-admin request to GET /api/admin/fx/rates
    r = client.get("/api/admin/fx/rates", headers=user["h"])
    assert r.status_code == 403, r.text

    # Non-admin request to PATCH /api/admin/fx/rates/EUR
    r = client.patch("/api/admin/fx/rates/EUR", headers=user["h"], json={"is_enabled": False})
    assert r.status_code == 403, r.text

    # Non-admin request to POST /api/admin/fx/refresh
    r = client.post("/api/admin/fx/refresh", headers=user["h"])
    assert r.status_code == 403, r.text


def test_admin_patch_writes_audit_log(client, admin, fx_rates):
    """Test that PATCH /api/admin/fx/rates/{currency} writes an audit log."""
    db = fx_rates

    # Patch EUR rate
    r = client.patch("/api/admin/fx/rates/EUR", headers=admin, json={"override_rate": "0.95"})
    assert r.status_code == 200, r.text

    # Verify audit log was written
    from app.models import AuditLog
    audit = db.query(AuditLog).filter(AuditLog.action == "UPDATE_FX_RATE").order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.admin_id is not None
    assert "EUR" in audit.details
    assert "enabled=" in audit.details
    assert "override=" in audit.details


def test_admin_refresh_writes_audit_log(client, admin, fx_rates):
    """Test that POST /api/admin/fx/refresh writes an audit log."""
    db = fx_rates

    # Trigger refresh (will fail due to no API, but audit should still be written)
    r = client.post("/api/admin/fx/refresh", headers=admin)
    assert r.status_code in (200, 500)  # May fail due to API, but should still respond

    # Verify audit log was written
    from app.models import AuditLog
    audit = db.query(AuditLog).filter(AuditLog.action == "REFRESH_FX").order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.admin_id is not None
    assert "Manual FX rate refresh" in audit.details


def test_invalid_override_rate_values(client, admin, fx_rates):
    """Test that invalid override_rate values return 422."""
    # Non-positive value
    r = client.patch("/api/admin/fx/rates/EUR", headers=admin, json={"override_rate": "-1.0"})
    assert r.status_code == 422, r.text

    # Zero
    r = client.patch("/api/admin/fx/rates/EUR", headers=admin, json={"override_rate": "0"})
    assert r.status_code == 422, r.text

    # Too large (> 1e9)
    r = client.patch("/api/admin/fx/rates/EUR", headers=admin, json={"override_rate": "1e10"})
    assert r.status_code == 422, r.text

    # Valid value should succeed
    r = client.patch("/api/admin/fx/rates/EUR", headers=admin, json={"override_rate": "0.95"})
    assert r.status_code == 200, r.text


def test_invalid_currency_path_param(client, admin, fx_rates):
    """Test that invalid currency path param returns 422."""
    # Too short
    r = client.patch("/api/admin/fx/rates/AB", headers=admin, json={"is_enabled": False})
    assert r.status_code == 422, r.text

    # Too long
    r = client.patch("/api/admin/fx/rates/ABCDEFGHIJK", headers=admin, json={"is_enabled": False})
    assert r.status_code == 422, r.text

    # Contains numbers
    r = client.patch("/api/admin/fx/rates/EUR1", headers=admin, json={"is_enabled": False})
    assert r.status_code == 422, r.text

    # Contains special chars
    r = client.patch("/api/admin/fx/rates/EUR$", headers=admin, json={"is_enabled": False})
    assert r.status_code == 422, r.text

    # Valid currency (lowercase should work, gets uppercased)
    r = client.patch("/api/admin/fx/rates/eur", headers=admin, json={"is_enabled": False})
    assert r.status_code in (200, 404)  # 404 if EUR doesn't exist in test DB


def test_to_usd_seeds_and_refreshes_on_empty_table(db_session, monkeypatch):
    """Test that to_usd with an empty fx_rates table seeds defaults and refreshes before converting."""
    from app.services.fx_service import to_usd, seed_default_rates, refresh_rates
    from datetime import datetime, timezone, timedelta

    db = db_session

    # Mock refresh_rates to succeed and set updated_at
    def mock_refresh(db):
        # Set some rates with recent timestamps
        for row in db.query(FxRate).all():
            if row.currency == "EUR":
                row.rate_per_usd = Decimal("0.92")
                row.updated_at = datetime.now(timezone.utc)
            elif row.currency == "USD":
                row.rate_per_usd = Decimal("1.0")
                row.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    # Patch refresh_rates
    import app.services.fx_service as fx_module
    monkeypatch.setattr(fx_module, "refresh_rates", mock_refresh)

    # Call to_usd - should seed and refresh automatically
    usd_amount, rate = to_usd(db, Decimal("100"), "EUR")
    assert usd_amount == Decimal("108.70")
    assert rate == Decimal("0.92")

    # Verify defaults were seeded
    rows = db.query(FxRate).all()
    assert len(rows) == 11  # DEFAULT_CURRENCIES has 11 items


def test_rate_expiry_72_hours(db_session):
    """Test that a rate older than 72 hours is rejected with 422."""
    from app.services.fx_service import to_usd
    from datetime import datetime, timezone, timedelta

    db = db_session

    # Create a EUR rate that's 100 hours old
    old_time = datetime.now(timezone.utc) - timedelta(hours=100)

    eur = FxRate(
        currency="EUR",
        rate_per_usd=Decimal("0.92"),
        is_enabled=True,
        source="test",
        updated_at=old_time
    )
    db.add(eur)
    db.commit()

    # Should be rejected due to expiry
    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("100"), "EUR")
    assert exc.value.status_code == 422
    assert "isn't available right now" in exc.value.detail


def test_override_rate_no_expiry(db_session):
    """Test that an override_rate older than 72 hours is still accepted."""
    from app.services.fx_service import to_usd
    from datetime import datetime, timezone, timedelta

    db = db_session

    # Create a EUR rate with an old override
    old_time = datetime.now(timezone.utc) - timedelta(hours=100)

    eur = FxRate(
        currency="EUR",
        rate_per_usd=Decimal("0.92"),
        override_rate=Decimal("0.95"),  # Override is old but should still work
        is_enabled=True,
        source="test",
        updated_at=old_time
    )
    db.add(eur)
    db.commit()

    # Should succeed because override_rate is set
    usd_amount, rate = to_usd(db, Decimal("100"), "EUR")
    assert usd_amount == Decimal("105.26")  # 100 / 0.95
    assert rate == Decimal("0.95")


def test_ensure_fresh_failure_backoff(db_session, monkeypatch):
    """Test that ensure_fresh does not fetch a second time within 15 minutes of a failure."""
    from app.services.fx_service import ensure_fresh
    from datetime import datetime, timezone, timedelta

    db = db_session

    # Mock refresh_rates to fail
    import app.services.fx_service as fx_module

    call_count = [0]
    def mock_refresh(db):
        call_count[0] += 1
        return False

    monkeypatch.setattr(fx_module, "refresh_rates", mock_refresh)

    # First call - should attempt refresh and fail
    ensure_fresh(db)
    assert call_count[0] == 1, "refresh_rates should be called on first ensure_fresh"
    assert fx_module._last_failure_time is not None

    # Set failure time to 1 minute ago (within backoff window)
    fx_module._last_failure_time = datetime.now(timezone.utc) - timedelta(minutes=1)

    # Second call - should skip due to backoff
    ensure_fresh(db)
    assert call_count[0] == 1  # No additional call

    # Set failure time to 20 minutes ago (outside backoff window)
    fx_module._last_failure_time = datetime.now(timezone.utc) - timedelta(minutes=20)

    # Third call - should attempt refresh again
    ensure_fresh(db)
    assert call_count[0] == 2

    # Mock success to test timestamp clearing
    def mock_refresh_success(db):
        call_count[0] += 1
        return True
    monkeypatch.setattr(fx_module, "refresh_rates", mock_refresh_success)
    fx_module._last_failure_time = datetime.now(timezone.utc) - timedelta(minutes=30)

    # Fourth call - should succeed and clear timestamp
    ensure_fresh(db)
    assert call_count[0] == 3
    assert fx_module._last_failure_time is None  # Cleared on success


def test_seed_default_rates_race_safe(db_session):
    """Test that seed_default_rates called twice does not raise and leaves one row per currency."""
    from app.services.fx_service import seed_default_rates

    db = db_session

    # Ensure table is empty
    db.query(FxRate).delete()
    db.commit()

    # First call
    seed_default_rates(db)
    rows_after_first = db.query(FxRate).all()
    assert len(rows_after_first) == 11  # DEFAULT_CURRENCIES

    # Second call - should not raise or duplicate
    seed_default_rates(db)
    rows_after_second = db.query(FxRate).all()
    assert len(rows_after_second) == 11  # Still 11, no duplicates


def test_seed_default_rates_no_insert_when_rows_exist(db_session):
    """Test that seed_default_rates makes no insert when rows already exist."""
    from app.services.fx_service import seed_default_rates

    db = db_session

    # Add a single row
    db.add(FxRate(currency="USD", rate_per_usd=Decimal("1.0"), is_enabled=True, source="test", updated_at=None))
    db.commit()

    initial_count = db.query(FxRate).count()

    # Call seed_default_rates - should return immediately without inserting
    seed_default_rates(db)

    final_count = db.query(FxRate).count()
    assert final_count == initial_count  # No new rows added


def test_get_rates_filters_unusable(client, make_user, db_session):
    """Test GET /rates omits currencies with no rate, old rate (no override), but keeps override and USDT."""
    from datetime import datetime, timezone, timedelta

    db = db_session
    user = make_user()

    # Clear existing rates
    db.query(FxRate).delete()
    db.commit()

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=100)

    # Currency with no rate
    db.add(FxRate(currency="JPY", rate_per_usd=None, is_enabled=True, source="test", updated_at=None))
    # Currency with old rate (no override) - should be omitted
    db.add(FxRate(currency="EUR", rate_per_usd=Decimal("0.92"), is_enabled=True, source="test", updated_at=old_time))
    # Currency with old override - should be included
    db.add(FxRate(currency="GBP", rate_per_usd=Decimal("0.79"), override_rate=Decimal("0.80"), is_enabled=True, source="test", updated_at=old_time))
    # USDT with old rate - should be included (stablecoin)
    db.add(FxRate(currency="USDT", rate_per_usd=Decimal("1.0"), is_enabled=True, source="test", updated_at=old_time))
    # USD with recent rate - should be included
    db.add(FxRate(currency="USD", rate_per_usd=Decimal("1.0"), is_enabled=True, source="test", updated_at=now))
    db.commit()

    r = client.get("/api/fx/rates", headers=user["h"])
    assert r.status_code == 200, r.text
    data = r.json()

    rate_currencies = [r["currency"] for r in data["rates"]]

    assert "JPY" not in rate_currencies  # No rate
    assert "EUR" not in rate_currencies  # Old rate, no override
    assert "GBP" in rate_currencies  # Has override
    assert "USDT" in rate_currencies  # Stablecoin
    assert "USD" in rate_currencies  # Recent rate


def test_to_usd_decimal_and_amount_validation(db_session):
    """Test to_usd rejects amounts with >2 decimal places and amounts > 1e9 for non-USD currencies."""
    from app.services.fx_service import to_usd

    db = db_session

    # Add EUR rate
    db.add(FxRate(currency="EUR", rate_per_usd=Decimal("0.92"), is_enabled=True, source="test", updated_at=None))
    db.commit()

    # More than 2 decimal places
    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("100.123"), "EUR")
    assert exc.value.status_code == 422
    assert "at most 2 decimal places" in exc.value.detail

    # Amount too large
    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("2000000000"), "EUR")
    assert exc.value.status_code == 422
    assert "too large" in exc.value.detail

    # USD should bypass these validations
    usd_amount, rate = to_usd(db, Decimal("100.123456"), "USD")
    assert usd_amount == Decimal("100.12")  # Rounded to 2 dp

    usd_amount, rate = to_usd(db, Decimal("2000000000"), "USD")
    assert usd_amount == Decimal("2000000000.00")


def test_to_usd_rejects_non_finite_amounts(db_session):
    """Test to_usd rejects NaN and Infinity with 422."""
    from app.services.fx_service import to_usd

    db = db_session

    # Add EUR rate
    db.add(FxRate(currency="EUR", rate_per_usd=Decimal("0.92"), is_enabled=True, source="test", updated_at=None))
    db.commit()

    # NaN
    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("NaN"), "EUR")
    assert exc.value.status_code == 422
    assert "valid amount" in exc.value.detail

    # Infinity
    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("Infinity"), "EUR")
    assert exc.value.status_code == 422
    assert "valid amount" in exc.value.detail

    # Negative Infinity
    with pytest.raises(HTTPException) as exc:
        to_usd(db, Decimal("-Infinity"), "EUR")
    assert exc.value.status_code == 422
    assert "valid amount" in exc.value.detail


def test_signup_resilient_to_country_currency_error(client, db_session, monkeypatch):
    """Test signup returns 200 and display_currency USD when get_currency_for_country fails."""
    email = f"user-{uuid.uuid4().hex[:8]}@test.dev"
    
    # Monkeypatch get_currency_for_country to raise ModuleNotFoundError
    import app.utils.country_currency as cc_module
    monkeypatch.setattr(cc_module, "get_currency_for_country", lambda country: (_ for _ in ()).throw(ModuleNotFoundError("pycountry not found")))
    
    r = client.post("/api/auth/signup", json={
        "full_name": "Test User",
        "email": email,
        "password": "User-pass-1",
        "confirm_password": "User-pass-1",
        "country": "Nigeria",
        "accept_terms": True
    })
    assert r.status_code == 201, r.text
    user_data = r.json()

    # Verify display_currency falls back to USD
    assert user_data["display_currency"] == "USD"


def test_signup_validates_display_currency_format(client, db_session):
    """Test signup validates client-supplied display_currency as 3-10 uppercase letters."""
    email = f"user-{uuid.uuid4().hex[:8]}@test.dev"
    
    # Too short
    r = client.post("/api/auth/signup", json={
        "full_name": "Test User",
        "email": email,
        "password": "User-pass-1",
        "confirm_password": "User-pass-1",
        "country": "Nigeria",
        "display_currency": "US",  # Too short
        "accept_terms": True
    })
    assert r.status_code == 422, r.text
    assert "display_currency must be 3-10 uppercase letters" in r.text
    
    # Too long
    email = f"user-{uuid.uuid4().hex[:8]}@test.dev"
    r = client.post("/api/auth/signup", json={
        "full_name": "Test User",
        "email": email,
        "password": "User-pass-1",
        "confirm_password": "User-pass-1",
        "country": "Nigeria",
        "display_currency": "ABCDEFGHIJK",  # Too long
        "accept_terms": True
    })
    assert r.status_code == 422, r.text
    assert "display_currency must be 3-10 uppercase letters" in r.text
    
    # Contains numbers
    email = f"user-{uuid.uuid4().hex[:8]}@test.dev"
    r = client.post("/api/auth/signup", json={
        "full_name": "Test User",
        "email": email,
        "password": "User-pass-1",
        "confirm_password": "User-pass-1",
        "country": "Nigeria",
        "display_currency": "EUR1",  # Contains number
        "accept_terms": True
    })
    assert r.status_code == 422, r.text
    assert "display_currency must be 3-10 uppercase letters" in r.text
