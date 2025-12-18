"""Artifact domain entities."""

from __future__ import annotations

from enum import Enum
from typing import Final


class ArtifactKind(str, Enum):
    """
    Artifact kinds used across the system.

    Naming convention:
    - Simple kinds: single word (source, video, timeline)
    - Namespaced kinds: category:variant (subtitle:original, voiceover:audio)
    """

    # Primary content artifacts
    SOURCE = "source"
    VIDEO = "video"

    # Subtitle artifacts
    SUBTITLE_ORIGINAL = "subtitle:original"
    SUBTITLE_TRANSLATED = "subtitle:translated"
    SUBTITLE_ENHANCED = "subtitle:enhanced"
    SUBTITLE_BACKGROUND = "subtitle:background"

    # Timeline artifacts
    TIMELINE = "timeline"

    # Voiceover artifacts
    VOICEOVER_AUDIO = "voiceover:audio"
    VOICEOVER_SYNC_TIMELINE = "voiceover:sync_timeline"

    # Slide lecture artifacts
    SLIDE_PDF = "slide:pdf"
    SLIDE_IMAGES = "slide:images"


# Fallback chain for video resolution (immutable to prevent runtime mutation)
VIDEO_FALLBACK_CHAIN: Final[tuple[str, ...]] = (
    ArtifactKind.VIDEO.value,
    ArtifactKind.SOURCE.value,
)
