"""Domain error types."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain errors."""

    pass


class ContentNotFoundError(DomainError):
    """Raised when content is not found."""

    def __init__(self, content_id: str, message: str | None = None):
        self.content_id = content_id
        self.message = message or f"Content not found: {content_id}"
        super().__init__(self.message)


class InvalidStateError(DomainError):
    """Raised when an operation is invalid for the current state."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ValidationError(DomainError):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        self.message = message
        super().__init__(self.message)
