"""Cheatsheet storage protocol."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class CheatsheetStorageProtocol(Protocol):
    """Protocol for cheatsheet persistence."""

    def load(self, content_id: str) -> tuple[str, datetime | None] | None:
        """Load cheatsheet content.

        Args:
            content_id: Content identifier.

        Returns:
            Tuple of (content, updated_at) if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, content: str) -> datetime:
        """Save cheatsheet content.

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
