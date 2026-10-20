"""
app/config.py — Pydantic v2 settings loaded from environment / .env
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Resend Email
    RESEND_API_KEY: str
    EMAIL_FROM: str = "noreply@zenfortmarkets.com"

    # CORS / frontend
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    # Public URL of the frontend, used to build links in emails (verification, referrals)
    FRONTEND_URL: str = "http://localhost:3000"
    # Set True in production (HTTPS) so the session cookie is only sent over TLS
    COOKIE_SECURE: bool = False

    # Base currency of every wallet/ledger entry. Crypto is only the payment rail.
    BASE_CURRENCY: str = "USD"
    # Max decoded size of uploaded proof images / KYC documents (bytes)
    MAX_UPLOAD_BYTES: int = 2_000_000
    # Bonus paid to a referrer on the referred user's first approved deposit
    REFERRAL_BONUS_AMOUNT: str = "10.00"
    # Require an approved KYC before a user can request a withdrawal
    REQUIRE_KYC_FOR_WITHDRAWAL: bool = True
    # Run the hourly ROI accrual loop inside the API process
    ENABLE_SCHEDULER: bool = True
    # Local testing only: add this many ms to every query to mimic a remote database. Keep 0 in real use.
    SIMULATE_DB_LATENCY_MS: int = 0
    # Open all DB connections at startup and keep them alive (important for remote databases)
    DB_KEEP_WARM: bool = True
    # Path to the built frontend (frontend/dist). When set, the API also serves the site, so the
    # browser sees ONE origin and the session cookie works (needed on Render: *.onrender.com
    # subdomains count as different sites). Empty = API only (local dev uses the Vite server).
    FRONTEND_DIST: str = ""

    # File storage. With SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY set, files go to Supabase Storage;
    # otherwise they're kept in LOCAL_UPLOAD_DIR (development / tests). The service key is server-only.
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    STORAGE_PUBLIC_BUCKET: str = "avatars"          # public: profile photos
    STORAGE_PRIVATE_BUCKET: str = "private-docs"    # private: ID documents, payment screenshots
    LOCAL_UPLOAD_DIR: str = "uploads"
    SIGNED_URL_SECONDS: int = 300

    # Bump when Terms/Privacy change; users are asked to accept the new version on their next visit.
    TERMS_VERSION: str = "2026-10"


settings = Settings()
