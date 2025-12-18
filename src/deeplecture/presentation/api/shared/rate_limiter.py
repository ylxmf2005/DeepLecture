"""
Rate Limiting Middleware.

In-memory token bucket rate limiter for Flask.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING

from flask import g, request

from deeplecture.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from flask import Flask, Request


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: float
    refill_rate: float
    tokens: float = field(default=0.0, init=False)
    last_refill: float = field(default_factory=time.time, init=False)
    lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_retry_after(self) -> float:
        """Get seconds until tokens are available."""
        with self.lock:
            if self.tokens >= 1.0:
                return 0.0
            tokens_needed = 1.0 - self.tokens
            return tokens_needed / self.refill_rate


class RateLimiter:
    """In-memory rate limiter with multiple limit tiers."""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, TokenBucket]] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 3600
        self._last_cleanup = time.time()

    def _get_client_id(self, req: Request) -> str:
        """
        Extract client identifier from request.

        Only trusts X-Forwarded-For when the request comes from a trusted proxy.
        This prevents attackers from spoofing their IP to bypass rate limiting.
        """
        settings = get_settings()
        trusted_proxies = set(settings.rate_limits.trusted_proxies)

        remote_addr = req.remote_addr or "unknown"

        # Only trust X-Forwarded-For if request comes from a trusted proxy
        if trusted_proxies and remote_addr in trusted_proxies:
            forwarded = req.headers.get("X-Forwarded-For", "")
            if forwarded:
                return forwarded.split(",")[0].strip()

        return remote_addr

    def _get_or_create_bucket(
        self,
        client_id: str,
        category: str,
        capacity: float,
        refill_rate: float,
    ) -> TokenBucket:
        """Get or create a token bucket for client and category."""
        with self._lock:
            now = time.time()
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_stale_buckets()
                self._last_cleanup = now

            if client_id not in self._buckets:
                self._buckets[client_id] = {}
            if category not in self._buckets[client_id]:
                self._buckets[client_id][category] = TokenBucket(
                    capacity=capacity,
                    refill_rate=refill_rate,
                )
            return self._buckets[client_id][category]

    def _cleanup_stale_buckets(self) -> None:
        """Remove buckets that haven't been used recently."""
        now = time.time()
        stale_threshold = 3600
        stale_clients = []
        for client_id, categories in self._buckets.items():
            all_stale = all(now - b.last_refill >= stale_threshold for b in categories.values())
            if all_stale:
                stale_clients.append(client_id)
        for client_id in stale_clients:
            del self._buckets[client_id]

    def check_rate_limit(self, req: Request, category: str = "default") -> tuple[bool, float]:
        """Check if request is within rate limit."""
        settings = get_settings()
        limits = settings.rate_limits
        client_id = self._get_client_id(req)

        if category == "upload":
            capacity = float(limits.upload_per_minute)
            refill_rate = capacity / 60.0
        elif category == "generate":
            capacity = float(limits.generate_per_hour)
            refill_rate = capacity / 3600.0
        else:
            capacity = float(limits.default_per_hour)
            refill_rate = capacity / 3600.0

        bucket = self._get_or_create_bucket(client_id, category, capacity, refill_rate)
        if bucket.consume():
            return True, 0.0
        return False, bucket.get_retry_after()


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def rate_limit(category: str = "default") -> Callable:
    """Decorator to apply rate limiting to a route."""
    from deeplecture.presentation.api.shared import response

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            allowed, retry_after = limiter.check_rate_limit(request, category)
            if not allowed:
                resp = response.rate_limited(f"Rate limit exceeded. Retry after {retry_after:.1f} seconds.")
                resp.headers["Retry-After"] = str(int(retry_after) + 1)
                return resp
            return f(*args, **kwargs)

        return wrapper

    return decorator


def init_rate_limiter(app: Flask) -> None:
    """Initialize rate limiting for Flask app."""
    limiter = get_rate_limiter()

    @app.before_request
    def check_default_rate_limit():
        if request.method == "OPTIONS":
            return None
        if "/stream/" in request.path:
            return None
        allowed, retry_after = limiter.check_rate_limit(request, "default")
        if not allowed:
            from deeplecture.presentation.api.shared import response

            resp = response.rate_limited(f"Rate limit exceeded. Retry after {retry_after:.1f} seconds.")
            resp.headers["Retry-After"] = str(int(retry_after) + 1)
            return resp
        g.rate_limit_client_id = limiter._get_client_id(request)
        return None
