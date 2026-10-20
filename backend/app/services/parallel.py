"""
app/services/parallel.py — run independent read-only queries concurrently.

Queries inside one request are otherwise strictly sequential, so a screen that
needs five independent results pays five network round trips to the database.
Running them on separate pooled connections makes it roughly one.
Only use for reads; writes stay in the request's own session/transaction.
"""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.database import SessionLocal

_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="dbread")


def _run(fn: Callable[[Session], Any]) -> Any:
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()


def run_parallel(*fns: Callable[[Session], Any]) -> list:
    # copy_context keeps per-request query counting (Server-Timing) working in worker threads
    futures = [_pool.submit(copy_context().run, _run, fn) for fn in fns]
    return [f.result() for f in futures]
