from __future__ import annotations

import threading
import time
from typing import Callable, Optional


class RateLimiter:
    """
    Simple thread-safe token bucket rate limiter.

    The limiter models a bucket that refills at a fixed rate (tokens per
    second) up to a fixed capacity. Each `acquire` call consumes tokens
    and blocks until enough tokens are available.
    """

    def __init__(
        self,
        max_rpm: int = 60,
        *,
        burst_ratio: float = 1.0,
        now: Optional[Callable[[], float]] = None,
    ) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_rpm: Maximum average operations per minute.
            burst_ratio: Multiplier applied to capacity to allow short bursts.
            now: Optional time source for tests; defaults to time.monotonic.
        """
        if max_rpm <= 0:
            max_rpm = 1

        if burst_ratio <= 0.0:
            burst_ratio = 1.0

        self._burst_ratio = burst_ratio
        self._rate_per_second = max_rpm / 60.0
        self._capacity = max(1.0, max_rpm * burst_ratio)
        self._tokens = self._capacity

        self._now = now or time.monotonic
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._last_refill_time = self._now()

    def _refill(self, now: float) -> None:
        """
        Refill tokens based on elapsed time since last refill.
        """
        elapsed = now - self._last_refill_time
        if elapsed <= 0.0:
            return

        added = elapsed * self._rate_per_second
        if added <= 0.0:
            return

        self._tokens = min(self._capacity, self._tokens + added)
        self._last_refill_time = now

    def acquire(self, tokens: float = 1.0) -> None:
        """
        Block until the requested number of tokens is available.

        Args:
            tokens: Number of tokens to consume (fractional allowed).
        """
        if tokens <= 0.0:
            return

        with self._cv:
            while True:
                now = self._now()
                self._refill(now)

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                missing = tokens - self._tokens
                wait_seconds = missing / self._rate_per_second if self._rate_per_second > 0.0 else 0.001
                if wait_seconds <= 0.0:
                    wait_seconds = 0.001

                self._cv.wait(timeout=wait_seconds)

    def update_limit(self, max_rpm: int) -> None:
        """
        Update the maximum rate (RPM) at runtime.

        This adjusts the refill rate and capacity while preserving the
        current token level up to the new capacity.
        """
        if max_rpm <= 0:
            max_rpm = 1

        with self._cv:
            now = self._now()
            self._refill(now)

            self._rate_per_second = max_rpm / 60.0
            new_capacity = max(1.0, max_rpm * self._burst_ratio)
            self._capacity = new_capacity
            if self._tokens > new_capacity:
                self._tokens = new_capacity

            self._cv.notify_all()

