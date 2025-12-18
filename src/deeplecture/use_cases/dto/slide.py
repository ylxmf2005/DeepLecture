"""Slide lecture DTOs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    id: int
    source: str
    target: str


@dataclass(frozen=True)
class TranscriptPage:
    deck_id: str
    page_index: int
    source_language: str
    target_language: str
    segments: list[TranscriptSegment]
    one_sentence_summary: str = ""


@dataclass(frozen=True)
class PageWorkPlan:
    page_index: int
    image_path: str
    transcript_json_path: str
    page_audio_wav_path: str
    segment_video_path: str


@dataclass(frozen=True)
class SlideGenerationRequest:
    """Request DTO for slide lecture generation.

    Contains only request-specific parameters passed from frontend.
    System configuration is injected via SlideLectureConfig.

    Attributes:
        content_id: Content identifier
        source_language: Language of slide content
        target_language: Target language for translation
        tts_language: Which language to use for TTS ("source" or "target")
        output_basename: Base name for output files
        llm_model: Runtime LLM model selection (None = use default)
        tts_model: Runtime TTS model selection (None = use default)
        prompts: Runtime prompt selection {func_id: impl_id}
    """

    content_id: str
    source_language: str
    target_language: str
    tts_language: str = "source"
    output_basename: str = "slide_lecture"
    # Runtime model/prompt selection (None = use defaults)
    llm_model: str | None = None
    tts_model: str | None = None
    prompts: tuple[tuple[str, str], ...] | None = None  # frozen: use tuple instead of dict


@dataclass(frozen=True)
class SlideGenerationResult:
    content_id: str
    video_path: str
    audio_wav_path: str
    page_count: int
    audio_duration: float
    video_duration: float
