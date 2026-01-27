"""Subtitle storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.transcription.interactive import SubtitleSegment


class SubtitleStorageProtocol(Protocol):
    """Protocol for subtitle persistence."""

    def load(self, content_id: str, language: str) -> list[SubtitleSegment] | None:
        """Load subtitle segments for a language.

        Args:
            content_id: Content identifier.
            language: Language code.

        Returns:
            List of segments if exists, None otherwise.
        """
        ...

    def save(
        self,
        content_id: str,
        language: str,
        segments: list[SubtitleSegment],
    ) -> None:
        """Save subtitle segments.

        Args:
            content_id: Content identifier.
            language: Language code.
            segments: Subtitle segments.
        """
        ...

    def exists(self, content_id: str, language: str) -> bool:
        """Check if subtitle exists.

        Args:
            content_id: Content identifier.
            language: Language code.

        Returns:
            True if subtitle exists.
        """
        ...

    def list_languages(self, content_id: str) -> list[str]:
        """List available languages for content.

        Args:
            content_id: Content identifier.

        Returns:
            List of language codes.
        """
        ...
