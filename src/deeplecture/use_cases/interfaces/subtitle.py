"""Subtitle storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.domain.entities import Segment


class SubtitleStorageProtocol(Protocol):
    """
    Subtitle storage contract.

    Maps (content_id, language) pairs to subtitle files on disk.
    """

    def save(self, content_id: str, segments: list[Segment], language: str) -> None:
        """
        Save subtitle segments to disk.

        Args:
            content_id: Content identifier
            segments: List of subtitle segments
            language: Language code (e.g., "en", "zh", "en_enhanced")
        """
        ...

    def load(self, content_id: str, language: str) -> list[Segment] | None:
        """
        Load subtitle segments from disk.

        Args:
            content_id: Content identifier
            language: Language code

        Returns:
            List of segments or None if not found
        """
        ...

    def exists(self, content_id: str, language: str) -> bool:
        """
        Check if subtitle file exists.

        Args:
            content_id: Content identifier
            language: Language code

        Returns:
            True if file exists
        """
        ...

    def delete(self, content_id: str, language: str) -> bool:
        """
        Delete subtitle file if it exists.

        Args:
            content_id: Content identifier
            language: Language code

        Returns:
            True if file was deleted, False if it didn't exist
        """
        ...

    def list_languages(self, content_id: str) -> list[str]:
        """
        List available language codes for a content item.

        Args:
            content_id: Content identifier

        Returns:
            List of language codes discovered in storage (may be empty)
        """
        ...

    def save_background(self, content_id: str, data: dict) -> None:
        """
        Save background context data.

        Args:
            content_id: Content identifier
            data: Background context dictionary
        """
        ...
