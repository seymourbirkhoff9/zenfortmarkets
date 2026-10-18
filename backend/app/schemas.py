"""
app/schemas.py — Pydantic request / response schemas
"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator


# ──────────────────────────────────────────────
# KYC Status Enum
# ──────────────────────────────────────────────
class KYCStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


# ──────────────────────────────────────────────
# Country Enum — drives the Swagger dropdown + currency resolution
# ──────────────────────────────────────────────
class CountryEnum(str, Enum):
    # Africa
    Nigeria         = "Nigeria"
    Ghana           = "Ghana"
    Kenya           = "Kenya"
    SouthAfrica     = "South Africa"
    Tanzania        = "Tanzania"
    Ethiopia        = "Ethiopia"
    Cameroon        = "Cameroon"
    Senegal         = "Senegal"
    IvoryCoast      = "Ivory Coast"
    Zambia          = "Zambia"
    Zimbabwe        = "Zimbabwe"
    Egypt           = "Egypt"
    # Europe
    UnitedKingdom   = "United Kingdom"
    France          = "France"
    Germany         = "Germany"
    Spain           = "Spain"
    Italy           = "Italy"
    Netherlands     = "Netherlands"
    Portugal        = "Portugal"
    Belgium         = "Belgium"
    Austria         = "Austria"
    Finland         = "Finland"
    Greece          = "Greece"
    Ireland         = "Ireland"
    Sweden          = "Sweden"
    Norway          = "Norway"
    Denmark         = "Denmark"
    Poland          = "Poland"
    Switzerland     = "Switzerland"
    Ukraine         = "Ukraine"
    Russia          = "Russia"
    Turkey          = "Turkey"
    # Americas
    UnitedStates    = "United States"
    Canada          = "Canada"
    Brazil          = "Brazil"
    Mexico          = "Mexico"
    Argentina       = "Argentina"
    # Asia-Pacific
    India           = "India"
    China           = "China"
    Japan           = "Japan"
    Singapore       = "Singapore"
    Australia       = "Australia"
    NewZealand      = "New Zealand"
    Indonesia       = "Indonesia"
    Malaysia        = "Malaysia"
    Pakistan        = "Pakistan"
    Bangladesh      = "Bangladesh"
    Thailand        = "Thailand"
    Vietnam         = "Vietnam"
    Philippines     = "Philippines"
    # Middle East
    UnitedArabEmirates = "United Arab Emirates"
    SaudiArabia     = "Saudi Arabia"


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────
# class SignUpRequest(BaseModel):
#     full_name: str
#     email: EmailStr
#     password: str
#     confirm_password: str
#     country: CountryEnum              # Swagger renders this as a dropdown
#     phone: Optional[str] = None

#     @field_validator("password")
#     @classmethod
#     def password_strength(cls, v: str) -> str:
#         if len(v) < 8:
#             raise ValueError("Password must be at least 8 characters.")
#         return v

#     @model_validator(mode="after")
#     def passwords_match(self) -> "SignUpRequest":
#         if self.password != self.confirm_password:
#             raise ValueError("password and confirm_password do not match.")
#         return self



class SignUpRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    confirm_password: str
    country: CountryEnum              # Swagger renders this as a dropdown (JSON body)
    phone: Optional[str] = None

    # ADD THIS VALIDATOR HERE:
    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, v):
        if isinstance(v, str):
            # Clean spaces and convert to title-case (e.g., "france" -> "France")
            cleaned = v.strip().title()
            # Try to match it against the Enum values or names
            for member in CountryEnum:
                if member.value.lower() == cleaned.lower() or member.name.lower() == cleaned.lower():
                    return member
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "SignUpRequest":
        if self.password != self.confirm_password:
            raise ValueError("password and confirm_password do not match.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────
class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    is_verified: bool
    country: Optional[str] = None
    phone: Optional[str] = None
    kyc_status: KYCStatus
    kyc_document_url: Optional[str] = None
    is_blocked: bool
    can_withdraw: bool
    can_deposit: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Wallets
# ──────────────────────────────────────────────
class WalletOut(BaseModel):
    id: uuid.UUID
    wallet_type: str
    currency: str
    balance: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class ExchangeRequest(BaseModel):
    """Move funds between the user's own Main ↔ Profit wallets."""
    source_wallet_type: Literal["main", "profit"]
    destination_wallet_type: Literal["main", "profit"]
    amount: Decimal

    @model_validator(mode="after")
    def wallets_must_differ(self) -> "ExchangeRequest":
        if self.source_wallet_type == self.destination_wallet_type:
            raise ValueError("Source and destination wallets must differ.")
        if self.amount <= 0:
            raise ValueError("Amount must be positive.")
        return self


class P2PTransferRequest(BaseModel):
    """Send funds from the current user's Main wallet to another user by email."""
    recipient_email: EmailStr
    amount: Decimal
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class TransactionOut(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: str
    tx_type: str
    description: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Investments
# ──────────────────────────────────────────────
class InvestmentCreateRequest(BaseModel):
    plan_name: str
    amount: Decimal
    currency: str = "USD"
    roi_percent: Decimal = Decimal("0.0")
    duration_days: int = 30


class InvestmentOut(BaseModel):
    id: uuid.UUID
    plan_name: str
    amount: Decimal
    currency: str
    roi_percent: Decimal
    status: str
    started_at: datetime
    matures_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Admin
# ──────────────────────────────────────────────
class AdminCreditRequest(BaseModel):
    user_email: EmailStr
    wallet_type: Literal["main", "profit"]
    amount: Decimal
    description: Optional[str] = None


class AdminDebitRequest(BaseModel):
    user_email: EmailStr
    wallet_type: Literal["main", "profit"]
    amount: Decimal
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class AdminUserStatusUpdate(BaseModel):
    is_blocked: Optional[bool] = None
    can_withdraw: Optional[bool] = None
    can_deposit: Optional[bool] = None
    is_active: Optional[bool] = None


class AdminKYCReviewRequest(BaseModel):
    status: Literal[KYCStatus.VERIFIED, KYCStatus.REJECTED]
    rejection_reason: Optional[str] = None
