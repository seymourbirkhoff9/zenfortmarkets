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

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:3000"


settings = Settings()
