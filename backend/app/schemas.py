"""
app/schemas.py — Pydantic request / response schemas
"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional, List
from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator


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
    referral_code: Optional[str] = None
    # Must be True: the user ticked "I agree to the Terms and Privacy Policy".
    # validate_default: an OMITTED field must fail too (Pydantic skips validators on defaults otherwise).
    accept_terms: bool = Field(default=False, validate_default=True)

    @field_validator("accept_terms")
    @classmethod
    def terms_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please accept the Terms and Privacy Policy to create an account.")
        return v

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
    # The document itself can be megabytes; only admins fetch it, via a dedicated endpoint.
    kyc_document_url: Optional[str] = Field(default=None, exclude=True)
    is_blocked: bool
    can_withdraw: bool
    can_deposit: bool
    referral_code: str
    email_verified: bool = False
    kyc_rejection_reason: Optional[str] = None
    # Set only while an admin is viewing this account (view-only impersonation)
    impersonated_by: Optional[str] = None
    impersonation_expires_at: Optional[datetime] = None
    avatar_url: Optional[str] = None          # browser-ready URL (converted from the storage reference)
    terms_version: Optional[str] = None
    terms_accepted_at: Optional[datetime] = None
    totp_enabled: bool = False

    @field_validator("avatar_url")
    @classmethod
    def avatar_public_url(cls, v):
        from app.services.storage import url_for
        return url_for(v) if v else None

    @computed_field
    @property
    def terms_current(self) -> bool:
        from app.config import settings
        return self.terms_version == settings.TERMS_VERSION
    referral_count: int = 0
    total_referral_earned: Decimal = Decimal("0")
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def has_kyc_document(self) -> bool:
        return bool(self.kyc_document_url)


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
    """List-safe transaction view. The proof image is only returned by detail endpoints."""
    id: uuid.UUID
    amount: Decimal
    currency: str
    tx_type: str
    description: Optional[str]
    status: str
    direction: Optional[Literal["in", "out"]] = None   # relative to the requesting user
    gateway_name: Optional[str] = None
    asset: Optional[str] = None
    network: Optional[str] = None
    fee: Optional[Decimal] = None
    tx_hash: Optional[str] = None
    has_proof: bool = False
    withdrawal_address: Optional[str] = None
    withdrawal_details: Optional[str] = None
    payout_tx_hash: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminTransactionOut(TransactionOut):
    user_id: Optional[uuid.UUID] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    proof_image_url: Optional[str] = None   # populated on detail requests only


# ──────────────────────────────────────────────
# Phase 4: Investment Plans & User Investments
# ──────────────────────────────────────────────
class InvestmentPlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    min_amount: Decimal
    max_amount: Decimal
    daily_roi_percent: Decimal
    duration_days: int

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required.")
        return v

    @model_validator(mode="after")
    def validate_amounts(self) -> "InvestmentPlanCreate":
        if self.min_amount <= 0:
            raise ValueError("Minimum amount must be positive.")
        if self.max_amount <= self.min_amount:
            raise ValueError("Maximum amount must be greater than the minimum.")
        if not (Decimal("0") < self.daily_roi_percent <= Decimal("100")):
            raise ValueError("Daily rate must be between 0 and 100 percent.")
        if not (0 < self.duration_days <= 3650):
            raise ValueError("Duration must be between 1 and 3650 days.")
        return self


class InvestmentPlanUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates and is_active toggle."""
    name: Optional[str] = None
    description: Optional[str] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    daily_roi_percent: Optional[Decimal] = None
    duration_days: Optional[int] = None
    is_active: Optional[bool] = None


class InvestmentPlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    min_amount: Decimal
    max_amount: Decimal
    daily_roi_percent: Decimal
    duration_days: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestRequest(BaseModel):
    """User subscribes to a plan with a specific amount."""
    plan_id: uuid.UUID
    amount: Decimal
    # Must be True: the user ticked "I've read the Risk Disclosure" (validated even when omitted)
    accept_risk: bool = Field(default=False, validate_default=True)

    @field_validator("accept_risk")
    @classmethod
    def risk_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please confirm you've read the Risk Disclosure.")
        return v

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive.")
        return v


class UserInvestmentResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: Optional[str] = None
    days_paid: int = 0
    amount_invested: Decimal
    daily_roi_percent: Decimal
    duration_days: int
    total_earned: Decimal
    status: str
    start_date: datetime
    maturity_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Phase 5: Notifications
