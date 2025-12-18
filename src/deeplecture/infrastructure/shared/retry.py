"""
Unified retry utilities.

Provides tenacity-based retry mechanism with exponential backoff
for LLM and TTS API calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Immutable retry configuration."""

    max_retries: int
    min_wait: float
    max_wait: float

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.min_wait < 0:
            raise ValueError("min_wait must be >= 0")
        if self.max_wait < self.min_wait:
            raise ValueError("max_wait must be >= min_wait")


def create_retry_decorator(
    config: RetryConfig,
    retry_exceptions: tuple[type[BaseException], ...] | None = None,
    logger_name: str | None = None,
):
    """
    Create a tenacity retry decorator.

    Args:
        config: Retry configuration.
        retry_exceptions: Exception types to retry on. Defaults to Exception.
        logger_name: Logger name for retry warnings.

    Returns:
        A tenacity retry decorator.
    """
    log = logging.getLogger(logger_name) if logger_name else logger

    retry_condition = (
        retry_if_exception_type(retry_exceptions) if retry_exceptions else retry_if_exception_type(Exception)
    )

    return retry(
        stop=stop_after_attempt(config.max_retries + 1),
        wait=wait_exponential(multiplier=1, min=config.min_wait, max=config.max_wait),
        retry=retry_condition,
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )


def with_retry(
    func: Callable[..., T],
    config: RetryConfig,
    retry_exceptions: tuple[type[BaseException], ...] | None = None,
    logger_name: str | None = None,
) -> Callable[..., T]:
    """
    Wrap a function with retry logic.

    Args:
        func: Function to wrap.
        config: Retry configuration.
        retry_exceptions: Exception types to retry on.
        logger_name: Logger for retry warnings.

    Returns:
        Wrapped function with retry logic.
    """
    decorator = create_retry_decorator(
        config=config,
        retry_exceptions=retry_exceptions,
        logger_name=logger_name,
    )
    return decorator(func)
