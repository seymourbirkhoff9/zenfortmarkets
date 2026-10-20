"""
app/security.py — password hashing, JWTs, and request authentication.

Authentication sources (checked in order):
  1. `Authorization: Bearer <jwt>`  — used by Swagger, scripts and tests.
  2. httpOnly cookie `zf_session`  — used by the browser frontend.

CSRF: cookie-authenticated requests with an unsafe method (POST/PUT/PATCH/DELETE)
must carry the `X-Requested-With: zenfort` header. Browsers will not attach a
custom header to a cross-site request without a CORS preflight, and our CORS
policy only allows the configured frontend origin.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_COOKIE = "zf_session"
ADMIN_COOKIE = "zf_admin_session"        # the admin's own session, parked while they view as a customer
IMPERSONATION_MINUTES = 30
# While viewing as a customer, these are the only writes allowed.
IMPERSONATION_WRITE_ALLOWLIST = {"/api/auth/impersonation/exit", "/api/auth/logout"}
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "zenfort"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# ── Passwords ─────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Tokens ────────────────────────────────────
def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Session token. `subject` is the user's email (kept for compatibility)."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode({"sub": subject, "exp": expire, "typ": "access"},
                      settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_purpose_token(subject: str, purpose: str, minutes: int) -> str:
    """Single-purpose token (e.g. email verification). Never accepted as a session."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": subject, "exp": expire, "typ": purpose},
                      settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str) -> str:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session has expired. Sign in again." if expected_type == "access"
        else "This link is invalid or has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise exc
    # Tokens minted before this change carry no "typ"; treat those as access tokens only.
    if payload.get("typ", "access") != expected_type:
        raise exc
    sub = payload.get("sub")
    if not sub:
        raise exc
    return sub


def decode_access_token(token: str) -> str:
    return decode_token(token, "access")


def decode_access_payload(token: str) -> dict:
    """Like decode_access_token, but returns the whole payload (for the impersonation claim)."""
    decode_token(token, "access")          # validates signature, expiry and type
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def create_impersonation_token(customer_email: str, admin_email: str) -> str:
    """A short-lived session for `customer_email`, marked with the admin who opened it."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=IMPERSONATION_MINUTES)
    return jwt.encode({"sub": customer_email, "exp": expire, "typ": "access", "imp": admin_email},
                      settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def set_cookie(response: Response, key: str, token: str, minutes: int, path: str = "/") -> None:
    response.set_cookie(key=key, value=token, max_age=minutes * 60, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="lax", path=path)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


# ── Dependencies ──────────────────────────────
def _extract_token(request: Request) -> tuple[Optional[str], bool]:
    """Return (token, came_from_cookie)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    cookie = request.cookies.get(SESSION_COOKIE)
    return (cookie, True) if cookie else (None, False)


def get_current_user(request: Request, db: Session = Depends(get_db)):
    from app.models import User  # local import avoids a circular dependency

    token, from_cookie = _extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue.")

    if from_cookie and request.method in UNSAFE_METHODS:
        if request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF header.")

    payload = decode_access_payload(token)
    impersonator = payload.get("imp")
    # View-only: an admin viewing as a customer can read everything but change nothing.
    # Enforced here, on the server, so no client can bypass it.
    if impersonator and request.method in UNSAFE_METHODS and request.url.path not in IMPERSONATION_WRITE_ALLOWLIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="View only: you're viewing this account as an admin. Exit to make changes.")

    user = db.query(User).filter(User.email == payload["sub"]).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is deactivated.")
    user.impersonated_by = impersonator      # not a column: read by UserOut so the UI can show the banner
    if impersonator:
        user.impersonation_expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    return user


def get_current_admin(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user
