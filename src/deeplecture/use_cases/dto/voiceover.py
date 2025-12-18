"""
Voiceover DTOs - Data Transfer Objects for the Voiceover Use Case.

This module contains:
- GenerateVoiceoverRequest: Input parameters for voiceover generation
- VoiceoverResult: Output of voiceover generation
- RetryPolicy: Configuration for TTS retry behavior
- Plan types: AlignmentPlan, ClipPlan, AudioOpPlan for Plan+Apply pattern

Design Decisions:
- DTOs are at the UseCase layer boundary (not Domain)
- Plan types make the Plan stage testable (pure function → data structure)
- AudioOpKind uses Literal instead of Enum for simplicity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# =============================================================================
# EXTERNAL API DTOs
# =============================================================================


@dataclass
class GenerateVoiceoverRequest:
    """
    Input parameters for voiceover generation.

    This DTO crosses the boundary from Controller to UseCase.
    """

    content_id: str
    video_path: str
    output_dir: str
    language: str = "zh"
    subtitle_language: str = "zh"
    audio_basename: str | None = None
    # Runtime model selection (None = use default)
    tts_model: str | None = None


@dataclass
class VoiceoverResult:
    """
    Result of voiceover generation.

    This DTO crosses the boundary from UseCase back to Controller.
    """

    audio_path: str  # Path to voiceover audio file (m4a)
    timeline_path: str  # Path to sync_timeline.json
    audio_duration: float  # Total audio duration in seconds
    video_duration: float  # Original video duration in seconds


# =============================================================================
# PLAN STAGE DTOs (for Plan+Apply pattern)
# =============================================================================

# Audio operation types: silence for gaps, copy for TTS audio
AudioOpKind = Literal["silence", "copy"]


@dataclass
class AudioOpPlan:
    """
    Plan for a single audio operation.

    This describes WHAT to do, not HOW to do it.
    The Apply stage executes this plan using AudioProcessorProtocol.
    """

    kind: AudioOpKind
    input_path: str | None  # None for silence generation
    output_path: str
    target_duration: float


@dataclass
class ClipPlan:
    """
    Plan for a single clip in the alignment.

    Maps a video timeline segment (src_*) to an audio operation.
    The dst_* values are calculated in the Apply stage using actual durations.
    """

    src_start: float  # Video timeline start
    src_end: float  # Video timeline end
    op: AudioOpPlan  # Audio operation to perform


@dataclass
class AlignmentPlan:
    """
    Complete alignment plan for all clips.

    This is the output of the Plan stage (pure function).
    The Apply stage iterates through clips and executes operations.
    """

    clips: list[ClipPlan] = field(default_factory=list)

    def add_clip(
        self,
        *,
        src_start: float,
        src_end: float,
        kind: AudioOpKind,
        input_path: str | None,
        output_path: str,
        target_duration: float,
    ) -> None:
        """Add a clip to the plan."""
        self.clips.append(
            ClipPlan(
                src_start=src_start,
                src_end=src_end,
                op=AudioOpPlan(
                    kind=kind,
                    input_path=input_path,
                    output_path=output_path,
                    target_duration=target_duration,
                ),
            )
        )
