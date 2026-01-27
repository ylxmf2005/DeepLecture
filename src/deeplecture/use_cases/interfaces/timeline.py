"""Timeline storage protocol."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class TimelineStorageProtocol(Protocol):
    """Protocol for timeline persistence."""

    def load(self, content_id: str) -> dict | None:
        """Load timeline data.

        Args:
            content_id: Content identifier.

        Returns:
            Timeline data if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, timeline: dict) -> datetime:
        """Save timeline data.

        Args:
            content_id: Content identifier.
            timeline: Timeline data dictionary.

        Returns:
            Timestamp when saved.
        """
        ...

    def exists(self, content_id: str) -> bool:
        """Check if timeline exists.

        Args:
            content_id: Content identifier.

        Returns:
            True if timeline exists.
        """
        ...
