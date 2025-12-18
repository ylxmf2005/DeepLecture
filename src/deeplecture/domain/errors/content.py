"""Content-related errors."""

from __future__ import annotations

from deeplecture.domain.errors.base import DomainError


class ContentNotFoundError(DomainError):
    """Raised when content is not found."""

    def __init__(self, content_id: str) -> None:
        self.content_id = content_id
        super().__init__(f"Content not found: {content_id}")
