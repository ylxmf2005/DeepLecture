"""Subtitle-related errors."""

from __future__ import annotations

from deeplecture.domain.errors.base import DomainError


class SubtitleError(DomainError):
    """Base class for subtitle-related errors."""


class SubtitleGenerationError(SubtitleError):
    """Raised when subtitle generation fails."""


class SubtitleNotFoundError(SubtitleError):
    """Raised when subtitle is not found."""

    def __init__(self, content_id: str, language: str) -> None:
        self.content_id = content_id
        self.language = language
        super().__init__(f"Subtitle not found: {content_id}/{language}")
