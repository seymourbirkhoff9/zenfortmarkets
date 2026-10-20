"""
app/services/referral_service.py — one-time bonus to a referrer.

The bonus is paid once per referred user, on their first qualifying event
(first approved deposit or first investment, whichever comes first).
Idempotency is enforced by a tag stored on the ledger row.
"""
import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Transaction, User
from app.services.email_templates import render_email, usd
from app.services.ledger import credit, lock_wallet, money
from app.services.notification_service import send_notification_and_email


logger = logging.getLogger("zenfort.referrals")


def _tag(user: User) -> str:
    return f"[ref:{user.id}]"


def process_referral_milestone(db: Session, user: User, milestone_type: str, amount: Decimal | None = None):
    """
    Best-effort side effect. It runs after the deposit/investment has already
    committed, so it must never raise: a failure here would make the API report
    an error for an action that actually succeeded.
    """
    try:
        _pay_bonus(db, user, milestone_type)
    except Exception:
        db.rollback()
        logger.exception("Referral bonus failed for user %s (%s)", getattr(user, "id", None), milestone_type)


def _pay_bonus(db: Session, user: User, milestone_type: str) -> None:
    if not user or not user.referred_by_id:
        return
    referrer = db.query(User).filter(User.id == user.referred_by_id, User.is_active.is_(True)).first()
    if not referrer or referrer.is_admin:     # staff codes don't earn bonuses (and have no wallets)
        return
    if db.query(Transaction.id).filter(Transaction.tx_type == "referral_bonus",
                                      Transaction.description.contains(_tag(user))).first():
        return

    bonus = money(settings.REFERRAL_BONUS_AMOUNT)
    wallet = lock_wallet(db, referrer.id, "main")
    credit(wallet, bonus)
    referrer.total_referral_earned = Decimal(referrer.total_referral_earned or 0) + bonus
    event = "first deposit" if milestone_type == "first_deposit" else "first investment"
    db.add(Transaction(receiver_wallet_id=wallet.id, amount=bonus, currency=settings.BASE_CURRENCY,
                       tx_type="referral_bonus", status="completed",
                       description=f"Referral bonus: {user.full_name}'s {event} {_tag(user)}"))
    db.commit()

    msg = f"You earned {usd(bonus)} because {user.full_name} made their {event}."
    send_notification_and_email(
        db=db, user=referrer, title="Referral bonus earned", message=msg, notification_type="referral",
        email_subject="Referral bonus earned — Zenfort Markets",
        email_html=render_email("Referral bonus earned", referrer.full_name,
                                [msg, "It's already in your Main wallet."]),
    )
