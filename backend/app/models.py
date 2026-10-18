"""
app/models.py — SQLAlchemy ORM models for Zenfort Markets
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, DateTime, Numeric, ForeignKey, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    investments = relationship("Investment", back_populates="user", cascade="all, delete-orphan")


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
    tx_type = Column(String(50), nullable=False)  # "transfer" | "p2p" | "deposit" | "withdrawal"
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="completed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender_wallet = relationship("Wallet", foreign_keys=[sender_wallet_id], back_populates="debit_transactions")
    receiver_wallet = relationship("Wallet", foreign_keys=[receiver_wallet_id], back_populates="credit_transactions")


# ──────────────────────────────────────────────
# Investments
# ──────────────────────────────────────────────
class Investment(Base):
    __tablename__ = "investments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_name = Column(String(100), nullable=False)
    amount = Column(Numeric(precision=20, scale=8), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    roi_percent = Column(Numeric(precision=5, scale=2), nullable=False, default=Decimal("0.0"))
    status = Column(String(20), nullable=False, default="active")  # active | matured | cancelled
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    matures_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="investments")
