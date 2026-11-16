"""
app/routers/public.py — read-only data for the public website (no sign-in).

Only fields that are safe to publish: no deposit addresses, no customer data.
Responses are cached in memory for a minute, so public traffic barely touches
the database, and changes made in the console appear within a minute.
"""
import time
from typing import Callable

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import InvestmentPlan, PaymentMethod, SiteVisitor, User, VisitorPageView
from app.schemas import VisitorTrackRequest
from app.security import SESSION_COOKIE, decode_access_token

router = APIRouter(prefix="/api/public", tags=["Public"])
_TTL = 60
_cache: dict = {}


def _cached(key: str, db: Session, build: Callable[[Session], list]) -> list:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    value = build(db)
    _cache[key] = (time.monotonic(), value)
    return value


def clear_public_cache() -> None:
    _cache.clear()


@router.get("/payment-methods")
def public_payment_methods(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = f"public, max-age={_TTL}"
    return _cached("methods", db, lambda d: [{
        "asset": m.asset, "network": m.network,
        "deposits": bool(m.deposit_enabled), "withdrawals": bool(m.withdraw_enabled),
        "min_deposit": str(m.min_deposit), "min_withdrawal": str(m.min_withdrawal),
        "withdrawal_fee": str(m.withdrawal_fee),
    } for m in d.query(PaymentMethod).filter(PaymentMethod.is_active.is_(True))
        .order_by(PaymentMethod.asset, PaymentMethod.network).all()])


@router.get("/plans")
def public_plans(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = f"public, max-age={_TTL}"
    return _cached("plans", db, lambda d: [{
        "name": p.name, "description": p.description,
        "daily_roi_percent": str(p.daily_roi_percent), "duration_days": p.duration_days,
        "min_amount": str(p.min_amount), "max_amount": str(p.max_amount),
    } for p in d.query(InvestmentPlan).filter(InvestmentPlan.is_active.is_(True))
        .order_by(InvestmentPlan.min_amount).all()])


@router.get("/info")
def public_info():
    return {"base_currency": settings.BASE_CURRENCY}


@router.post("/track")
def track_visitor(payload: VisitorTrackRequest, request: Request, db: Session = Depends(get_db)):
    """Record visitor page view or heartbeat. Safe and non-blocking for public usage."""
    # 1. IP extraction
    ip = (request.headers.get("cf-connecting-ip")
          or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else None))

    # 2. Country extraction
    country = request.headers.get("cf-ipcountry")
    if not country:
        if ip in ("127.0.0.1", "::1", "localhost") or (ip and ip.startswith("192.168.")):
            country = "Localhost"
        else:
            country = "Unknown"

    # 3. Device detection from User-Agent
    ua = request.headers.get("user-agent", "")
    device_type = "Desktop"
    if any(k in ua for k in ("Mobile", "Android", "iPhone")):
        device_type = "Mobile"
    elif any(k in ua for k in ("iPad", "Tablet")):
        device_type = "Tablet"

    # 4. Check for logged in user (optional)
    user_id = None
    token = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    else:
        token = request.cookies.get(SESSION_COOKIE)

    if token:
        try:
            sub = decode_access_token(token)
            if sub:
                u = db.query(User.id).filter(User.email == sub.lower()).first()
                if u:
                    user_id = u[0]
        except Exception:
            pass

    # 5. Upsert visitor
    visitor = db.query(SiteVisitor).filter(SiteVisitor.visitor_id == payload.visitor_id).first()
    path = payload.path.strip() or "/"
    if visitor:
        visitor.last_seen_at = func.now()
        visitor.current_path = path[:255]
        visitor.page_views += 1
        if user_id:
            visitor.user_id = user_id
        if ip:
            visitor.ip_address = ip
        if country and country != "Unknown":
            visitor.country = country
        if payload.referrer and not visitor.referrer:
            visitor.referrer = payload.referrer[:500]
        if ua:
            visitor.user_agent = ua[:500]
        visitor.device_type = device_type
    else:
        visitor = SiteVisitor(
            visitor_id=payload.visitor_id,
            user_id=user_id,
            ip_address=ip,
            country=country,
            current_path=path[:255],
            user_agent=ua[:500] if ua else None,
            device_type=device_type,
            referrer=payload.referrer[:500] if payload.referrer else None,
            page_views=1,
        )
        db.add(visitor)

    # 6. Append page view log
    db.add(VisitorPageView(visitor_id=payload.visitor_id, path=path[:255]))
    db.commit()
    return {"status": "ok"}

