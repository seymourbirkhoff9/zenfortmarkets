"""
app/database.py — SQLAlchemy engine + session factory for Supabase PostgreSQL.

Latency notes (measured from a laptop in Nigeria to Supabase eu-north-1):
  * a query on an already-open connection: ~300 ms (network distance)
  * opening a NEW connection: ~2 s (TLS + pooler login, ~9 round trips)
  * a fresh DNS lookup on some ISP resolvers: 5–15 s
So the rule is: open connections once, keep them alive, never throw them away.
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger("zenfort.db")

POOL_SIZE = 15

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=False,
    pool_size=POOL_SIZE,
    max_overflow=10,
    pool_recycle=3600,
    pool_timeout=30,
    connect_args={
        "connect_timeout": 20,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_stats: ContextVar[dict | None] = ContextVar("db_stats", default=None)


def start_request_stats() -> dict:
    stats = {"queries": 0, "db_ms": 0.0}
    _stats.set(stats)
    return stats


@event.listens_for(engine, "before_cursor_execute")
def _before(conn, cursor, statement, parameters, context, executemany):
    context._zf_start = time.perf_counter()
    if settings.SIMULATE_DB_LATENCY_MS:
        time.sleep(settings.SIMULATE_DB_LATENCY_MS / 1000)


@event.listens_for(engine, "after_cursor_execute")
def _after(conn, cursor, statement, parameters, context, executemany):
    stats = _stats.get()
    if stats is not None:
        stats["queries"] += 1
        stats["db_ms"] += (time.perf_counter() - context._zf_start) * 1000


def _ping_all(n: int) -> int:
    def one(_):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return 1
        except Exception:
            return 0
    with ThreadPoolExecutor(max_workers=n) as ex:
        return sum(ex.map(one, range(n)))


_keepwarm_started = False


def warm_pool(interval_seconds: int = 45) -> None:
    """Open POOL_SIZE connections now, then re-ping them in the background every interval."""
    global _keepwarm_started
    if _keepwarm_started:
        return
    _keepwarm_started = True
    t0 = time.perf_counter()
    ok = _ping_all(POOL_SIZE)
    logger.info("Opened %d/%d database connections in %.1f s", ok, POOL_SIZE, time.perf_counter() - t0)

    def loop():
        while True:
            time.sleep(interval_seconds)
            _ping_all(POOL_SIZE)

    threading.Thread(target=loop, name="db-keepwarm", daemon=True).start()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
