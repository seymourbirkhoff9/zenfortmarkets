"""
app/routers/admin.py — admin operations console API.

Every state change that touches money or a user's standing:
  * runs inside one DB transaction with the affected wallet rows locked,
  * records who reviewed it and when,
  * writes an AuditLog row in the same transaction,
  * notifies the user in-app (and by email, in the background).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    AuditLog, InvestmentPlan, KYCStatus, PaymentMethod, Transaction, User, UserInvestment, Wallet,
)
from app.schemas import (
    AdminCreditRequest, AdminDebitRequest, AdminDepositReviewRequest, AdminKYCReviewRequest,
    AdminStats, AdminTransactionOut, AdminUserDetail, AdminUserStatusUpdate,
    AdminWithdrawalReviewRequest, AuditLogResponse, InvestmentPlanCreate, InvestmentPlanResponse,
    InvestmentPlanUpdate, PaymentMethodCreate, PaymentMethodOut, PaymentMethodUpdate, RoleUpdate, UserOut, UserPage,
)
from app.security import (
    ADMIN_COOKIE, IMPERSONATION_MINUTES, SESSION_COOKIE, _extract_token, create_impersonation_token,
    get_current_admin, set_cookie,
)
from app.services.email_templates import render_email, usd
from app.services.ledger import credit, debit, lock_wallet, lock_wallet_by_id, money
from app.services.notification_service import send_notification_and_email
from app.services.referral_service import process_referral_milestone
from app.services.parallel import run_parallel
from app.services.roi import run_roi_accrual
from app.services.serializers import admin_tx_view, tx_view

router = APIRouter(prefix="/api/admin", tags=["Admin"])
CUR = settings.BASE_CURRENCY


# ── helpers ───────────────────────────────────
def _audit(db: Session, admin: User, action: str, target_user_id=None, details: str = "") -> None:
    """Queue an audit row. The caller's commit makes it atomic with the change it describes."""
    db.add(AuditLog(admin_id=admin.id, action=action, target_user_id=target_user_id, details=details))


def _notify(db: Session, user: User, title: str, message: str, kind: str, extra: list[str] | None = None):
    send_notification_and_email(
        db=db, user=user, title=title, message=message, notification_type=kind,
        email_subject=f"{title} — Zenfort Markets",
        email_html=render_email(title, user.full_name, [message, *(extra or [])]),
    )


