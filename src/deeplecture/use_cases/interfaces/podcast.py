"""Podcast storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class PodcastStorageProtocol(Protocol):
    """
    Podcast persistence contract.

    Stores podcast manifest (dialogue + timestamps) as JSON and audio as M4A
    per content/language combination.
    """

    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None:
        """Load podcast manifest from storage.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            Tuple of (podcast_data, updated_at) if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime:
        """Save podcast manifest to storage.

        Args:
            content_id: Content identifier.
            language: Podcast language.
            data: Podcast data to save (segments, title, summary, etc.).

        Returns:
            Timestamp when saved.
        """
        ...

    def exists(self, content_id: str, language: str | None = None) -> bool:
        """Check if podcast exists.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            True if podcast exists, False otherwise.
        """
        ...

    def get_audio_path(self, content_id: str, language: str) -> str:
        """Get the filesystem path for the podcast audio file.

        Args:
            content_id: Content identifier.
            language: Podcast language.

        Returns:
            Absolute path to the M4A audio file.
        """
        ...
