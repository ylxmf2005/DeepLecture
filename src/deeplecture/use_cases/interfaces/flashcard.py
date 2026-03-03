"""Flashcard storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class FlashcardStorageProtocol(Protocol):
    """
    Flashcard persistence contract.

    Stores flashcard items as JSON per content/language combination.
    """

    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None:
        """Load flashcard data from storage.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            Tuple of (flashcard_data, updated_at) if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime:
        """Save flashcard data to storage.

        Args:
            content_id: Content identifier.
            language: Flashcard language.
            data: Flashcard data to save (items, stats, etc.).

        Returns:
            Timestamp when saved.
        """
        ...

    def exists(self, content_id: str, language: str | None = None) -> bool:
        """Check if flashcards exist.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            True if flashcards exist, False otherwise.
        """
        ...
