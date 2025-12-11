"""
Unified retry utilities for LLM and TTS calls.

Provides a consistent retry mechanism with exponential backoff
that can be shared across different service types.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    RetryCallState,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def create_retry_decorator(
    max_retries: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_exceptions: Optional[Tuple[Type[BaseException], ...]] = None,
    logger_name: Optional[str] = None,
):
    """
    Create a tenacity retry decorator with consistent settings.

    Args:
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1)
        min_wait: Minimum wait time in seconds (exponential backoff base)
        max_wait: Maximum wait time in seconds (exponential backoff cap)
        retry_exceptions: Tuple of exception types to retry on. If None, retries on all Exceptions.
        logger_name: Logger name for retry logging. If None, uses module logger.

    Returns:
        A tenacity retry decorator configured with the specified settings.
    """
    log = logging.getLogger(logger_name) if logger_name else logger

    retry_condition = (
        retry_if_exception_type(retry_exceptions)
        if retry_exceptions
        else retry_if_exception_type(Exception)
    )

    return retry(
        stop=stop_after_attempt(max_retries + 1),  # +1 because first attempt is not a "retry"
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_condition,
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )


def with_retry(
    func: Callable[..., T],
    max_retries: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_exceptions: Optional[Tuple[Type[BaseException], ...]] = None,
    logger_name: Optional[str] = None,
) -> Callable[..., T]:
    """
    Wrap a function with retry logic.

    This is useful when you can't use a decorator directly (e.g., instance methods
    where you want to configure retry based on instance attributes).

    Args:
        func: The function to wrap with retry logic
        max_retries: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        retry_exceptions: Tuple of exception types to retry on
        logger_name: Logger name for retry logging

    Returns:
        The wrapped function with retry logic applied.
    """
    decorator = create_retry_decorator(
        max_retries=max_retries,
        min_wait=min_wait,
        max_wait=max_wait,
        retry_exceptions=retry_exceptions,
        logger_name=logger_name,
    )
    return decorator(func)


class RetryConfig:
    """
    Configuration holder for retry settings.

    Provides a consistent interface for loading retry settings from config dicts.
    """

    def __init__(
        self,
        max_retries: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 60.0,
    ) -> None:
        self.max_retries = max(0, max_retries)
        self.min_wait = max(0.0, min_wait)
        self.max_wait = max(self.min_wait, max_wait)

    @classmethod
    def from_config(cls, config: dict, prefix: str = "") -> "RetryConfig":
        """
        Load retry config from a dictionary.

        Supports both flat keys and prefixed keys:
        - max_retries / {prefix}_max_retries
        - retry_min_wait / {prefix}_retry_min_wait
        - retry_max_wait / {prefix}_retry_max_wait
        """
        def get_val(key: str, default: Any) -> Any:
            # Try prefixed key first, then unprefixed
            if prefix:
                prefixed = f"{prefix}_{key}"
                if prefixed in config:
                    return config[prefixed]
            return config.get(key, default)

        max_retries = int(get_val("max_retries", 3))
        min_wait = float(get_val("retry_min_wait", 1.0))
        max_wait = float(get_val("retry_max_wait", 60.0))

        return cls(
            max_retries=max_retries,
            min_wait=min_wait,
            max_wait=max_wait,
        )

    def create_decorator(
        self,
        retry_exceptions: Optional[Tuple[Type[BaseException], ...]] = None,
        logger_name: Optional[str] = None,
    ):
        """Create a retry decorator with this config's settings."""
        return create_retry_decorator(
            max_retries=self.max_retries,
            min_wait=self.min_wait,
            max_wait=self.max_wait,
            retry_exceptions=retry_exceptions,
            logger_name=logger_name,
        )
