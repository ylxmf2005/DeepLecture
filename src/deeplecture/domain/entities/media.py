"""
Media Entities

Time-based media structures used across subtitles, timelines, etc.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """
    A timed text segment.

    Used for subtitles, timeline segments, transcripts, etc.
    Immutable by design - segments don't change once created.
    """

    start: float  # seconds
    end: float  # seconds
    text: str

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.end - self.start

    def __post_init__(self) -> None:
        """Validate segment data."""
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")
        if self.end < self.start:
            raise ValueError(f"end ({self.end}) must be >= start ({self.start})")
