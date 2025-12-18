"""
Unified Error Handling for API Layer.

Maps domain errors to appropriate HTTP responses.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from werkzeug.exceptions import HTTPException

from deeplecture.domain.errors import (
    ContentNotFoundError,
    DomainError,
    InvalidURLError,
    PDFMergeError,
    SubtitleGenerationError,
    SubtitleNotFoundError,
    TaskNotFoundError,
    UnsupportedFileFormatError,
    UploadError,
    VideoDownloadError,
    VideoMergeError,
)
from deeplecture.presentation.api.shared import response
from deeplecture.presentation.api.shared.validation import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from flask import Flask, Response

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

ERROR_CODE_MAP: dict[type[Exception], tuple[str, int]] = {
    ContentNotFoundError: ("CONTENT_NOT_FOUND", 404),
    SubtitleNotFoundError: ("SUBTITLE_NOT_FOUND", 404),
    TaskNotFoundError: ("TASK_NOT_FOUND", 404),
    InvalidURLError: ("INVALID_URL", 400),
    UnsupportedFileFormatError: ("UNSUPPORTED_FORMAT", 400),
    SubtitleGenerationError: ("SUBTITLE_GENERATION_FAILED", 500),
    VideoDownloadError: ("VIDEO_DOWNLOAD_FAILED", 500),
    VideoMergeError: ("VIDEO_MERGE_FAILED", 500),
    PDFMergeError: ("PDF_MERGE_FAILED", 500),
    UploadError: ("UPLOAD_FAILED", 500),
    DomainError: ("DOMAIN_ERROR", 400),
    ValidationError: ("VALIDATION_ERROR", 400),
    ValueError: ("INVALID_REQUEST", 400),
    KeyError: ("MISSING_FIELD", 400),
    TypeError: ("INVALID_TYPE", 400),
}


def handle_errors(func: Callable[P, R]) -> Callable[P, Response | R]:
    """Decorator that catches exceptions and converts to API error responses."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Response | R:
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise  # Let Flask handle HTTP exceptions (400, 404, etc.)
        except Exception as exc:
            return _exception_to_response(exc)

    return wrapper


def _exception_to_response(exc: Exception) -> Response:
    """Convert exception to appropriate error response."""
    exc_type = type(exc)
    code, status = ERROR_CODE_MAP.get(exc_type, ("INTERNAL_ERROR", 500))

    if code == "INTERNAL_ERROR" and isinstance(exc, DomainError):
        code, status = "DOMAIN_ERROR", 400

    message = _safe_error_message(exc)

    if status >= 500:
        logger.exception("Server error: %s", exc)
    else:
        logger.warning("Client error [%s]: %s", code, message)

    return response.error(message, code=code, status=status)


def _safe_error_message(exc: Exception) -> str:
    """Extract safe error message for client (no paths or internals)."""
    msg = str(exc)
    if len(msg) > 200:
        msg = msg[:200] + "..."
    if "/" in msg and any(p in msg.lower() for p in ["/home/", "/users/", "/var/", "/tmp/"]):
        return "Operation failed. Check server logs for details."
    return msg


def register_error_handlers(app: Flask) -> None:
    """Register global error handlers for Flask app."""

    @app.errorhandler(400)
    def handle_bad_request(error: Exception) -> Response:
        return response.bad_request(str(error))

    @app.errorhandler(404)
    def handle_not_found(error: Exception) -> Response:
        return response.not_found("Resource not found")

    @app.errorhandler(405)
    def handle_method_not_allowed(error: Exception) -> Response:
        return response.error("Method not allowed", code="METHOD_NOT_ALLOWED", status=405)

    @app.errorhandler(429)
    def handle_rate_limit(error: Exception) -> Response:
        return response.rate_limited()

    @app.errorhandler(500)
    def handle_server_error(error: Exception) -> Response:
        logger.exception("Unhandled server error: %s", error)
        return response.error("Internal server error", code="INTERNAL_ERROR", status=500)

    for exc_type, (code, status) in ERROR_CODE_MAP.items():
        _register_domain_handler(app, exc_type, code, status)


def _register_domain_handler(
    app: Flask,
    exc_type: type[Exception],
    code: str,
    status: int,
) -> None:
    """Register handler for a specific domain exception type."""

    @app.errorhandler(exc_type)
    def handler(error: Exception) -> Response:
        message = _safe_error_message(error)
        if status >= 500:
            logger.exception("Domain error [%s]: %s", code, error)
        return response.error(message, code=code, status=status)

    handler.__name__ = f"handle_{exc_type.__name__}"
