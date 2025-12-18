"""Subtitle DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deeplecture.domain.entities import Segment


# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class GenerateSubtitleRequest:
    """Request to generate subtitles.

    All language parameters must be provided by the frontend.
    """

    content_id: str
    language: str


@dataclass
class EnhanceTranslateRequest:
    """Request to enhance and translate subtitles.

    All language parameters must be provided by the frontend.
    """

    content_id: str
    source_language: str
    target_language: str
    # Runtime model/prompt selection (None = use defaults)
    llm_model: str | None = None
    prompts: dict[str, str] | None = None  # {func_id: impl_id}


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class SubtitleResult:
    """Result of subtitle generation."""

    content_id: str
    segments: list[Segment]
    language: str

    @property
    def text(self) -> str:
        """Get full text without timing."""
        return " ".join(seg.text for seg in self.segments)

    def to_srt(self) -> str:
        """Convert to SRT format."""
        lines = []
        for i, seg in enumerate(self.segments, 1):
            start = _format_srt_time(seg.start)
            end = _format_srt_time(seg.end)
            lines.append(f"{i}\n{start} --> {end}\n{seg.text}\n")
        return "\n".join(lines)

    def to_vtt(self) -> str:
        """Convert to WebVTT format."""
        lines = ["WEBVTT", ""]
        for i, seg in enumerate(self.segments, 1):
            start = _format_vtt_time(seg.start)
            end = _format_vtt_time(seg.end)
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)


# =============================================================================
# Internal DTOs (used within UseCase)
# =============================================================================


@dataclass
class BackgroundContext:
    """Extracted background context from transcript."""

    topic: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    tone: str = "neutral"

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "summary": self.summary,
            "keywords": self.keywords,
            "tone": self.tone,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackgroundContext:
        return cls(
            topic=data.get("topic", ""),
            summary=data.get("summary", ""),
            keywords=data.get("keywords", []),
            tone=data.get("tone", "neutral"),
        )


@dataclass
class BilingualSegment:
    """A segment with both source and target language text."""

    start: float
    end: float
    text_source: str
    text_target: str

    def to_source_segment(self) -> Segment:
        from deeplecture.domain.entities import Segment

        return Segment(start=self.start, end=self.end, text=self.text_source)

    def to_target_segment(self) -> Segment:
        from deeplecture.domain.entities import Segment

        return Segment(start=self.start, end=self.end, text=self.text_target)


# =============================================================================
# Utilities
# =============================================================================


def _format_srt_time(seconds: float) -> str:
    """Format seconds to SRT time format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_time(seconds: float) -> str:
    """Format seconds to VTT time format: HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
