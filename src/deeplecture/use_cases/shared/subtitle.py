"""Shared utilities for working with subtitles in use cases."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.transcription.interactive import SubtitleSegment
    from deeplecture.use_cases.interfaces.subtitle import SubtitleStorageProtocol

logger = logging.getLogger(__name__)

# Language priority for subtitle selection (higher index = higher priority)
LANGUAGE_PRIORITY = [
    "en",  # English - most common academic language
    "zh",  # Chinese
    "ja",  # Japanese
    "ko",  # Korean
    "es",  # Spanish
    "fr",  # French
    "de",  # German
]


def prioritize_subtitle_languages(languages: list[str]) -> list[str]:
    """
    Sort languages by priority for subtitle selection.

    English and enhanced versions get highest priority.

    Args:
        languages: List of available language codes.

    Returns:
        Languages sorted by priority (highest first).
    """
    if not languages:
        return []

    def get_priority(lang: str) -> tuple[int, int]:
        """Return (is_enhanced, base_priority) tuple for sorting."""
        # Enhanced versions get priority
        is_enhanced = 1 if lang.endswith("-enhanced") else 0
        base = lang.replace("-enhanced", "").lower()

        # Get base language priority
        try:
            base_priority = len(LANGUAGE_PRIORITY) - LANGUAGE_PRIORITY.index(base)
        except ValueError:
            base_priority = 0  # Unknown languages get lowest priority

        return (is_enhanced, base_priority)

    return sorted(languages, key=get_priority, reverse=True)


def load_first_available_subtitle_segments(
    storage: SubtitleStorageProtocol,
    *,
    content_id: str,
    candidate_languages: list[str],
) -> tuple[str, list[SubtitleSegment]] | None:
    """
    Load subtitle segments from the first available language.

    Args:
        storage: Subtitle storage interface.
        content_id: Content identifier.
        candidate_languages: Languages to try, in priority order.

    Returns:
        Tuple of (language, segments) if found, None otherwise.
    """
    for lang in candidate_languages:
        segments = storage.load(content_id, lang)
        if segments:
            logger.debug("Loaded subtitles for %s in %s", content_id, lang)
            return lang, segments

    logger.debug("No subtitles found for %s in languages: %s", content_id, candidate_languages)
    return None
