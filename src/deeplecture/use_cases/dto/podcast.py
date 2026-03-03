"""Podcast DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

# =============================================================================
# Internal DTOs
# =============================================================================


@dataclass
class DialogueItem:
    """Single dialogue turn in a podcast conversation.

    Each item represents one speaker's utterance.
    """

    speaker: str  # "host" | "guest"
    text: str  # Dialogue text (dramatized version)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"speaker": self.speaker, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DialogueItem:
        """Create from dictionary."""
        return cls(
            speaker=data.get("speaker", "host"),
            text=data.get("text", ""),
        )


@dataclass
class PodcastSegment:
    """Audio segment with timestamp for transcript synchronization.

    Maps a dialogue item to its position in the merged audio file.
    """

    speaker: str  # "host" | "guest"
    text: str  # Dialogue text
    start_time: float  # Start position in merged audio (seconds)
    end_time: float  # End position in merged audio (seconds)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "speaker": self.speaker,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PodcastSegment:
        """Create from dictionary."""
        return cls(
            speaker=data.get("speaker", "host"),
            text=data.get("text", ""),
            start_time=float(data.get("start_time", 0)),
            end_time=float(data.get("end_time", 0)),
        )


# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class GeneratePodcastRequest:
    """Request to generate a podcast conversation.

    Supports dual TTS models — one per speaker role.
    """

    content_id: str
    language: str  # Required: output language
    context_mode: str = "both"  # subtitle | slide | both
    user_instruction: str = ""
    subject_type: str = "auto"  # stem | humanities | auto
    llm_model: str | None = None  # LLM model override
    tts_model_host: str | None = None  # Host TTS model
    tts_model_guest: str | None = None  # Guest TTS model
    voice_id_host: str | None = None  # Host voice ID
    voice_id_guest: str | None = None  # Guest voice ID
    turn_gap_seconds: float = 0.3  # Silence between speaker turns
    prompts: dict[str, str] | None = None  # Prompt template overrides


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class PodcastStats:
    """Statistics about podcast generation."""

    total_dialogue_items: int = 0  # Items from dialogue LLM
    tts_success_count: int = 0  # Successful TTS calls
    tts_failure_count: int = 0  # Failed TTS calls (silence fallback)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_dialogue_items": self.total_dialogue_items,
            "tts_success_count": self.tts_success_count,
            "tts_failure_count": self.tts_failure_count,
        }


@dataclass
class PodcastResult:
    """Result of podcast retrieval."""

    content_id: str
    language: str
    title: str = ""
    summary: str = ""
    segments: list[PodcastSegment] = field(default_factory=list)
    duration: float = 0.0  # Total audio duration in seconds
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "language": self.language,
            "title": self.title,
            "summary": self.summary,
            "segments": [s.to_dict() for s in self.segments],
            "segment_count": len(self.segments),
            "duration": self.duration,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class GeneratedPodcastResult:
    """Result of AI-generated podcast creation."""

    content_id: str
    language: str
    title: str
    summary: str
    segments: list[PodcastSegment]
    duration: float
    updated_at: datetime | None
    used_sources: list[str]  # ["subtitle", "slide"]
    stats: PodcastStats = field(default_factory=PodcastStats)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "language": self.language,
            "title": self.title,
            "summary": self.summary,
            "segments": [s.to_dict() for s in self.segments],
            "segment_count": len(self.segments),
            "duration": self.duration,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "used_sources": self.used_sources,
            "stats": self.stats.to_dict(),
        }