def _get_user(db: Session, user_id=None, email: Optional[str] = None) -> User:
    q = db.query(User)
    user = q.filter(User.id == user_id).first() if user_id else q.filter(User.email == (email or "").lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def _owner_of(db: Session, tx: Transaction) -> Optional[User]:
    wallet_id = tx.receiver_wallet_id if tx.tx_type in ("deposit", "admin_credit", "roi_credit",
                                                         "principal_return", "referral_bonus") \
        else tx.sender_wallet_id or tx.receiver_wallet_id
    if not wallet_id:
        return None
    return db.query(User).join(Wallet, Wallet.user_id == User.id).filter(Wallet.id == wallet_id).first()


def _with_owners(db: Session, txs: list[Transaction]) -> list[dict]:
    wallet_ids = {w for t in txs for w in (t.sender_wallet_id, t.receiver_wallet_id) if w}
    owners = dict(db.query(Wallet.id, User).join(User, User.id == Wallet.user_id)
                  .filter(Wallet.id.in_(wallet_ids)).all()) if wallet_ids else {}
    out = []
    for t in txs:
        primary = t.sender_wallet_id if t.tx_type in ("withdrawal", "admin_debit", "investment", "p2p") \
            else (t.receiver_wallet_id or t.sender_wallet_id)
        out.append(admin_tx_view(t, owners.get(primary)))
    return out


def _revalidate(model, data: dict) -> None:
    """Validate the merged result of a partial update; surface failures as 422, not 500."""
    try:
        model(**data)
    except ValidationError as e:
        msg = "; ".join(err["msg"].removeprefix("Value error, ") for err in e.errors())
        raise HTTPException(status_code=422, detail=msg)


def _parse_status(value: str) -> str:
    return "completed" if value in ("approved", "completed") else value


# ── Overview ──────────────────────────────────
def _stats_parts(now: datetime):
    """Four aggregate queries (instead of ~12) that can run in parallel."""
    since7, since30 = now - timedelta(days=7), now - timedelta(days=30)
    T, U = Transaction, User
    pend, done30 = (T.status == "pending"), (T.status == "completed") & (T.created_at >= since30)
    is_dep, is_wd = (T.tx_type == "deposit"), (T.tx_type == "withdrawal")

    def tx_agg(db):
        return db.query(
            func.count().filter(is_dep & pend), func.coalesce(func.sum(T.amount).filter(is_dep & pend), 0),
            func.min(T.created_at).filter(is_dep & pend),
            func.count().filter(is_wd & pend), func.coalesce(func.sum(T.amount).filter(is_wd & pend), 0),
            func.min(T.created_at).filter(is_wd & pend),
            func.coalesce(func.sum(T.amount).filter(is_dep & done30), 0),
            func.coalesce(func.sum(T.amount).filter(is_wd & done30), 0),
        ).filter(T.tx_type.in_(("deposit", "withdrawal"))).one()

    def user_agg(db):
        cust = U.is_admin.is_(False)
        kyc = U.kyc_status == KYCStatus.PENDING
        return db.query(
            func.count().filter(cust), func.count().filter(cust & (U.created_at >= since7)),
            func.count().filter(cust & U.is_blocked.is_(True)), func.count().filter(kyc),
            func.min(func.coalesce(U.updated_at, U.created_at)).filter(kyc),
        ).one()

    def wallet_agg(db):
        return db.query(
            func.coalesce(func.sum(Wallet.balance).filter(Wallet.wallet_type == "main"), 0),
            func.coalesce(func.sum(Wallet.balance).filter(Wallet.wallet_type == "profit"), 0),
        ).join(User, User.id == Wallet.user_id).filter(User.is_admin.is_(False)).one()

    def inv_agg(db):
        return db.query(func.count(UserInvestment.id), func.coalesce(func.sum(UserInvestment.amount_invested), 0)) \
            .filter(UserInvestment.status == "active").one()

    return tx_agg, user_agg, wallet_agg, inv_agg


def _compose_stats(tx, us, wa, inv) -> dict:
    return dict(
        users_total=us[0], users_new_7d=us[1], users_blocked=us[2], pending_kyc=us[3],
        pending_deposits=tx[0], pending_deposits_amount=tx[1],
        pending_withdrawals=tx[3], pending_withdrawals_amount=tx[4],
        deposits_completed_30d=tx[6], withdrawals_completed_30d=tx[7],
        total_main_balance=wa[0], total_profit_balance=wa[1],
        active_investments=inv[0], active_investment_capital=inv[1],
    )


@router.get("/stats", response_model=AdminStats)
def stats(admin=Depends(get_current_admin)):
    tx, us, wa, inv = run_parallel(*_stats_parts(datetime.now(timezone.utc)))
    return AdminStats(**_compose_stats(tx, us, wa, inv))


@router.get("/queue-counts")
def queue_counts(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Sidebar badges. One query; polled every 30 s."""
    T = Transaction
    pend = T.status == "pending"
    dep = select(func.count()).where(T.tx_type == "deposit", pend).scalar_subquery()
    wd = select(func.count()).where(T.tx_type == "withdrawal", pend).scalar_subquery()
    kyc = select(func.count()).where(User.kyc_status == KYCStatus.PENDING).scalar_subquery()
    d, w, k = db.execute(select(dep, wd, kyc)).one()
    return {"deposits": d, "withdrawals": w, "kyc": k}


@router.get("/overview")
def overview(admin=Depends(get_current_admin)):
    """Everything the admin overview needs, in one request with parallel queries."""
    def recent(db):
        rows = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(8).all()
        return _with_owners(db, rows)

    tx, us, wa, inv, latest = run_parallel(*_stats_parts(datetime.now(timezone.utc)), recent)
    return {
        "stats": AdminStats(**_compose_stats(tx, us, wa, inv)).model_dump(mode="json"),
        "oldest": {"deposit": tx[2], "withdrawal": tx[5], "kyc": us[4]},
        "recent": [AdminTransactionOut(**r).model_dump(mode="json") for r in latest],
    }


# ── Users ─────────────────────────────────────
@router.get("/users", response_model=UserPage)
def list_users(
    q: Optional[str] = Query(None, description="Search email or name"),
    filter: Optional[str] = Query(None, pattern="^(blocked|kyc_pending|admins|inactive)$"),
    skip: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200),
    admin=Depends(get_current_admin), db: Session = Depends(get_db),
):
    query = db.query(User)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if filter == "blocked":
        query = query.filter(User.is_blocked.is_(True))
    elif filter == "kyc_pending":
        query = query.filter(User.kyc_status == KYCStatus.PENDING)
    elif filter == "admins":
        query = query.filter(User.is_admin.is_(True))
    elif filter == "inactive":
        query = query.filter(User.is_active.is_(False))
    total = query.count()
    items = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return UserPage(total=total, items=items)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def user_detail(user_id: str, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Everything about one customer in one call: profile, balances, investments, recent ledger."""
    user = _get_user(db, user_id=user_id)
    wallets = db.query(Wallet).filter(Wallet.user_id == user.id).order_by(Wallet.wallet_type).all()
    ids = [w.id for w in wallets]
    txs = (db.query(Transaction)
           .filter(Transaction.sender_wallet_id.in_(ids) | Transaction.receiver_wallet_id.in_(ids))
           .order_by(Transaction.created_at.desc()).limit(50).all()) if ids else []
    plans = dict(db.query(InvestmentPlan.id, InvestmentPlan.name).all())
    invs = db.query(UserInvestment).filter(UserInvestment.user_id == user.id) \
        .order_by(UserInvestment.created_at.desc()).all()
    referrer = db.query(User.email).filter(User.id == user.referred_by_id).scalar() if user.referred_by_id else None
    return {
        "user": user, "wallets": wallets,
        "investments": [{**{c: getattr(i, c) for c in (
            "id", "plan_id", "amount_invested", "daily_roi_percent", "duration_days", "total_earned",
            "status", "start_date", "maturity_date", "created_at", "days_paid")},
            "plan_name": plans.get(i.plan_id)} for i in invs],
        "transactions": [tx_view(t, ids) for t in txs],
        "referred_by_email": referrer,
    }


@router.patch("/users/{user_id}/status", response_model=UserOut)
def update_user_status(user_id: str, payload: AdminUserStatusUpdate,
                       admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    user = _get_user(db, user_id=user_id)
    if user.id == admin.id and (payload.is_blocked or payload.is_active is False):
        raise HTTPException(status_code=400, detail="You can't restrict your own admin account.")

    changes, notices = [], []
    for field, on_msg, off_msg in (
        ("is_blocked", "Your account has been restricted. Contact support for details.",
         "Your account restriction has been lifted."),
        ("can_deposit", "Deposits are turned back on for your account.",
         "Deposits have been turned off for your account. Contact support for details."),
        ("can_withdraw", "Withdrawals are turned back on for your account.",
         "Withdrawals have been turned off for your account. Contact support for details."),
        ("is_active", None, None),
    ):
        new = getattr(payload, field)
        if new is None or new == getattr(user, field):
            continue
        setattr(user, field, new)
        changes.append(f"{field}={new}")
        if on_msg:
            notices.append(on_msg if new else off_msg)

    if not changes:
        return user
    action = "BLOCK_USER" if payload.is_blocked else "UNBLOCK_USER" if payload.is_blocked is False else "UPDATE_USER_FLAGS"
    _audit(db, admin, action, user.id, ", ".join(changes))
    db.commit()
    db.refresh(user)
    for msg in notices:
        _notify(db, user, "Account update", msg, "account")
    return user


@router.patch("/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: str, payload: RoleUpdate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Promote a customer to admin, or remove admin rights."""
    user = _get_user(db, user_id=user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You can't change your own role. Ask another admin.")
    if user.is_admin == payload.is_admin:
        return user
    if payload.is_admin and not user.is_active:
        raise HTTPException(status_code=400, detail="Reopen this account before making it an admin.")
    if not payload.is_admin:
        # Lock the admin rows (Postgres can't lock an aggregate) so two simultaneous demotions can't both pass.
        admins = db.query(User.id).filter(User.is_admin.is_(True), User.is_active.is_(True)).with_for_update().all()
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="There must always be at least one admin.")
    user.is_admin = payload.is_admin
    _audit(db, admin, "PROMOTE_ADMIN" if payload.is_admin else "DEMOTE_ADMIN", user.id,
           f"{user.email} {'given' if payload.is_admin else 'removed from'} admin access")
    db.commit()
    db.refresh(user)
    _notify(db, user, "Account role changed",
            "You now have admin access to the operations console." if payload.is_admin
            else "Your admin access has been removed.", "account")
    return user


@router.post("/users/{user_id}/impersonate")
def impersonate(user_id: str, request: Request, response: Response,
                admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    View the app as this customer, read-only, for troubleshooting.
    The admin's own session is parked in a separate httpOnly cookie that only
    /api/auth/* receives, and restored by POST /api/auth/impersonation/exit.
    """
    user = _get_user(db, user_id=user_id)
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Admin accounts can't be viewed this way.")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="This account is closed.")
    admin_token, _ = _extract_token(request)
    set_cookie(response, ADMIN_COOKIE, admin_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES, path="/api/auth")
    set_cookie(response, SESSION_COOKIE, create_impersonation_token(user.email, admin.email), IMPERSONATION_MINUTES)
    _audit(db, admin, "IMPERSONATE_START", user.id, f"Viewing as {user.email} (read-only, {IMPERSONATION_MINUTES} min)")
    db.commit()
    return {"redirect": "/app.html", "expires_in_minutes": IMPERSONATION_MINUTES}


@router.patch("/users/{user_id}/activate", response_model=UserOut, deprecated=True)
def activate_user(user_id: str, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return update_user_status(user_id, AdminUserStatusUpdate(is_active=True), admin, db)


@router.patch("/users/{user_id}/deactivate", response_model=UserOut, deprecated=True)
def deactivate_user(user_id: str, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return update_user_status(user_id, AdminUserStatusUpdate(is_active=False), admin, db)


# ── Manual balance adjustments ────────────────
@router.post("/credit", response_model=AdminTransactionOut, status_code=201)
def credit_user_wallet(payload: AdminCreditRequest, admin=Depends(get_current_admin),
                       db: Session = Depends(get_db)):
    user = _get_user(db, user_id=payload.user_id, email=payload.user_email)
    amount = money(payload.amount)
    wallet = lock_wallet(db, user.id, payload.wallet_type)
    credit(wallet, amount)
    note = (payload.description or "").strip()[:200] or f"Credit to {payload.wallet_type} wallet"
    tx = Transaction(receiver_wallet_id=wallet.id, amount=amount, currency=CUR, tx_type="admin_credit",
                     status="completed", description=note, reviewed_by_id=admin.id,
                     reviewed_at=datetime.now(timezone.utc))
    db.add(tx)
    _audit(db, admin, "CREDIT_WALLET", user.id, f"+{usd(amount)} to {payload.wallet_type}: {note}")
    db.commit()
    db.refresh(tx)
    _notify(db, user, "Wallet credited", f"{usd(amount)} was added to your {payload.wallet_type.title()} wallet.",
            "deposit", [note])
    return admin_tx_view(tx, user)


@router.post("/wallets/debit", response_model=AdminTransactionOut, status_code=201)
def debit_user_wallet(payload: AdminDebitRequest, admin=Depends(get_current_admin),
                      db: Session = Depends(get_db)):
    if not payload.user_id and not payload.user_email:
        raise HTTPException(status_code=422, detail="Provide user_id or user_email.")
    user = _get_user(db, user_id=payload.user_id, email=payload.user_email)
    amount = money(payload.amount)
    wallet = lock_wallet(db, user.id, payload.wallet_type)
    debit(wallet, amount, "The wallet balance is lower than that amount.")
    note = (payload.description or "").strip()[:200] or f"Debit from {payload.wallet_type} wallet"
    tx = Transaction(sender_wallet_id=wallet.id, amount=amount, currency=CUR, tx_type="admin_debit",
                     status="completed", description=note, reviewed_by_id=admin.id,
                     reviewed_at=datetime.now(timezone.utc))
    db.add(tx)
    _audit(db, admin, "DEBIT_WALLET", user.id, f"-{usd(amount)} from {payload.wallet_type}: {note}")
    db.commit()
    db.refresh(tx)
    _notify(db, user, "Wallet debited", f"{usd(amount)} was deducted from your {payload.wallet_type.title()} wallet.",
            "account", [note])
    return admin_tx_view(tx, user)


# ── Ledger ────────────────────────────────────
@router.get("/transactions", response_model=List[AdminTransactionOut])
def list_all_transactions(
    response: Response,
    tx_type: Optional[str] = None, status_: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, description="User email contains"),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    admin=Depends(get_current_admin), db: Session = Depends(get_db),
):
    query = db.query(Transaction)
    if tx_type:
        query = query.filter(Transaction.tx_type == tx_type)
    if status_:
        query = query.filter(Transaction.status == status_)
    if q:
        wallet_ids = db.query(Wallet.id).join(User, User.id == Wallet.user_id) \
            .filter(User.email.ilike(f"%{q.strip()}%")).subquery()
        query = query.filter(Transaction.sender_wallet_id.in_(wallet_ids.select())
                             | Transaction.receiver_wallet_id.in_(wallet_ids.select()))
    response.headers["X-Total-Count"] = str(query.count())
    rows = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
    return _with_owners(db, rows)


@router.get("/transactions/{tx_id}", response_model=AdminTransactionOut)
def transaction_detail(tx_id: str, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return admin_tx_view(tx, _owner_of(db, tx), include_proof=True)


@router.get("/deposits/pending", response_model=List[AdminTransactionOut])
def list_pending_deposits(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.query(Transaction).filter(Transaction.tx_type == "deposit", Transaction.status == "pending") \
        .order_by(Transaction.created_at.asc()).all()   # oldest first: a review queue is FIFO
    return _with_owners(db, rows)


@router.get("/withdrawals/pending", response_model=List[AdminTransactionOut])
def list_pending_withdrawals(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.query(Transaction).filter(Transaction.tx_type == "withdrawal", Transaction.status == "pending") \
        .order_by(Transaction.created_at.asc()).all()
    return _with_owners(db, rows)


def _lock_pending(db: Session, tx_id: str, kind: str) -> Transaction:
    tx = db.query(Transaction).filter(Transaction.id == tx_id).with_for_update().populate_existing().first()
    if not tx or tx.tx_type != kind:
        raise HTTPException(status_code=404, detail=f"{kind.title()} not found.")
    if tx.status != "pending":
        raise HTTPException(status_code=409, detail=f"This {kind} was already {tx.status}.")
    return tx


@router.patch("/deposits/{transaction_id}/review", response_model=AdminTransactionOut)
def review_deposit(transaction_id: str, payload: AdminDepositReviewRequest,
                   admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    tx = _lock_pending(db, transaction_id, "deposit")
    if not tx.receiver_wallet_id:
        raise HTTPException(status_code=409, detail="This deposit isn't linked to any wallet (a legacy record), so it can't be credited.")
    wallet = lock_wallet_by_id(db, tx.receiver_wallet_id)
    user = db.query(User).filter(User.id == wallet.user_id).first()
    decision = _parse_status(payload.status)
    tx.reviewed_by_id, tx.reviewed_at = admin.id, datetime.now(timezone.utc)

    if decision == "completed":
        credit(wallet, money(tx.amount))
        tx.status = "completed"
        _audit(db, admin, "APPROVE_DEPOSIT", user.id, f"{usd(tx.amount)} via {tx.gateway_name} ({tx.id})")
    else:
        reason = (payload.rejection_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=422, detail="Give the user a reason for the rejection.")
        tx.status, tx.rejection_reason = "rejected", reason[:500]
        _audit(db, admin, "REJECT_DEPOSIT", user.id, f"{usd(tx.amount)} ({tx.id}): {reason}")
    db.commit()
    db.refresh(tx)

    if tx.status == "completed":
        process_referral_milestone(db, user, "first_deposit", tx.amount)
        _notify(db, user, "Deposit approved",
                f"Your {usd(tx.amount)} deposit via {tx.gateway_name} is now in your Main wallet.", "deposit")
    else:
        _notify(db, user, "Deposit rejected",
                f"Your {usd(tx.amount)} deposit via {tx.gateway_name} was not approved.", "deposit",
                [f"Reason: {tx.rejection_reason}"])
    return admin_tx_view(tx, user)


@router.patch("/withdrawals/{transaction_id}/review", response_model=AdminTransactionOut)
def review_withdrawal(transaction_id: str, payload: AdminWithdrawalReviewRequest,
                      admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    tx = _lock_pending(db, transaction_id, "withdrawal")
    if not tx.sender_wallet_id:
        raise HTTPException(status_code=409, detail="This withdrawal isn't linked to any wallet (a legacy record), so it can't be paid or refunded.")
    wallet = lock_wallet_by_id(db, tx.sender_wallet_id)
    user = db.query(User).filter(User.id == wallet.user_id).first()
    decision = _parse_status(payload.status)
    tx.reviewed_by_id, tx.reviewed_at = admin.id, datetime.now(timezone.utc)
    payout = money(tx.amount) - money(tx.fee or 0)

    if decision == "completed":
        ref = (payload.payout_tx_hash or "").strip()
        if not ref:
            raise HTTPException(status_code=422, detail="Paste the payout transaction hash before marking it paid.")
        tx.status, tx.payout_tx_hash = "completed", ref[:255]
        _audit(db, admin, "APPROVE_WITHDRAWAL", user.id, f"{usd(tx.amount)} ({tx.id}) paid, ref {ref}")
    else:
        reason = (payload.rejection_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=422, detail="Give the user a reason for the rejection.")
        credit(wallet, money(tx.amount))     # release the held funds
        tx.status, tx.rejection_reason = "rejected", reason[:500]
        _audit(db, admin, "REJECT_WITHDRAWAL", user.id, f"{usd(tx.amount)} ({tx.id}) refunded: {reason}")
    db.commit()
    db.refresh(tx)

    if tx.status == "completed":
        _notify(db, user, "Withdrawal sent",
                f"We sent {usd(payout)} worth of {tx.asset} on {tx.network} to your address.", "withdrawal",
                [f"Payout reference: {tx.payout_tx_hash}"])
    else:
        _notify(db, user, "Withdrawal rejected",
                f"Your {usd(tx.amount)} withdrawal was not processed and the funds are back in your Main wallet.",
                "withdrawal", [f"Reason: {tx.rejection_reason}"])
    return admin_tx_view(tx, user)


# ── KYC ───────────────────────────────────────
@router.get("/kyc/pending", response_model=List[UserOut])
def list_pending_kyc(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.query(User).filter(User.kyc_status == KYCStatus.PENDING).order_by(User.updated_at.asc().nullsfirst()).all()


@router.get("/kyc/{user_id}/document")
def kyc_document(user_id: str, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    user = _get_user(db, user_id=user_id)
    if not user.kyc_document_url:
        raise HTTPException(status_code=404, detail="No document on file.")
    return {"user_id": str(user.id), "document": user.kyc_document_url}


@router.patch("/kyc/{user_id}/review", response_model=UserOut)
def review_kyc(user_id: str, payload: AdminKYCReviewRequest,
               admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    user = _get_user(db, user_id=user_id)
    if user.kyc_status != KYCStatus.PENDING:
        raise HTTPException(status_code=409, detail="There's no pending submission to review.")
    if payload.status.value == "VERIFIED":
        user.kyc_status, user.is_verified, user.kyc_rejection_reason = KYCStatus.VERIFIED, True, None
        _audit(db, admin, "APPROVE_KYC", user.id, "Identity verified")
    else:
        reason = (payload.rejection_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=422, detail="Tell the user what to fix.")
        user.kyc_status, user.is_verified, user.kyc_rejection_reason = KYCStatus.REJECTED, False, reason[:500]
        _audit(db, admin, "REJECT_KYC", user.id, reason)
    db.commit()
    db.refresh(user)
    if user.kyc_status == KYCStatus.VERIFIED:
        _notify(db, user, "Identity verified", "Your identity check passed. Withdrawals are now available.", "kyc")
    else:
        _notify(db, user, "Identity check needs another look",
                "We couldn't verify the document you sent.", "kyc",
                [f"What to fix: {user.kyc_rejection_reason}", "You can upload a new document from Settings."])
    return user


# ── Investment plans ──────────────────────────
@router.post("/plans/", response_model=InvestmentPlanResponse, status_code=201)
def create_investment_plan(payload: InvestmentPlanCreate, admin=Depends(get_current_admin),
                           db: Session = Depends(get_db)):
    if db.query(InvestmentPlan.id).filter(func.lower(InvestmentPlan.name) == payload.name.lower()).first():
        raise HTTPException(status_code=409, detail=f"A plan named “{payload.name}” already exists.")
    plan = InvestmentPlan(**payload.model_dump(), is_active=True)
    db.add(plan)
    _audit(db, admin, "CREATE_PLAN", None, f"{payload.name}: {payload.daily_roi_percent}%/day × {payload.duration_days}d")
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plans/", response_model=List[InvestmentPlanResponse])
def list_all_plans(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.query(InvestmentPlan).order_by(InvestmentPlan.created_at.asc()).all()


@router.patch("/plans/{plan_id}", response_model=InvestmentPlanResponse)
def update_investment_plan(plan_id: str, payload: InvestmentPlanUpdate,
                           admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"].strip().lower() != plan.name.lower():
        if db.query(InvestmentPlan.id).filter(func.lower(InvestmentPlan.name) == data["name"].strip().lower()).first():
            raise HTTPException(status_code=409, detail="Another plan already uses that name.")
    merged = {c: data.get(c, getattr(plan, c)) for c in
              ("name", "description", "min_amount", "max_amount", "daily_roi_percent", "duration_days")}
    _revalidate(InvestmentPlanCreate, merged)
    for k, v in data.items():
        setattr(plan, k, v.strip() if isinstance(v, str) else v)
    _audit(db, admin, "UPDATE_PLAN", None, f"{plan.name}: {', '.join(f'{k}={v}' for k, v in data.items())}")
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", status_code=204)
def delete_investment_plan(plan_id: str, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    plan = db.query(InvestmentPlan).filter(InvestmentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    if db.query(UserInvestment.id).filter(UserInvestment.plan_id == plan.id).first():
        raise HTTPException(status_code=409, detail="This plan has investments. Pause it instead of deleting it.")
    _audit(db, admin, "DELETE_PLAN", None, plan.name)
    db.delete(plan)
    db.commit()
    return Response(status_code=204)


@router.get("/investments")
def list_investments(status_: Optional[str] = Query(None, alias="status"),
                     skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                     admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    q = db.query(UserInvestment, User.email, InvestmentPlan.name, User.full_name) \
        .join(User, User.id == UserInvestment.user_id) \
        .join(InvestmentPlan, InvestmentPlan.id == UserInvestment.plan_id)
    if status_:
        q = q.filter(UserInvestment.status == status_)
    rows = q.order_by(UserInvestment.created_at.desc()).offset(skip).limit(limit).all()
    return [{"id": str(i.id), "user_id": str(i.user_id), "user_email": email, "user_name": full_name, "plan_name": name,
             "amount_invested": str(i.amount_invested), "daily_roi_percent": str(i.daily_roi_percent),
             "duration_days": i.duration_days, "days_paid": i.days_paid, "total_earned": str(i.total_earned),
             "status": i.status, "start_date": i.start_date.isoformat(),
             "maturity_date": i.maturity_date.isoformat()} for i, email, name, full_name in rows]


@router.post("/investments/process-roi")
def process_roi(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """Run accrual now. Safe to call any number of times; the scheduler also runs it hourly."""
    result = run_roi_accrual(db)
    _audit(db, admin, "RUN_ROI", None, f"days={result['days_paid']} amount={result['amount_paid']}")
    db.commit()
    return result


# ── Payment methods ───────────────────────────
@router.get("/payment-methods", response_model=List[PaymentMethodOut])
def list_methods(admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.query(PaymentMethod).order_by(PaymentMethod.asset, PaymentMethod.network).all()


@router.post("/payment-methods", response_model=PaymentMethodOut, status_code=201)
def create_method(payload: PaymentMethodCreate, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    m = PaymentMethod(**payload.model_dump())
    m.asset = m.asset.upper()
    db.add(m)
    _audit(db, admin, "CREATE_PAYMENT_METHOD", None, f"{m.asset} ({m.network})")
    db.commit()
    db.refresh(m)
    return m


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodOut)
def update_method(method_id: str, payload: PaymentMethodUpdate,
                  admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    m = db.query(PaymentMethod).filter(PaymentMethod.id == method_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Payment method not found.")
    data = payload.model_dump(exclude_unset=True)
    merged = {c: data.get(c, getattr(m, c)) for c in PaymentMethodCreate.model_fields}
    _revalidate(PaymentMethodCreate, merged)
    for k, v in data.items():
        setattr(m, k, v.upper() if k == "asset" and v else v)
    _audit(db, admin, "UPDATE_PAYMENT_METHOD", None,
           f"{m.asset} ({m.network}): " + ", ".join(f"{k}={v}" for k, v in data.items()))
    db.commit()
    db.refresh(m)
    return m


@router.delete("/payment-methods/{method_id}", status_code=204)
def delete_method(method_id: str, admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    m = db.query(PaymentMethod).filter(PaymentMethod.id == method_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Payment method not found.")
    if db.query(Transaction.id).filter(Transaction.payment_method_id == m.id).first():
        raise HTTPException(status_code=409, detail="Transactions reference this method. Turn it off instead.")
    _audit(db, admin, "DELETE_PAYMENT_METHOD", None, f"{m.asset} ({m.network})")
    db.delete(m)
    db.commit()
    return Response(status_code=204)


# ── Audit trail ───────────────────────────────
@router.get("/audit-logs", response_model=List[AuditLogResponse])
def list_audit_logs(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                    admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    ids = {r.admin_id for r in rows} | {r.target_user_id for r in rows if r.target_user_id}
    emails = dict(db.query(User.id, User.email).filter(User.id.in_(ids)).all()) if ids else {}
    return [{"id": r.id, "admin_id": r.admin_id, "admin_email": emails.get(r.admin_id), "action": r.action,
             "target_user_id": r.target_user_id, "target_email": emails.get(r.target_user_id),
             "details": r.details, "created_at": r.created_at} for r in rows]
