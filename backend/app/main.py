"""
app/main.py — FastAPI application entry point for Zenfort Markets
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import Base

# Import routers
from app.routers import auth, wallets, investments, admin, notifications, admin_emails, leaderboard, users

logger = logging.getLogger("zenfort.startup")


# ──────────────────────────────────────────────
# Lifespan: create tables on startup (doesn't crash if DB is briefly unavailable)
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Connecting to database and syncing schema…")
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema synced ✓")
    except Exception as exc:
        logger.error(
            "⚠️  Could not reach database on startup: %s\n"
            "Server will still start — retries happen per-request.",
            exc,
        )
    yield
    # shutdown hook (add cleanup here if needed)
    logger.info("Zenfort Markets API shutting down.")


# ──────────────────────────────────────────────
# App instance
# ──────────────────────────────────────────────
app = FastAPI(
    title="Zenfort Markets API",
    description="Multi-currency crypto broker and investment platform backend.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(wallets.router)
app.include_router(investments.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(admin_emails.router)
app.include_router(leaderboard.router)
app.include_router(users.router)


# ──────────────────────────────────────────────
# Health-check endpoint (for uptime monitors / external pingers)
# ──────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "zenfort-markets-api"}
