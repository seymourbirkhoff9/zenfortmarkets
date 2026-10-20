"""
app/main.py — FastAPI application entry point for Zenfort Markets.

Schema changes are managed by Alembic (`alembic upgrade head`); the app no
longer calls create_all(), which silently skipped column changes and let the
database drift away from the migrations.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
import time

from fastapi import Request

from app.database import SessionLocal, engine, start_request_stats, warm_pool
from app.routers import admin, admin_emails, auth, files, investments, leaderboard, notifications, users, wallets
from app.services.roi import run_roi_accrual

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("zenfort.startup")

ROI_INTERVAL_SECONDS = 60 * 60


async def _roi_scheduler():
    """Accrue investment returns hourly. Accrual is idempotent, so overlap or restarts are harmless."""
    while True:
        try:
            def job():
                db = SessionLocal()
                try:
                    return run_roi_accrual(db)
                finally:
                    db.close()
            result = await asyncio.to_thread(job)
            if result["days_paid"] or result["matured"]:
                logger.info("ROI accrual: %s", result)
        except Exception:
            logger.exception("ROI accrual failed")
        await asyncio.sleep(ROI_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database reachable ✓")
    except Exception as exc:
        logger.error("Database not reachable on startup: %s", exc)
    if settings.DB_KEEP_WARM:
        # Start even if the check above failed: it retries in the background every 45 s.
        asyncio.get_running_loop().run_in_executor(None, warm_pool)
    task = asyncio.create_task(_roi_scheduler()) if settings.ENABLE_SCHEDULER else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="Zenfort Markets API",
    description="Educational crypto-broker simulation: USD ledger, manual crypto rails, admin review.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list({settings.FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"}),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Total-Count", "Server-Timing", "X-DB-Queries"],
)

@app.middleware("http")
async def server_timing(request: Request, call_next):
    """Expose DB round trips and time per request (browser devtools → Network → Timing)."""
    stats = start_request_stats()
    t0 = time.perf_counter()
    response = await call_next(request)
    total = (time.perf_counter() - t0) * 1000
    response.headers["Server-Timing"] = (
        f'db;dur={stats["db_ms"]:.1f};desc="{stats["queries"]} queries", total;dur={total:.1f}')
    response.headers["X-DB-Queries"] = str(stats["queries"])
    if total > 800:
        logger.warning("Slow request %s %s: %.0f ms, %d queries", request.method, request.url.path,
                       total, stats["queries"])
    return response


for r in (auth, wallets, investments, admin, notifications, admin_emails, leaderboard, users, files):
    app.include_router(r.router)


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"], include_in_schema=False)
def health_check():
    return {"status": "ok", "service": "zenfort-markets-api"}


# Serve the built frontend from the same origin (production). Mounted last, so /api/* wins.
if settings.FRONTEND_DIST:
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    _dist = Path(settings.FRONTEND_DIST)
    if (_dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
        logger.info("Serving frontend from %s", _dist)
    else:
        logger.error("FRONTEND_DIST=%s has no index.html; run `npm run build` in frontend/", _dist)
