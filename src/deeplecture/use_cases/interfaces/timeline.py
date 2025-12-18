"""Timeline storage protocol."""

from __future__ import annotations

from typing import Any, Protocol


class TimelineStorageProtocol(Protocol):
    """
    Timeline storage contract.

    Manages timeline JSON payloads on disk.
    """

    def load(self, content_id: str, language: str) -> dict[str, Any] | None:
        """
        Load timeline data from disk.

        Args:
            content_id: Content identifier
            language: Language code

        Returns:
            Timeline data or None if not found
        """
        ...

    def save(
        self,
        payload: dict[str, Any],
        content_id: str,
        language: str,
        learner_profile: str | None = None,
    ) -> None:
        """
        Save timeline data to disk.

        Args:
            payload: Timeline data
            content_id: Content identifier
            language: Language code
            learner_profile: Optional learner profile identifier
        """
        ...

    def exists(self, content_id: str, language: str) -> bool:
        """
        Check if timeline exists.

        Args:
            content_id: Content identifier
            language: Language code

        Returns:
            True if timeline exists
        """
        ...
