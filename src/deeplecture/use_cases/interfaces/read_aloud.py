"""Read-aloud audio cache protocol."""

from __future__ import annotations

from typing import Protocol


class ReadAloudCacheProtocol(Protocol):
    """
    Contract for caching read-aloud audio segments.

    Audio is keyed by (content_id, sentence_key) where sentence_key
    follows the format "p{paragraph_index}_s{sentence_index}".
    """

    def save_audio(self, content_id: str, sentence_key: str, audio_data: bytes) -> None:
        """
        Save an audio segment to cache.

        Args:
            content_id: Content identifier
            sentence_key: Unique key like "p0_s2"
            audio_data: MP3 audio bytes
        """
        ...

    def load_audio(self, content_id: str, sentence_key: str) -> bytes | None:
        """
        Load a cached audio segment.

        Args:
            content_id: Content identifier
            sentence_key: Unique key like "p0_s2"

        Returns:
            MP3 audio bytes if cached, None otherwise
        """
        ...

    def clear(self, content_id: str) -> None:
        """
        Clear all cached audio for a content item.

        Args:
            content_id: Content identifier
        """
        ...
