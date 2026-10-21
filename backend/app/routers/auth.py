"""
app/routers/auth.py — sign up, sessions, email verification, profile and KYC.
"""
import hashlib
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AuditLog, KYCStatus, User, Wallet
from app.schemas import (
    AvatarUpload, EmailVerifyRequest, KYCSubmitRequest, LoginRequest, SignUpRequest, TokenResponse, UserOut,
)
from app.security import (
    ADMIN_COOKIE, CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE, decode_access_payload, decode_access_token,
    clear_session_cookie, create_access_token, create_purpose_token, decode_token,
    get_current_user, hash_password, set_session_cookie, verify_password,
)
from app.services.admin_alerts import notify_admins
from app.services.email_templates import render_email
from app.services.notification_service import queue_email
from app.services import ratelimit, storage, twofactor
from app.services.ratelimit import client_ip
from app.utils.uploads import DOCUMENT_TYPES, IMAGE_TYPES, validate_data_url

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
        terms_version=settings.TERMS_VERSION, terms_accepted_at=datetime.now(timezone.utc),
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


def _start_session(response: Response, user: User) -> dict:
    token = create_access_token(subject=user.email, session_version=user.session_version or 0)
    set_session_cookie(response, token)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Password sign-in. If two-factor is on, returns {"two_factor_required": true, "challenge": …}
    instead of a session; finish with POST /login/2fa.
    """
    email = payload.email.lower().strip()
    # Only failed attempts count; a successful sign-in clears them.
    key = f"login:{client_ip(request)}:{email}"
    ratelimit.check(key, 10, 15 * 60, "Too many sign-in attempts. Wait 15 minutes, or reset your password.")
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        ratelimit.hit(key)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    ratelimit.reset(key)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is deactivated. Contact support.")
    if user.totp_enabled:
        return {"two_factor_required": True,
                "challenge": create_purpose_token(user.email, TWO_FA_PURPOSE, 5)}
    return _start_session(response, user)


class TwoFactorLogin(BaseModel):
    challenge: str
    code: str


@router.post("/login/2fa")
def login_two_factor(payload: TwoFactorLogin, response: Response, db: Session = Depends(get_db)):
    """Second step of sign-in: a 6-digit authenticator code or a recovery code."""
    try:
        email = decode_token(payload.challenge, TWO_FA_PURPOSE)
    except HTTPException:
        raise HTTPException(status_code=401, detail="That took too long. Sign in again.")
    ratelimit.check(f"2fa:{email}", 5, 10 * 60, "Too many incorrect codes. Wait 10 minutes and try again.")
    user = db.query(User).filter(User.email == email).with_for_update().first()
    if not user or not user.is_active or not user.totp_enabled:
        raise HTTPException(status_code=401, detail="Sign in again.")
    step = twofactor.check_code(user.totp_secret, payload.code, user.totp_last_step)
    if step is not None:
        user.totp_last_step = step
    else:
        remaining_codes = twofactor.use_recovery_code(user.recovery_codes, payload.code)
        if remaining_codes is None:
            db.rollback()
            ratelimit.hit(f"2fa:{email}")
            raise HTTPException(status_code=400, detail="That code isn’t right. Check your authenticator app and try again.")
        user.recovery_codes = remaining_codes
        left = twofactor.remaining(remaining_codes)
        queue_email(user.email, "A recovery code was used — Zenfort Markets",
                    render_email("A recovery code was used", user.full_name,
                                 [f"You signed in with a recovery code. You have {left} left.",
                                  "If this wasn’t you, reset your password now and contact support."]))
    db.commit()
    ratelimit.reset(f"2fa:{email}")
    return _start_session(response, user)


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
def change_password(payload: PasswordChange, response: Response, current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Signs out every other device; this one stays signed in with a fresh session."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.session_version = (current_user.session_version or 0) + 1
    db.commit()
    _start_session(response, current_user)
    _security_email(current_user, "Your password was changed", "Your Zenfort Markets password was just changed.")
    response.status_code = 204
    return response


def _security_email(user: User, heading: str, line: str) -> None:
    queue_email(user.email, f"{heading} — Zenfort Markets",
                render_email(heading, user.full_name, [line, "If this wasn’t you, reset your password now and contact support."],
                             cta=("Reset password", f"{settings.FRONTEND_URL.rstrip('/')}/forgot-password.html")))


# ── Password reset by email ───────────────────
RESET_PURPOSE = "pwd_reset"
RESET_MINUTES = 30


def _password_fingerprint(user: User) -> str:
    """Changes whenever the password changes, so a reset link works only once."""
    return hashlib.sha256(user.hashed_password.encode()).hexdigest()[:16]


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong(cls, v):
        if len(v) < 8:
            raise ValueError("Use at least 8 characters.")
        return v


@router.post("/forgot-password", status_code=202)
def forgot_password(payload: ForgotPassword, request: Request, db: Session = Depends(get_db)):
    """Always answers the same way, so it can't be used to discover who has an account."""
    email = payload.email.lower().strip()
    ratelimit.limit(f"forgot:{client_ip(request)}", 10, 60 * 60)
    ratelimit.limit(f"forgot:{email}", 3, 60 * 60)
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user:
        token = jwt.encode({"sub": user.email, "typ": RESET_PURPOSE, "ph": _password_fingerprint(user),
                            "exp": datetime.now(timezone.utc) + timedelta(minutes=RESET_MINUTES)},
                           settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password.html?token={token}"
        queue_email(user.email, "Reset your password — Zenfort Markets",
                    render_email("Reset your password", user.full_name,
                                 ["We received a request to reset your password. The link works once and expires in 30 minutes.",
                                  "If you didn’t ask for this, you can ignore this email; your password stays the same."],
                                 cta=("Choose a new password", link)))
    return {"status": "sent", "message": "If an account uses that email, we’ve sent a reset link. Check your inbox and spam folder."}


@router.post("/reset-password")
def reset_password(payload: ResetPassword, db: Session = Depends(get_db)):
    expired = HTTPException(status_code=400, detail="This reset link is invalid or has expired. Request a new one.")
    try:
        claims = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise expired
    if claims.get("typ") != RESET_PURPOSE:
        raise expired
    user = db.query(User).filter(User.email == claims.get("sub"), User.is_active.is_(True)).with_for_update().first()
    if not user or claims.get("ph") != _password_fingerprint(user):
        raise expired                              # already used, or the password changed since
    user.hashed_password = hash_password(payload.new_password)
    user.session_version = (user.session_version or 0) + 1     # sign out everywhere
    db.commit()
    _security_email(user, "Your password was reset", "Your Zenfort Markets password was just reset using an emailed link.")
    return {"status": "ok", "message": "Password updated. Sign in with your new password."}


# ── Two-factor sign-in (authenticator app) ─────
TWO_FA_PURPOSE = "2fa_challenge"


class PasswordConfirm(BaseModel):
    password: str


class CodeConfirm(BaseModel):
    code: str


class DisableTwoFactor(BaseModel):
    password: str
    code: str


@router.get("/2fa")
def two_factor_status(current_user: User = Depends(get_current_user)):
    return {"enabled": bool(current_user.totp_enabled),
            "recovery_codes_left": twofactor.remaining(current_user.recovery_codes) if current_user.totp_enabled else 0}


@router.post("/2fa/setup")
def two_factor_setup(payload: PasswordConfirm, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Step 1: create a new secret (not active until confirmed with a code)."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect.")
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="Two-factor sign-in is already on.")
    secret, encrypted = twofactor.new_secret()
    current_user.totp_secret = encrypted
    current_user.totp_last_step = None
    db.commit()
    return {"secret": secret, "otpauth_uri": twofactor.provisioning_uri(secret, current_user.email)}


