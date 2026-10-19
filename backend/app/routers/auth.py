"""
app/routers/auth.py — Sign Up & Login endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from decimal import Decimal
import random
import string

from app.database import get_db
from app.models import User, Wallet, KYCStatus
from app.schemas import SignUpRequest, LoginRequest, TokenResponse, UserOut, KYCSubmitRequest
from app.security import hash_password, verify_password, create_access_token, get_current_user
from app.services.email import send_welcome_email
from app.utils.country_currency import get_currency_for_country

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _generate_unique_referral_code(db: Session) -> str:
    """Generate a unique 8-character uppercase alphanumeric referral code."""
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        existing = db.query(User).filter(User.referral_code == code).first()
        if not existing:
            return code


def _init_wallets(db: Session, user_id, currency: str = "USD") -> None:
    """Create Main and Profit wallets for a new user in the resolved currency."""
    for wtype in ("main", "profit"):
        wallet = Wallet(
            user_id=user_id,
            wallet_type=wtype,
            currency=currency,
            balance=Decimal("0.0"),
        )
        db.add(wallet)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Register a new user.

    - Schema validates `password == confirm_password` before this runs.
    - Resolves wallet currency from `country` via Rest Countries API (falls back to USD).
    - Auto-initialises Main + Profit wallets in the resolved currency.
    - Returns the standard user profile plus `wallet_currency`.
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Handle referral code if provided
    referrer = None
    if payload.referral_code:
        referrer = db.query(User).filter(User.referral_code == payload.referral_code).first()
        if not referrer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid referral code.",
            )

    # Resolve the user's local currency — never raises, falls back to USD
    currency = get_currency_for_country(payload.country)

    # Generate unique referral code for new user
    referral_code = _generate_unique_referral_code(db)

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        country=payload.country,
        phone=payload.phone,
        is_active=True,
        is_admin=False,
        is_verified=False,
        referral_code=referral_code,
        referred_by_id=referrer.id if referrer else None,
    )
    db.add(user)
    db.flush()                          # populate user.id before wallet FK
    _init_wallets(db, user.id, currency)

    # Increment referrer's referral count
    if referrer:
        referrer.referral_count += 1
        db.flush()

    db.commit()
    db.refresh(user)

    background_tasks.add_task(send_welcome_email, user.email, user.full_name)

    # Extend the standard UserOut with the resolved wallet currency
    user_data = UserOut.model_validate(user).model_dump(mode="json")
    user_data["wallet_currency"] = currency
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=user_data)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact support.",
        )
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete the authenticated user's account.

    Cascade behaviour (defined on the ORM relationships):
      - Wallets (main + profit) → deleted automatically
      - Investments             → deleted automatically
      - Transactions            → wallet FK set to NULL (sender/receiver_wallet_id)

    Returns 204 No Content on success.
    """
    db.delete(current_user)
    db.commit()


@router.post("/kyc/submit", response_model=UserOut, status_code=status.HTTP_200_OK)
def submit_kyc(
    payload: KYCSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit KYC document for verification.

    Updates the user's kyc_status from UNVERIFIED or REJECTED to PENDING,
    and saves the kyc_document_url.
    """
    # Only allow submission if current status is UNVERIFIED or REJECTED
    if current_user.kyc_status not in [KYCStatus.UNVERIFIED, KYCStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"KYC cannot be submitted. Current status: {current_user.kyc_status.value}",
        )

    current_user.kyc_document_url = payload.kyc_document_url
    current_user.kyc_status = KYCStatus.PENDING
    db.commit()
    db.refresh(current_user)
    return current_user

