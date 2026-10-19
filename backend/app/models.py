"""
app/models.py — SQLAlchemy ORM models for Zenfort Markets
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
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
    is_verified = Column(Boolean, default=False)
    country = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    # Compliance & Governance fields
    kyc_status = Column(SQLEnum(KYCStatus), default=KYCStatus.UNVERIFIED, nullable=False)
    kyc_document_url = Column(String(500), nullable=True)
    is_blocked = Column(Boolean, default=False)
    can_withdraw = Column(Boolean, default=True)
    can_deposit = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    user_investments = relationship("UserInvestment", back_populates="user", cascade="all, delete-orphan")


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
    proof_image_url = Column(String(500), nullable=True)
    # Withdrawal payout fields
    withdrawal_address = Column(String(255), nullable=True)  # User's withdrawal address
    payout_tx_hash = Column(String(255), nullable=True)  # Admin's payout transaction reference
    rejection_reason = Column(Text, nullable=True)
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="user_investments")
    plan = relationship("InvestmentPlan", back_populates="user_investments")
