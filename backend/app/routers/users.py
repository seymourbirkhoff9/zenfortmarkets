"""
app/routers/users.py — User profile and referral endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User
from app.schemas import ReferralStatsResponse, ReferredUser
from app.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])


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
            email=u.email,
            full_name=u.full_name,
            created_at=u.created_at,
        )
        for u in referred_users
    ]

    # Generate referral link
    referral_link = f"https://zenfortmarkets.com/signup?ref={current_user.referral_code}"

    return ReferralStatsResponse(
        referral_code=current_user.referral_code,
        referral_link=referral_link,
        total_referrals=current_user.referral_count,
        total_earned=current_user.total_referral_earned,
        referred_users=referred_users_data,
    )