@router.post("/2fa/enable")
def two_factor_enable(payload: CodeConfirm, response: Response, current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """Step 2: prove the app works, then turn it on. Returns recovery codes ONCE."""
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="Two-factor sign-in is already on.")
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Start setup first.")
    step = twofactor.check_code(current_user.totp_secret, payload.code, None)
    if step is None:
        raise HTTPException(status_code=400, detail="That code isn’t right. Make sure your phone’s clock is correct and try the newest code.")
    codes, hashed = twofactor.new_recovery_codes()
    current_user.totp_enabled, current_user.totp_last_step, current_user.recovery_codes = True, step, hashed
    current_user.session_version = (current_user.session_version or 0) + 1      # other devices must sign in again
    db.commit()
    _start_session(response, current_user)
    _security_email(current_user, "Two-factor sign-in turned on", "Two-factor sign-in is now on for your account.")
    return {"enabled": True, "recovery_codes": codes}


@router.post("/2fa/disable")
def two_factor_disable(payload: DisableTwoFactor, response: Response, current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if not current_user.totp_enabled:
        return {"enabled": False}
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect.")
    ok = twofactor.check_code(current_user.totp_secret, payload.code, current_user.totp_last_step) is not None \
        or twofactor.use_recovery_code(current_user.recovery_codes, payload.code) is not None
    if not ok:
        raise HTTPException(status_code=400, detail="That code isn’t right.")
    current_user.totp_enabled, current_user.totp_secret = False, None
    current_user.totp_last_step, current_user.recovery_codes = None, None
    current_user.session_version = (current_user.session_version or 0) + 1
    db.commit()
    _start_session(response, current_user)
    _security_email(current_user, "Two-factor sign-in turned off", "Two-factor sign-in was turned off for your account.")
    return {"enabled": False}


@router.post("/2fa/recovery-codes")
def two_factor_new_codes(payload: DisableTwoFactor, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Replace all recovery codes (old ones stop working). Needs password + a current code."""
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="Two-factor sign-in is off.")
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect.")
    step = twofactor.check_code(current_user.totp_secret, payload.code, current_user.totp_last_step)
    if step is None:
        raise HTTPException(status_code=400, detail="That code isn’t right.")
    codes, hashed = twofactor.new_recovery_codes()
    current_user.recovery_codes, current_user.totp_last_step = hashed, step
    db.commit()
    return {"recovery_codes": codes}


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
    old_files = (current_user.kyc_document_url, current_user.avatar_url)
    current_user.kyc_document_url = None
    current_user.avatar_url = None
    db.commit()
    for ref in old_files:
        storage.remove(ref)
    clear_session_cookie(response)
    response.status_code = 204
    return response


# ── Consent and profile photo ─────────────────
@router.post("/accept-terms", response_model=UserOut)
def accept_terms(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Record acceptance of the current Terms and Privacy Policy (asked again when they change)."""
    current_user.terms_version = settings.TERMS_VERSION
    current_user.terms_accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/avatar", response_model=UserOut)
def upload_avatar(payload: AvatarUpload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    image = validate_data_url(payload.image, IMAGE_TYPES, "Profile photo")
    old = current_user.avatar_url
    current_user.avatar_url = storage.store(image, f"{current_user.id}", private=False)
    db.commit()
    db.refresh(current_user)
    storage.remove(old)               # after the commit: never lose the new photo over a cleanup failure
    return current_user


@router.delete("/avatar", response_model=UserOut)
def remove_avatar(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    old = current_user.avatar_url
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    storage.remove(old)
    return current_user


# ── KYC ───────────────────────────────────────
@router.post("/kyc/submit", response_model=UserOut)
def submit_kyc(payload: KYCSubmitRequest, current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if current_user.kyc_status not in (KYCStatus.UNVERIFIED, KYCStatus.REJECTED):
        raise HTTPException(status_code=400,
                            detail=f"Your verification is already {current_user.kyc_status.value.lower()}.")
    doc = validate_data_url(payload.kyc_document_url, DOCUMENT_TYPES, "ID document")
    old = current_user.kyc_document_url
    current_user.kyc_document_url = storage.store(doc, f"kyc/{current_user.id}", private=True)
    current_user.kyc_status = KYCStatus.PENDING
    current_user.kyc_rejection_reason = None
    notify_admins(db, "Identity check submitted", f"{current_user.email} submitted an ID document.", "kyc")
    db.commit()
    db.refresh(current_user)
    storage.remove(old)
    return current_user
