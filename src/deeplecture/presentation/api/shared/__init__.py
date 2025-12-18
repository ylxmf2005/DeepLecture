"""Shared API utilities."""

from deeplecture.presentation.api.shared.errors import handle_errors, register_error_handlers
from deeplecture.presentation.api.shared.rate_limiter import init_rate_limiter, rate_limit
from deeplecture.presentation.api.shared.response import (
    accepted,
    bad_request,
    created,
    error,
    not_found,
    rate_limited,
    success,
)

__all__ = [
    "accepted",
    "bad_request",
    "created",
    "error",
    "handle_errors",
    "init_rate_limiter",
    "not_found",
    "rate_limit",
    "rate_limited",
    "register_error_handlers",
    "success",
]
