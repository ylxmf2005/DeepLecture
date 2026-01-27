"""Note storage protocol."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class NoteStorageProtocol(Protocol):
    """Protocol for note persistence."""

    def load(self, content_id: str) -> tuple[str, datetime | None] | None:
        """Load note content.

        Args:
            content_id: Content identifier.

        Returns:
            Tuple of (content, updated_at) if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, content: str) -> datetime:
        """Save note content.

        Args:
            content_id: Content identifier.
            content: Markdown content to save.

        Returns:
            Timestamp when saved.
        """
        ...

    def exists(self, content_id: str) -> bool:
        """Check if note exists.

        Args:
            content_id: Content identifier.

        Returns:
            True if note exists.
        """
        ...
