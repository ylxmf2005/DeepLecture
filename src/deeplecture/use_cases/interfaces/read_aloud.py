"""Read-aloud audio cache protocol."""

from __future__ import annotations

from typing import Protocol


class ReadAloudCacheProtocol(Protocol):
    """
    Contract for caching read-aloud audio segments.

    Audio is keyed by (content_id, variant_key, sentence_key), where:
    - variant_key identifies language/model/voice/content snapshot
    - sentence_key follows "p{paragraph_index}_s{sentence_index}"
    """

    def save_audio(self, content_id: str, variant_key: str, sentence_key: str, audio_data: bytes) -> None:
        """
        Save an audio segment to cache.

        Args:
            content_id: Content identifier
            variant_key: Read-aloud cache variant key
            sentence_key: Sentence key like "p0_s2"
            audio_data: MP3 audio bytes
        """
        ...

    def load_audio(self, content_id: str, variant_key: str, sentence_key: str) -> bytes | None:
        """
        Load a cached audio segment.

        Args:
            content_id: Content identifier
            variant_key: Read-aloud cache variant key
            sentence_key: Sentence key like "p0_s2"

        Returns:
            MP3 audio bytes if cached, None otherwise
        """
        ...

    def clear(self, content_id: str, variant_key: str | None = None) -> None:
        """
        Clear cached audio for a content item.

        Args:
            content_id: Content identifier
            variant_key: Optional variant key (None = clear all variants)
        """
        ...
