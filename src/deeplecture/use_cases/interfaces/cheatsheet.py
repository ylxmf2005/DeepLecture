"""Cheatsheet storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class CheatsheetStorageProtocol(Protocol):
    """
    Cheatsheet persistence contract.

    Stores a single Markdown cheatsheet file per content item.
    """

    def load(self, content_id: str) -> tuple[str, datetime | None] | None:
        """Load cheatsheet content from storage.

        Args:
            content_id: Content identifier.

        Returns:
            Tuple of (content, updated_at) if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, content: str) -> datetime:
        """Save cheatsheet content to storage.

        Args:
            content_id: Content identifier.
            content: Markdown content to save.

        Returns:
            Timestamp when saved.
        """
        ...

    def exists(self, content_id: str) -> bool:
        """Check if cheatsheet exists.

        Args:
            content_id: Content identifier.

        Returns:
            True if cheatsheet exists, False otherwise.
        """
        ...
