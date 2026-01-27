"""Ask (Q&A) storage protocol."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class AskStorageProtocol(Protocol):
    """Protocol for Q&A conversation persistence."""

    def load_history(self, content_id: str) -> list[dict] | None:
        """Load conversation history.

        Args:
            content_id: Content identifier.

        Returns:
            List of message dictionaries if exists, None otherwise.
        """
        ...

    def save_history(self, content_id: str, history: list[dict]) -> datetime:
        """Save conversation history.

        Args:
            content_id: Content identifier.
            history: List of message dictionaries.

        Returns:
            Timestamp when saved.
        """
        ...

    def clear_history(self, content_id: str) -> bool:
        """Clear conversation history.

        Args:
            content_id: Content identifier.

        Returns:
            True if cleared, False if not found.
        """
        ...
