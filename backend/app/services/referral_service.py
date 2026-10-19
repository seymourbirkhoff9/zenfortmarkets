"""
app/services/referral_service.py — Referral bonus and milestone reward logic
"""
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models import User, Wallet, Transaction
from app.services.notification_service import send_notification_and_email


REFERRAL_BONUS_AMOUNT = Decimal("10.00")  # Configurable bonus amount


def process_referral_milestone(
    db: Session,
    user: User,
    milestone_type: str,  # "first_deposit" or "first_investment"
    amount: Decimal = None,
):
    """
    Process referral milestone rewards.
    
    When a referred user completes their first deposit or investment,
    pay a bonus to the referrer's Main Wallet.
    
    Args:
        db: Database session
        user: The referred user who triggered the milestone
        milestone_type: Type of milestone ("first_deposit" or "first_investment")
        amount: Amount of deposit or investment (for notification details)
    """
    # Check if user was referred
    if not user.referred_by_id:
        return
    
    referrer = db.query(User).filter(User.id == user.referred_by_id).first()
    if not referrer:
        return
    
    # Check if this is the first milestone of this type for this user
    # We'll track this by checking if the referrer has already received a bonus for this user
    # For simplicity, we'll check if the referrer has any referral_bonus transactions for this user
    existing_bonus = (
        db.query(Transaction)
        .filter(
            Transaction.tx_type == "referral_bonus",
            Transaction.description.like(f"%{user.email}%")
        )
        .first()
    )
    
    if existing_bonus:
        return  # Already paid bonus for this user
    
    # Get referrer's main wallet
    main_wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == referrer.id, Wallet.wallet_type == "main")
        .first()
    )
    
    if not main_wallet:
        return
    
    # Credit the bonus
    main_wallet.balance += REFERRAL_BONUS_AMOUNT
    referrer.total_referral_earned += REFERRAL_BONUS_AMOUNT
    
    # Create transaction record
    tx = Transaction(
        receiver_wallet_id=main_wallet.id,
        amount=REFERRAL_BONUS_AMOUNT,
        currency=main_wallet.currency,
        tx_type="referral_bonus",
        description=f"Referral bonus for {user.full_name} ({user.email}) - {milestone_type}",
        status="completed",
    )
    db.add(tx)
    
    db.commit()
    db.refresh(referrer)
    
    # Send notification and email to referrer
    milestone_text = "first deposit" if milestone_type == "first_deposit" else "first investment"
    amount_text = f"${amount}" if amount else ""
    
    send_notification_and_email(
        db=db,
        user=referrer,
        title="Referral Bonus Earned!",
        message=f"Congratulations! You earned ${REFERRAL_BONUS_AMOUNT} as a referral bonus for {user.full_name}'s {milestone_text} {amount_text}.",
        notification_type="referral",
        email_subject=f"Referral Bonus Earned - ${REFERRAL_BONUS_AMOUNT}",
        email_html=f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
          <h2 style="color:#1a1a3e;">Referral Bonus Earned!</h2>
          <p>Hi {referrer.full_name},</p>
          <p>Congratulations! You've earned a referral bonus of <strong>${REFERRAL_BONUS_AMOUNT}</strong>.</p>
          <p>Your referral {user.full_name} just完成 their {milestone_text} {amount_text}.</p>
          <p>The bonus has been credited to your Main Wallet.</p>
          <hr/>
          <small style="color:#888;">Zenfort Markets</small>
        </div>
        """,
    )
