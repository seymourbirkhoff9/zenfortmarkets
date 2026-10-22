"""
app/models.py — SQLAlchemy ORM models for Zenfort Markets
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    Column, String, Boolean, DateTime, Numeric, Integer, ForeignKey, Text, func, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────
class KYCStatus(enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=False)        # True after email verify
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)       # KYC-verified (set by KYC approval)
    email_verified = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(Text, nullable=True)            # storage reference, e.g. sb://avatars/<user>/<file>.jpg
    terms_version = Column(String(20), nullable=True)   # version of Terms/Privacy the user accepted
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    # Bumped on password change/reset and 2FA changes: sessions carrying an older value stop working.
    session_version = Column(Integer, nullable=False, default=0, server_default="0")
    # Two-factor sign-in (authenticator app). The secret is encrypted with a key derived from SECRET_KEY.
    totp_secret = Column(Text, nullable=True)
    totp_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    totp_last_step = Column(BigInteger, nullable=True)       # stops a code being used twice
    recovery_codes = Column(Text, nullable=True)             # JSON list of SHA-256 hashes, one-time use
    country = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    # Compliance & Governance fields
    kyc_status = Column(SQLEnum(KYCStatus), default=KYCStatus.UNVERIFIED, nullable=False)
    kyc_document_url = Column(Text, nullable=True)
    kyc_rejection_reason = Column(Text, nullable=True)
    is_blocked = Column(Boolean, default=False)
    can_withdraw = Column(Boolean, default=True)
    can_deposit = Column(Boolean, default=True)
    # Referral Program fields
    referral_code = Column(String(8), unique=True, nullable=False, index=True)
    referred_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    referral_count = Column(Integer, default=0, nullable=False)
    total_referral_earned = Column(Numeric(18, 8), default=Decimal("0.00"), nullable=False)
    display_currency = Column(String(10), nullable=True)  # User's preferred display currency (e.g., "EUR", "NGN")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    user_investments = relationship("UserInvestment", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    referred_users = relationship("User", backref="referrer", remote_side=[id])


# ──────────────────────────────────────────────
# Wallets
# ──────────────────────────────────────────────
class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    wallet_type = Column(String(50), nullable=False)   # "main" | "profit"
    currency = Column(String(10), nullable=False, default="USD")
    balance = Column(Numeric(precision=20, scale=8), nullable=False, default=Decimal("0.0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="wallets")
    debit_transactions = relationship(
        "Transaction", foreign_keys="Transaction.sender_wallet_id", back_populates="sender_wallet"
    )
    credit_transactions = relationship(
        "Transaction", foreign_keys="Transaction.receiver_wallet_id", back_populates="receiver_wallet"
    )


# ──────────────────────────────────────────────
# Transactions / Ledger
# ──────────────────────────────────────────────
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True)
    receiver_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True)
    amount = Column(Numeric(precision=20, scale=8), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    tx_type = Column(String(50), nullable=False)  # "transfer" | "p2p" | "deposit" | "withdrawal" | "admin_debit" | "roi_credit" | "investment" | "principal_return"
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="completed")  # "pending" | "completed" | "rejected"
    # Manual deposit fields
    gateway_name = Column(String(50), nullable=True)  # e.g., "BTC", "USDT_TRC20"
    tx_hash = Column(String(255), nullable=True)
    proof_image_url = Column(Text, nullable=True)     # data URL (validated, size-capped)
    payment_method_id = Column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)
    asset = Column(String(20), nullable=True)          # e.g. "USDT"
    network = Column(String(50), nullable=True)        # e.g. "TRC20"
    fee = Column(Numeric(precision=20, scale=8), nullable=True)
    withdrawal_details = Column(Text, nullable=True)   # memo/tag or notes for the admin paying out
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    # Withdrawal payout fields
    withdrawal_address = Column(String(255), nullable=True)  # User's withdrawal address
    payout_tx_hash = Column(String(255), nullable=True)  # Admin's payout transaction reference
    rejection_reason = Column(Text, nullable=True)
    # Multi-currency input tracking
    input_amount = Column(Numeric(precision=20, scale=8), nullable=True)  # Original amount in input_currency
    input_currency = Column(String(10), nullable=True)  # Currency user specified (e.g., "EUR")
    fx_rate = Column(Numeric(precision=20, scale=10), nullable=True)  # Rate used for conversion
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender_wallet = relationship("Wallet", foreign_keys=[sender_wallet_id], back_populates="debit_transactions")
    receiver_wallet = relationship("Wallet", foreign_keys=[receiver_wallet_id], back_populates="credit_transactions")


# ──────────────────────────────────────────────
# Investment Plans (Admin-managed templates)
# ──────────────────────────────────────────────
class InvestmentPlan(Base):
    __tablename__ = "investment_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    min_amount = Column(Numeric(precision=20, scale=8), nullable=False)
    max_amount = Column(Numeric(precision=20, scale=8), nullable=False)
    daily_roi_percent = Column(Numeric(precision=7, scale=4), nullable=False)
    duration_days = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_investments = relationship("UserInvestment", back_populates="plan")


# ──────────────────────────────────────────────
# User Investments (Subscriptions to plans)
# ──────────────────────────────────────────────
class UserInvestment(Base):
    __tablename__ = "user_investments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("investment_plans.id"), nullable=False)

    amount_invested = Column(Numeric(precision=20, scale=8), nullable=False)
    # Snapshotted at investment time — insulates user from plan changes
    daily_roi_percent = Column(Numeric(precision=7, scale=4), nullable=False)
    duration_days = Column(Integer, nullable=False)

    total_earned = Column(Numeric(precision=20, scale=8), nullable=False, default=Decimal("0.0"))
    status = Column(String(20), nullable=False, default="active")  # "active" | "completed" | "cancelled"

    start_date = Column(DateTime(timezone=True), nullable=False)
    maturity_date = Column(DateTime(timezone=True), nullable=False)
    # Number of daily ROI payouts already credited — makes the ROI engine idempotent.
    days_paid = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="user_investments")
    plan = relationship("InvestmentPlan", back_populates="user_investments")


# ──────────────────────────────────────────────
# Notifications (In-app notification center)
# ──────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # "kyc" | "deposit" | "withdrawal" | "account" | "general"
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")


# ──────────────────────────────────────────────
# Broadcast Logs (Admin email broadcast history)
# ──────────────────────────────────────────────
class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    target_filter = Column(String(50), nullable=False, default="all")  # "all", "verified_kyc", "active_investors", "unverified_kyc"
    recipient_count = Column(Integer, nullable=False, default=0)
    delivered_count = Column(Integer, nullable=True)     # filled in when sending finishes
    failed_count = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ──────────────────────────────────────────────
# Audit Logs (System-wide administrative action logs)
# ──────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)  # e.g., "BLOCK_USER", "APPROVE_KYC", "CREDIT_WALLET"
    target_user_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ──────────────────────────────────────────────
# Payment Methods (admin-managed crypto rails for deposits / withdrawals)
# ──────────────────────────────────────────────
class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    method_type = Column(String(10), nullable=False, default="crypto")  # "crypto" | "bank"
    asset = Column(String(20), nullable=False)          # "USDT", "BTC", "BANK"
    network = Column(String(50), nullable=False)        # "TRC20", "Bitcoin", bank name
    deposit_address = Column(String(255), nullable=True)
    deposit_memo = Column(String(255), nullable=True)   # tag/memo some chains require
    bank_details = Column(Text, nullable=True)          # JSON: bank-specific fields for bank transfers
    deposit_enabled = Column(Boolean, nullable=False, default=True)
    withdraw_enabled = Column(Boolean, nullable=False, default=True)
    min_deposit = Column(Numeric(precision=20, scale=8), nullable=False, default=Decimal("0"))
    min_withdrawal = Column(Numeric(precision=20, scale=8), nullable=False, default=Decimal("0"))
    withdrawal_fee = Column(Numeric(precision=20, scale=8), nullable=False, default=Decimal("0"))  # flat, in USD
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ──────────────────────────────────────────────
# FX Rates (currency conversion rates)
# ──────────────────────────────────────────────
class FxRate(Base):
    __tablename__ = "fx_rates"

    currency = Column(String(10), primary_key=True, nullable=False)  # ISO code, e.g., "EUR", "NGN"
    rate_per_usd = Column(Numeric(precision=20, scale=10), nullable=True)  # Units of this currency per 1 USD
    override_rate = Column(Numeric(precision=20, scale=10), nullable=True)  # Admin override, wins when set
    is_enabled = Column(Boolean, nullable=False, default=True)
    source = Column(String(50), nullable=True)  # e.g., "open.er-api.com"
    updated_at = Column(DateTime(timezone=True), nullable=True)

