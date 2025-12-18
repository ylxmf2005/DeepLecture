"""
Subtitle selection helpers for the UseCases layer.

This module centralizes the policy of "prefer enhanced subtitles, then fallback
to the base language" without leaking filesystem/path concerns into controllers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.domain.entities import Segment
    from deeplecture.use_cases.interfaces import SubtitleStorageProtocol

_ENHANCED_SUFFIX = "_enhanced"


def get_preferred_subtitle_languages(base_language: str) -> list[str]:
    """
    Return preferred subtitle language keys for a given base language.

    Examples:
    - "en" -> ["en_enhanced", "en"]
    - "en_enhanced" -> ["en_enhanced", "en"]
    """
    lang = (base_language or "").strip()
    if not lang:
        raise ValueError("base_language is required")

    if lang.endswith(_ENHANCED_SUFFIX):
        base = lang[: -len(_ENHANCED_SUFFIX)]
        base = base.strip()
        return [lang, base] if base else [lang]

    return [f"{lang}{_ENHANCED_SUFFIX}", lang]


def load_first_available_subtitle_segments(
    subtitle_storage: SubtitleStorageProtocol,
    *,
    content_id: str,
    candidate_languages: list[str],
) -> tuple[str, list[Segment]] | None:
    """Load subtitle segments from the first language key that exists."""
    for lang in candidate_languages:
        key = (lang or "").strip()
        if not key:
            continue
        segments = subtitle_storage.load(content_id, key)
        if segments:
            return key, segments
    return None


def load_subtitle_segments_with_fallback(
    subtitle_storage: SubtitleStorageProtocol,
    *,
    content_id: str,
    base_language: str,
) -> tuple[str, list[Segment]] | None:
    """Load subtitle segments with enhanced->base fallback for a base language."""
    return load_first_available_subtitle_segments(
        subtitle_storage,
        content_id=content_id,
        candidate_languages=get_preferred_subtitle_languages(base_language),
    )


def prioritize_subtitle_languages(available: list[str]) -> list[str]:
    """
    Sort available language codes so enhanced versions come before base versions.

    Given a list like ["en", "ja", "zh_enhanced", "en_enhanced", "zh"],
    returns ["en_enhanced", "en", "ja", "zh_enhanced", "zh"].

    The sort key ensures:
    1. Languages are grouped by their base (without _enhanced suffix)
    2. Within each group, _enhanced comes before the base version
    """

    def sort_key(lang: str) -> tuple[str, int]:
        if lang.endswith(_ENHANCED_SUFFIX):
            base = lang[: -len(_ENHANCED_SUFFIX)]
            return (base, 0)  # Enhanced comes first (0 < 1)
        return (lang, 1)  # Base comes second

    return sorted(available, key=sort_key)
