"""Slide-related Data Transfer Objects."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple


@dataclass
class SlideDeckDTO:
    """Metadata for an uploaded PDF slide deck."""

    deck_id: str
    filename: str
    pdf_path: str
    output_dir: str
    page_count: int
    created_at: datetime


@dataclass
class SlideLectureGenerationResult:
    """Result of starting slide lecture generation."""

    deck_id: str
    lecture_video_path: str
    subtitle_path: str
    status: str
    message: str
    job_id: Optional[str] = None


@dataclass
class SlideGenerationContext:
    """Resolved paths and parameters for a generation job."""

    deck_id: str
    pdf_path: str
    page_count: int
    workspace_dir: str
    pages_dir: str
    transcripts_dir: str
    audio_dir: str
    subtitle_path: str
    video_output_path: str


@dataclass
class TranscriptSegment:
    """Single spoken segment for one slide page."""

    id: int
    source: str
    target: str


@dataclass
class TranscriptPage:
    """Transcript for a single page of a slide deck."""

    deck_id: str
    page_index: int
    source_language: str
    target_language: str
    segments: List[TranscriptSegment]
    one_sentence_summary: str = ""


@dataclass
class TranscriptHistory:
    """Maintains context from previous pages for sequential generation."""

    prev_transcript_text: str = ""
    summary_lines: List[str] = field(default_factory=list)

    def as_prompt_blocks(
        self,
        *,
        max_prev_chars: int = 2000,
        max_summaries: int = 15,
        lookback_pages: int = -1,
        summary_lookback_pages: int = -1,
    ) -> Tuple[str, str]:
        """Format history as prompt blocks with truncation limits."""
        prev = ""
        if lookback_pages != 0:
            prev = self.prev_transcript_text
            if len(prev) > max_prev_chars:
                prev = "..." + prev[-max_prev_chars:].lstrip()

        if summary_lookback_pages == 0:
            summaries = ""
        elif summary_lookback_pages > 0:
            recent = self.summary_lines[-summary_lookback_pages:]
            summaries = "\n".join(recent)
        else:
            recent = self.summary_lines[-max_summaries:]
            summaries = "\n".join(recent)

        return prev, summaries

    def after_page(self, page: "TranscriptPage") -> "TranscriptHistory":
        """
        Create updated history after processing a page.

        Appends the page's transcript to prev_transcript_text and adds
        the one-sentence summary to summary_lines.

        Args:
            page: The completed TranscriptPage

        Returns:
            New TranscriptHistory with updated context
        """
        # Build transcript text from page segments
        page_text = "\n".join(seg.source for seg in page.segments if seg.source)

        # Append to previous transcript
        new_prev = self.prev_transcript_text
        if new_prev and page_text:
            new_prev = new_prev + "\n\n" + page_text
        elif page_text:
            new_prev = page_text

        # Add summary if present
        new_summaries = list(self.summary_lines)
        if page.one_sentence_summary:
            new_summaries.append(f"Page {page.page_index}: {page.one_sentence_summary}")

        return TranscriptHistory(
            prev_transcript_text=new_prev,
            summary_lines=new_summaries,
        )


@dataclass
class AudioSegmentInfo:
    """Timeline and text for a synthesized TTS segment."""

    page_index: int
    segment_index: int
    start: float
    end: float
    source: str
    target: str
    audio_path: str = ""


@dataclass
class PageAudioArtifacts:
    """Audio artifacts for a single page."""

    page_index: int
    page_audio_path: str
    page_duration: float
    segment_durations: List[float]


@dataclass
class PageVideoArtifacts:
    """Video artifacts for a single page."""

    page_index: int
    segment_path: str
