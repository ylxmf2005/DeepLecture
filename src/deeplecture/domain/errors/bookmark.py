"""Bookmark-related errors."""

from __future__ import annotations

from deeplecture.domain.errors.base import DomainError


class BookmarkNotFoundError(DomainError):
    """Raised when a bookmark ID is not found."""

    def __init__(self, bookmark_id: str) -> None:
        self.bookmark_id = bookmark_id
        super().__init__(f"Bookmark not found: {bookmark_id}")
