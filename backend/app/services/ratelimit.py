"""
app/services/ratelimit.py — simple sliding-window limits for sensitive endpoints
(sign-in, password reset, 2FA codes, support requests).

In memory, per server process: right for a single Render instance. If you ever run
several instances, move this to Redis. Client IP comes from X-Forwarded-For (set by
Vercel/Render), falling back to the socket address.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def limit(key: str, max_hits: int, window_seconds: int, message: str = "Too many attempts. Please wait a few minutes and try again.") -> None:
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= max_hits:
            retry = int(window_seconds - (now - q[0])) + 1
            raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(retry)})
        q.append(now)


def reset(key: str) -> None:
    with _lock:
        _hits.pop(key, None)


def check(key: str, max_hits: int, window_seconds: int, message: str) -> None:
    """Raise if `key` is already over the limit, without counting this call."""
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= max_hits:
            retry = int(window_seconds - (now - q[0])) + 1
            raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(retry)})


def hit(key: str) -> None:
    """Count one failure against `key`."""
    with _lock:
        _hits[key].append(time.monotonic())