# ──────────────────────────────────────────────
class NotificationResponse(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Phase 6: Admin Email Broadcast
# ──────────────────────────────────────────────
class AdminSendUserEmailRequest(BaseModel):
    user_id: uuid.UUID
    subject: str
    body: str


class AdminBroadcastEmailRequest(BaseModel):
    subject: str
    body: str
    target_filter: str = "all"  # "all", "verified_kyc", "active_investors", "unverified_kyc"


class BroadcastLogResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID
    subject: str
    target_filter: str
    recipient_count: int
    delivered_count: Optional[int] = None
    failed_count: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Phase 7: Wallet Transfers & Audit Logs
# ──────────────────────────────────────────────
class WalletTransferRequest(BaseModel):
    from_wallet: Literal["main", "profit"]
    to_wallet: Literal["main", "profit"]
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive.")
        return v

    @model_validator(mode="after")
    def different_wallets(self):
        if self.from_wallet == self.to_wallet:
            raise ValueError("from_wallet and to_wallet must be different.")
        return self


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID
    admin_email: Optional[str] = None
    action: str
    target_user_id: Optional[uuid.UUID]
    target_email: Optional[str] = None
    details: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Phase 8: Referral Program & Leaderboard
# ──────────────────────────────────────────────
class ReferredUser(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralStatsResponse(BaseModel):
    referral_code: str
    referral_link: str
    total_referrals: int
    total_earned: Decimal
    referred_users: List[ReferredUser]

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    metric_value: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Admin
# ──────────────────────────────────────────────
class AdminCreditRequest(BaseModel):
    user_email: Optional[EmailStr] = None
    user_id: Optional[uuid.UUID] = None
    wallet_type: Literal["main", "profit"]
    amount: Decimal
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v

    @model_validator(mode="after")
    def target_required(self):
        if not self.user_email and not self.user_id:
            raise ValueError("Provide user_id or user_email.")
        return self


class AdminDebitRequest(BaseModel):
    user_email: Optional[EmailStr] = None
    user_id: Optional[uuid.UUID] = None
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


# ──────────────────────────────────────────────
# Phase 2: KYC & Manual Deposit Schemas
# ──────────────────────────────────────────────
class KYCSubmitRequest(BaseModel):
    kyc_document_url: str   # data URL (image or PDF), validated server-side


class DepositCreateRequest(BaseModel):
    """Amount is the USD value the user sent. Crypto is only the payment rail."""
    payment_method_id: uuid.UUID
    amount: Decimal
    tx_hash: Optional[str] = None
    proof_image_url: Optional[str] = None

    @model_validator(mode="after")
    def evidence_required(self):
        if not (self.tx_hash and self.tx_hash.strip()) and not self.proof_image_url:
            raise ValueError("Add the transaction hash or a screenshot of the payment.")
        return self

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class AdminDepositReviewRequest(BaseModel):
    status: Literal["approved", "completed", "rejected"]
    rejection_reason: Optional[str] = None


# ──────────────────────────────────────────────
# Phase 3: Manual Withdrawal Schemas
# ──────────────────────────────────────────────
class WithdrawalCreateRequest(BaseModel):
    payment_method_id: uuid.UUID
    amount: Decimal                          # USD amount debited from the Main wallet
    withdrawal_address: str
    withdrawal_details: Optional[str] = None  # memo/tag or notes for the admin

    @field_validator("withdrawal_address")
    @classmethod
    def address_shape(cls, v: str) -> str:
        v = v.strip()
        if not (10 <= len(v) <= 128) or any(c.isspace() for c in v):
            raise ValueError("Enter a valid wallet address.")
        return v

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class AdminWithdrawalReviewRequest(BaseModel):
    status: Literal["approved", "completed", "rejected"]
    payout_tx_hash: Optional[str] = None
    rejection_reason: Optional[str] = None


# ──────────────────────────────────────────────
# Payment methods
# ──────────────────────────────────────────────
class PaymentMethodBase(BaseModel):
    asset: str
    network: str
    deposit_address: Optional[str] = None
    deposit_memo: Optional[str] = None
    deposit_enabled: bool = True
    withdraw_enabled: bool = True
    min_deposit: Decimal = Decimal("0")
    min_withdrawal: Decimal = Decimal("0")
    withdrawal_fee: Decimal = Decimal("0")
    is_active: bool = True

    @field_validator("asset", "network")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Required.")
        return v

    @field_validator("min_deposit", "min_withdrawal", "withdrawal_fee")
    @classmethod
    def non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Must be zero or more.")
        return v

    @model_validator(mode="after")
    def deposit_needs_address(self):
        if self.deposit_enabled and not (self.deposit_address and self.deposit_address.strip()):
            raise ValueError("A deposit address is required when deposits are enabled.")
        return self


class PaymentMethodCreate(PaymentMethodBase):
    pass


class PaymentMethodUpdate(BaseModel):
    asset: Optional[str] = None
    network: Optional[str] = None
    deposit_address: Optional[str] = None
    deposit_memo: Optional[str] = None
    deposit_enabled: Optional[bool] = None
    withdraw_enabled: Optional[bool] = None
    min_deposit: Optional[Decimal] = None
    min_withdrawal: Optional[Decimal] = None
    withdrawal_fee: Optional[Decimal] = None
    is_active: Optional[bool] = None


class PaymentMethodOut(PaymentMethodBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def deposit_needs_address(self):  # outputs are not re-validated
        return self


# ──────────────────────────────────────────────
# Admin overview / users
# ──────────────────────────────────────────────
class AdminStats(BaseModel):
    users_total: int
    users_new_7d: int
    users_blocked: int
    pending_deposits: int
    pending_deposits_amount: Decimal
    pending_withdrawals: int
    pending_withdrawals_amount: Decimal
    pending_kyc: int
    total_main_balance: Decimal
    total_profit_balance: Decimal
    active_investments: int
    active_investment_capital: Decimal
    deposits_completed_30d: Decimal
    withdrawals_completed_30d: Decimal


class UserPage(BaseModel):
    total: int
    items: List[UserOut]


class AdminUserDetail(BaseModel):
    user: UserOut
    wallets: List[WalletOut]
    investments: List[UserInvestmentResponse]
    transactions: List[TransactionOut]
    referred_by_email: Optional[str] = None


class AvatarUpload(BaseModel):
    image: str        # data URL; validated and moved to storage server-side


class EmailVerifyRequest(BaseModel):
    token: str


class RoleUpdate(BaseModel):
    is_admin: bool


class UnreadCount(BaseModel):
    unread: int
