"""Simple in-memory rate limiter for sign-in, uploads, and AI calls.

Good enough for one server instance. With several instances, move this to Redis or use the
host's built-in throttling (e.g. AWS WAF rate-based rules).
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def check(key: str, limit: int, window_seconds: int, message: str) -> None:
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry = int(window_seconds - (now - q[0])) + 1
            raise HTTPException(429, f"{message} Try again in {retry} seconds.", headers={"Retry-After": str(retry)})
        q.append(now)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def reset() -> None:
    with _lock:
        _hits.clear()
