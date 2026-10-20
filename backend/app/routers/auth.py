"""
app/routers/auth.py — sign up, sessions, email verification, profile and KYC.
"""
import secrets
import string
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AuditLog, KYCStatus, User, Wallet
from app.schemas import (
    EmailVerifyRequest, KYCSubmitRequest, LoginRequest, SignUpRequest, TokenResponse, UserOut,
)
from app.security import (
    ADMIN_COOKIE, CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE, decode_access_payload, decode_access_token,
    clear_session_cookie, create_access_token, create_purpose_token, decode_token,
    get_current_user, hash_password, set_session_cookie, verify_password,
)
from app.services.admin_alerts import notify_admins
from app.services.email_templates import render_email
from app.services.notification_service import queue_email
from app.utils.uploads import DOCUMENT_TYPES, validate_data_url

router = APIRouter(prefix="/api/auth", tags=["Auth"])

VERIFY_PURPOSE = "email_verify"
VERIFY_MINUTES = 60 * 24
_ALPHABET = string.ascii_uppercase + string.digits


def _generate_unique_referral_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        if not db.query(User.id).filter(User.referral_code == code).first():
            return code


def _send_verification(user: User) -> None:
    token = create_purpose_token(user.email, VERIFY_PURPOSE, VERIFY_MINUTES)
    link = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email.html?token={token}"
    queue_email(user.email, "Confirm your email — Zenfort Markets",
                render_email("Confirm your email", user.full_name,
                             ["Confirm this address so we can reach you about deposits and withdrawals.",
                              "The link expires in 24 hours."],
                             cta=("Confirm email", link)))


# ── Sign up / sessions ────────────────────────
@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    referrer = None
    if payload.referral_code:
        referrer = db.query(User).filter(User.referral_code == payload.referral_code.strip().upper()).first()
        if not referrer:
            raise HTTPException(status_code=400, detail="That referral code doesn't exist.")

    user = User(
        email=email, full_name=payload.full_name.strip(), hashed_password=hash_password(payload.password),
        country=payload.country.value if hasattr(payload.country, "value") else payload.country,
        phone=payload.phone, is_active=True, is_admin=False, is_verified=False, email_verified=False,
        referral_code=_generate_unique_referral_code(db),
        referred_by_id=referrer.id if referrer else None,
    )
    db.add(user)
    db.flush()
    for wtype in ("main", "profit"):
        db.add(Wallet(user_id=user.id, wallet_type=wtype, currency=settings.BASE_CURRENCY, balance=Decimal("0")))
    if referrer:
        referrer.referral_count += 1
    db.commit()
    db.refresh(user)
    _send_verification(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is deactivated. Contact support.")
    token = create_access_token(subject=user.email)
    set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)
    response.delete_cookie(ADMIN_COOKIE, path="/api/auth")
    response.status_code = 204
    return response


@router.post("/impersonation/exit")
def exit_impersonation(request: Request, response: Response, db: Session = Depends(get_db)):
    """Restore the admin's own session after viewing as a customer. Works even if the view-only session expired."""
    if request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
        raise HTTPException(status_code=403, detail="Missing CSRF header.")
    admin_token = request.cookies.get(ADMIN_COOKIE)
    if not admin_token:
        raise HTTPException(status_code=400, detail="You're not viewing as a customer.")
    admin = db.query(User).filter(User.email == decode_access_token(admin_token)).first()
    if not admin or not admin.is_admin or not admin.is_active:
        response.delete_cookie(ADMIN_COOKIE, path="/api/auth")
        raise HTTPException(status_code=401, detail="Sign in again.")

    target = None
    try:
        payload = decode_access_payload(request.cookies.get(SESSION_COOKIE, ""))
        if payload.get("imp") == admin.email:
            target = db.query(User).filter(User.email == payload["sub"]).first()
    except HTTPException:
        pass            # the view-only session already expired; still restore the admin
    db.add(AuditLog(admin_id=admin.id, action="IMPERSONATE_END", target_user_id=target.id if target else None,
                    details=f"Stopped viewing as {target.email}" if target else "View-only session ended"))
    db.commit()

    set_session_cookie(response, admin_token)
    response.delete_cookie(ADMIN_COOKIE, path="/api/auth")
    return {"redirect": f"/admin.html#/customers/{target.id}" if target else "/admin.html"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── Email verification ────────────────────────
@router.post("/verify-email", response_model=UserOut)
def verify_email(payload: EmailVerifyRequest, db: Session = Depends(get_db)):
    """Consume the signed link sent by email. Works without being signed in."""
    email = decode_token(payload.token, VERIFY_PURPOSE)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired.")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
        db.refresh(user)
    return user


@router.post("/resend-verification", status_code=202)
def resend_verification(current_user: User = Depends(get_current_user)):
    if current_user.email_verified:
        return {"status": "already_verified"}
    _send_verification(current_user)
    return {"status": "sent"}


# ── Profile ───────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Name can't be empty.")
        return v.strip() if v else v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong(cls, v):
        if len(v) < 8:
            raise ValueError("Use at least 8 characters.")
        return v


@router.patch("/me", response_model=UserOut)
def update_profile(payload: ProfileUpdate, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.phone is not None:
        current_user.phone = payload.phone.strip() or None
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password", status_code=204)
def change_password(payload: PasswordChange, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=204)


@router.delete("/account", status_code=204)
def delete_account(response: Response, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """
    Close the account. Financial records are retained, so the row is
    deactivated and anonymised instead of hard-deleted (a hard delete would
    also violate the transactions → wallets foreign key).
    """
    if current_user.is_admin:
        raise HTTPException(status_code=400, detail="Admin accounts can't be closed from here.")
    wallets = db.query(Wallet).filter(Wallet.user_id == current_user.id).all()
    if any(w.balance > 0 for w in wallets):
        raise HTTPException(status_code=400, detail="Withdraw your remaining balance before closing the account.")
    current_user.is_active = False
    current_user.email = f"deleted+{uuid.uuid4().hex[:12]}@deleted.invalid"
    current_user.full_name = "Closed account"
    current_user.phone = None
    current_user.kyc_document_url = None
    db.commit()
    clear_session_cookie(response)
    response.status_code = 204
    return response


# ── KYC ───────────────────────────────────────
@router.post("/kyc/submit", response_model=UserOut)
def submit_kyc(payload: KYCSubmitRequest, current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if current_user.kyc_status not in (KYCStatus.UNVERIFIED, KYCStatus.REJECTED):
        raise HTTPException(status_code=400,
                            detail=f"Your verification is already {current_user.kyc_status.value.lower()}.")
    current_user.kyc_document_url = validate_data_url(payload.kyc_document_url, DOCUMENT_TYPES, "ID document")
    current_user.kyc_status = KYCStatus.PENDING
    current_user.kyc_rejection_reason = None
    notify_admins(db, "Identity check submitted", f"{current_user.email} submitted an ID document.", "kyc")
    db.commit()
    db.refresh(current_user)
    return current_user
