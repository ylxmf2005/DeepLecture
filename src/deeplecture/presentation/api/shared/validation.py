"""
Input validation utilities for API layer.

Provides reusable validators for common input types.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
CONTENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
DANGEROUS_PATH_CHARS = re.compile(r"[/\\:]|\.\.|\x00")

MAX_CONTENT_ID_LENGTH = 128
MAX_FILENAME_LENGTH = 255
MAX_MESSAGE_LENGTH = 10000
MAX_URL_LENGTH = 2048
MAX_TITLE_LENGTH = 500


class ValidationError(ValueError):
    """Raised when input validation fails."""


def validate_content_id(content_id: str | None, *, field_name: str = "content_id") -> str:
    """Validate content ID format."""
    if not content_id:
        raise ValidationError(f"{field_name} is required")
    content_id = content_id.strip()
    if len(content_id) > MAX_CONTENT_ID_LENGTH:
        raise ValidationError(f"{field_name} exceeds maximum length")
    if not (UUID_PATTERN.match(content_id) or CONTENT_ID_PATTERN.match(content_id)):
        raise ValidationError(f"{field_name} contains invalid characters")
    return content_id


def validate_uuid(value: str | None, *, field_name: str = "id") -> str:
    """Validate UUID format."""
    if not value:
        raise ValidationError(f"{field_name} is required")
    value = value.strip().lower()
    if not UUID_PATTERN.match(value):
        raise ValidationError(f"{field_name} must be a valid UUID")
    return value


def validate_task_id(task_id: str | None, *, field_name: str = "task_id") -> str:
    """Validate task ID format."""
    if not task_id:
        raise ValidationError(f"{field_name} is required")
    task_id = task_id.strip()
    if len(task_id) > 256:
        raise ValidationError(f"{field_name} exceeds maximum length")
    if DANGEROUS_PATH_CHARS.search(task_id):
        raise ValidationError(f"{field_name} contains invalid characters")
    return task_id


def validate_filename(
    filename: str | None,
    *,
    field_name: str = "filename",
    allowed_extensions: set[str] | None = None,
) -> str:
    """Validate filename for safety."""
    if not filename:
        raise ValidationError(f"{field_name} is required")
    filename = filename.strip()
    if len(filename) > MAX_FILENAME_LENGTH:
        raise ValidationError(f"{field_name} exceeds maximum length")
    if DANGEROUS_PATH_CHARS.search(filename):
        raise ValidationError(f"{field_name} contains invalid characters")
    if allowed_extensions:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in allowed_extensions:
            allowed = ", ".join(sorted(allowed_extensions))
            raise ValidationError(f"{field_name} must have extension: {allowed}")
    return filename


def validate_url(
    url: str | None,
    *,
    field_name: str = "url",
    allowed_schemes: set[str] | None = None,
) -> str:
    """Validate URL format and safety."""
    if not url:
        raise ValidationError(f"{field_name} is required")
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise ValidationError(f"{field_name} exceeds maximum length")
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValidationError(f"{field_name} is not a valid URL") from None
    if not parsed.scheme or not parsed.netloc:
        raise ValidationError(f"{field_name} is not a valid URL")
    schemes = allowed_schemes or {"http", "https"}
    if parsed.scheme.lower() not in schemes:
        raise ValidationError(f"{field_name} must use {' or '.join(schemes)}")
    hostname = parsed.hostname or ""
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValidationError(f"{field_name} cannot target localhost")
    if hostname.startswith(("10.", "172.", "192.168.", "169.254.")):
        raise ValidationError(f"{field_name} cannot target private networks")
    return url


def validate_message(
    message: str | None,
    *,
    field_name: str = "message",
    max_length: int = MAX_MESSAGE_LENGTH,
    min_length: int = 1,
) -> str:
    """Validate text message/content."""
    if not message:
        raise ValidationError(f"{field_name} is required")
    message = message.strip()
    if len(message) < min_length:
        raise ValidationError(f"{field_name} is required")
    if len(message) > max_length:
        raise ValidationError(f"{field_name} exceeds maximum length ({max_length})")
    return message


def validate_title(
    title: str | None,
    *,
    field_name: str = "title",
    required: bool = False,
    default: str = "",
) -> str:
    """Validate title field."""
    if not title:
        if required:
            raise ValidationError(f"{field_name} is required")
        return default
    title = title.strip()
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"{field_name} exceeds maximum length")
    return title


def validate_positive_int(
    value: int | str | None,
    *,
    field_name: str = "value",
    required: bool = False,
    default: int | None = None,
    max_value: int | None = None,
) -> int | None:
    """Validate positive integer."""
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required")
        return default
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a number") from None
    if int_value < 0:
        raise ValidationError(f"{field_name} must be non-negative")
    if max_value is not None and int_value > max_value:
        raise ValidationError(f"{field_name} exceeds maximum value ({max_value})")
    return int_value


def validate_language(
    language: str | None,
    *,
    field_name: str = "language",
    default: str = "en",
    allow_auto: bool = False,
) -> str:
    """Validate language code.

    Supports:
        - Basic codes: en, zh, eng
        - Extended codes with suffix: en_enhanced, zh_translated
    """
    if not language:
        return default
    language = language.strip().lower()
    if allow_auto and language == "auto":
        return language
    if not re.match(r"^[a-z]{2,3}(_[a-z]+)?$", language):
        raise ValidationError(f"{field_name} must be a valid language code")
    return language
