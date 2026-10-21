import uuid
from decimal import Decimal
"""
app/routers/users.py — User profile and referral endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import ReferralStatsResponse, ReferredUser
from app.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}***@{domain}"


# ──────────────────────────────────────────────
# GET /api/users/me/referrals — Referral stats
# ──────────────────────────────────────────────
@router.get("/me/referrals", response_model=ReferralStatsResponse)
def get_referral_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current user's referral statistics and list of referred users."""
    # Get referred users
    referred_users = (
        db.query(User)
        .filter(User.referred_by_id == current_user.id)
        .all()
    )

    referred_users_data = [
        ReferredUser(
            id=u.id,
            email=_mask(u.email),
            full_name=u.full_name,
            created_at=u.created_at,
        )
        for u in referred_users
    ]

    # Generate referral link
    referral_link = f"{settings.FRONTEND_URL.rstrip('/')}/signup.html?ref={current_user.referral_code}"

    return ReferralStatsResponse(
        referral_code=current_user.referral_code,
        referral_link=referral_link,
        total_referrals=current_user.referral_count,
        total_earned=current_user.total_referral_earned,
        referred_users=referred_users_data,
    )


# ──────────────────────────────────────────────
# Combined reads for the customer app (one request per screen)
# ──────────────────────────────────────────────
from sqlalchemy import func as _func, select  # noqa: E402

from app.models import Notification, PaymentMethod, Transaction, UserInvestment, InvestmentPlan, Wallet  # noqa: E402
from app.schemas import PaymentMethodOut, TransactionOut, UserOut, WalletOut  # noqa: E402
from app.services.parallel import run_parallel  # noqa: E402
from app.services.serializers import tx_view  # noqa: E402


def _wallets(user_id):
    return lambda db: [WalletOut.model_validate(w).model_dump(mode="json") for w in
                       db.query(Wallet).filter(Wallet.user_id == user_id).order_by(Wallet.wallet_type).all()]


def _methods(db):
    return [PaymentMethodOut.model_validate(m).model_dump(mode="json") for m in
            db.query(PaymentMethod).filter(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.asset, PaymentMethod.network).all()]


@router.get("/me/context")
def my_context(current_user: User = Depends(get_current_user)):
    """What money dialogs need, fresh, in one request: standing, balances, payment methods."""
    wallets, methods = run_parallel(_wallets(current_user.id), _methods)
    return {"user": UserOut.model_validate(current_user).model_dump(mode="json"),
            "wallets": wallets, "payment_methods": methods}


@router.get("/me/dashboard")
def my_dashboard(current_user: User = Depends(get_current_user)):
    """Customer overview in one request; the independent queries run in parallel."""
    uid = current_user.id

    mine = select(Wallet.id).where(Wallet.user_id == uid).scalar_subquery()
    involves = Transaction.sender_wallet_id.in_(mine) | Transaction.receiver_wallet_id.in_(mine)

    def recent(db):
        return db.query(Transaction).filter(involves).order_by(Transaction.created_at.desc()).limit(8).all()

    def pending(db):
        return db.query(Transaction).filter(involves, Transaction.status == "pending") \
            .order_by(Transaction.created_at.desc()).limit(20).all()

    def investments(db):
        rows = db.query(UserInvestment.amount_invested).filter(UserInvestment.user_id == uid,
                                                               UserInvestment.status == "active").all()
        return {"count": len(rows), "capital": str(sum((r[0] for r in rows), Decimal("0")))}

    def unread(db):
        return db.query(_func.count(Notification.id)).filter(Notification.user_id == uid,
                                                             Notification.is_read.is_(False)).scalar()

    wallets, recent_rows, pending_rows, inv, unread_n = run_parallel(
        _wallets(uid), recent, pending, investments, unread)
    ids = [uuid.UUID(w["id"]) for w in wallets]
    view = lambda rows: [TransactionOut(**tx_view(t, ids)).model_dump(mode="json") for t in rows]  # noqa: E731
    return {"user": UserOut.model_validate(current_user).model_dump(mode="json"), "wallets": wallets,
            "recent": view(recent_rows), "pending": view(pending_rows), "active_investments": inv, "unread": unread_n}
