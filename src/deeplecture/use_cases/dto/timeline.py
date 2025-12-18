"""Timeline DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class GenerateTimelineRequest:
    """Request to generate timeline.

    All language parameters must be provided by the frontend.
    """

    content_id: str
    subtitle_language: str  # Required: source language for loading subtitles
    output_language: str  # Required: target language for LLM output
    learner_profile: str | None = None
    force: bool = False
    # Runtime model/prompt selection (None = use defaults)
    llm_model: str | None = None
    prompts: dict[str, str] | None = None  # {func_id: impl_id}


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class TimelineEntry:
    """
    A single timeline entry shown at a specific playback time.

    Represents a knowledge unit with explanation content.
    """

    id: int
    kind: str  # e.g., "segment_explanation"
    start: float  # Trigger time in seconds
    end: float  # End time in seconds
    title: str
    markdown: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "kind": self.kind,
            "start": self.start,
            "end": self.end,
            "title": self.title,
            "markdown": self.markdown,
        }


@dataclass
class TimelineResult:
    """Result of timeline generation."""

    content_id: str
    language: str
    entries: list[TimelineEntry]
    cached: bool = False
    status: str = "ready"

    @property
    def count(self) -> int:
        """Number of timeline entries."""
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "video_id": self.content_id,  # Keep legacy API compatibility
            "language": self.language,
            "timeline": [entry.to_dict() for entry in self.entries],
            "count": self.count,
            "cached": self.cached,
            "status": self.status,
        }


# =============================================================================
# Internal DTOs (used within UseCase)
# =============================================================================


@dataclass
class SubtitleSegment:
    """
    Single subtitle entry with timing in seconds.

    Simple, self-contained representation for timeline generation.
    """

    id: int
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        """Segment duration in seconds."""
        return max(0.0, self.end - self.start)


@dataclass
class KnowledgeUnit:
    """
    A higher-level conceptual slice of the lecture.

    Represents a continuous time range covering one main idea.
    """

    id: int
    start: float
    end: float
    title: str
