from __future__ import annotations
"""
app/routers/leaderboard.py — Gamified leaderboard endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from decimal import Decimal

from app.database import get_db
from app.models import User, UserInvestment
from app.schemas import LeaderboardEntry
from app.security import get_current_user

router = APIRouter(prefix="/api/leaderboard", tags=["Leaderboard"])


def _mask_email(email: str) -> str:
    """Mask email for privacy: user***@domain.com"""
    parts = email.split("@")
    if len(parts) != 2:
        return email
    username = parts[0]
    domain = parts[1]
    if len(username) <= 3:
        masked = username[:1] + "***"
    else:
        masked = username[:3] + "***"
    return f"{masked}@{domain}"


# ──────────────────────────────────────────────
# GET /api/leaderboard/referrals — Top referrers
# ──────────────────────────────────────────────
@router.get("/referrals", response_model=List[LeaderboardEntry])
def referral_leaderboard(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Top users ranked by referral count and total referral earnings."""
    # Query users with referrals, ranked by referral_count then total_referral_earned
    users = (
        db.query(User)
        .filter(User.referral_count > 0)
        .order_by(desc(User.referral_count), desc(User.total_referral_earned))
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        LeaderboardEntry(
            rank=idx + 1 + skip,
            username=_mask_email(u.email),
            metric_value=Decimal(str(u.referral_count)),
            created_at=u.created_at,
        )
        for idx, u in enumerate(users)
    ]


# ──────────────────────────────────────────────
# GET /api/leaderboard/investors — Top investors
# ──────────────────────────────────────────────
@router.get("/investors", response_model=List[LeaderboardEntry])
def investor_leaderboard(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Top users ranked by total active investment capital."""
    # Calculate total investment per user
    user_investments = (
        db.query(
            UserInvestment.user_id,
            func.sum(UserInvestment.amount_invested).label("total_invested"),
        )
        .filter(UserInvestment.status == "active")
        .group_by(UserInvestment.user_id)
        .all()
    )

    # Sort by total invested
    sorted_investments = sorted(
        user_investments, key=lambda x: x.total_invested or 0, reverse=True
    )

    # Get user details for top investors
    entries = []
    for idx, (user_id, total) in enumerate(sorted_investments[skip : skip + limit]):
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            entries.append(
                LeaderboardEntry(
                    rank=idx + 1 + skip,
                    username=_mask_email(user.email),
                    metric_value=Decimal(str(total)) if total else Decimal("0"),
                    created_at=user.created_at,
                )
            )

    return entries


# ──────────────────────────────────────────────
# GET /api/leaderboard/veterans — Oldest accounts
# ──────────────────────────────────────────────
@router.get("/veterans", response_model=List[LeaderboardEntry])
def veteran_leaderboard(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Top users ranked by oldest account creation date."""
    users = (
        db.query(User)
        .order_by(User.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        LeaderboardEntry(
            rank=idx + 1 + skip,
            username=_mask_email(u.email),
            metric_value=Decimal("0"),  # No metric value for veterans
            created_at=u.created_at,
        )
        for idx, u in enumerate(users)
    ]
