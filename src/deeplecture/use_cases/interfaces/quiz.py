"""Quiz storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class QuizStorageProtocol(Protocol):
    """
    Quiz persistence contract.

    Stores quiz items as JSON per content/language combination.
    """

    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None:
        """Load quiz data from storage.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            Tuple of (quiz_data, updated_at) if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime:
        """Save quiz data to storage.

        Args:
            content_id: Content identifier.
            language: Quiz language.
            data: Quiz data to save (items, stats, etc.).

        Returns:
            Timestamp when saved.
        """
        ...

    def exists(self, content_id: str, language: str | None = None) -> bool:
        """Check if quiz exists.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            True if quiz exists, False otherwise.
        """
        ...
