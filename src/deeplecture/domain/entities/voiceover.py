"""
Voiceover Domain Entities - Pure data structures and pure functions.

This module contains:
- SubtitleSegment: Subtitle entry with timing and index
- SyncSegment: A/V sync mapping for playback-side synchronization
- Pure functions: SRT parsing, segment merging

Design Decisions:
- SubtitleSegment has its own `index` field for stable sorting (not reusing Segment)
- All thresholds are constants to prevent magic number drift
- Pure functions have no I/O - they only transform data
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# =============================================================================
# CONSTANTS - These values are behavior-locked and MUST NOT be changed
# =============================================================================

# Leading silence threshold: only generate silence if first_start > this value
LEADING_SILENCE_THRESHOLD = 0.01

# Slot skip threshold: skip segments with slot_duration < this value
SLOT_SKIP_THRESHOLD = 1e-3

# Merge tolerance: merge adjacent segments if differences < this value
MERGE_TOLERANCE = 1e-3


# =============================================================================
# DOMAIN ENTITIES
# =============================================================================


@dataclass
class SubtitleSegment:
    """
    Single subtitle entry with timing in seconds.

    The `index` field is critical for stable sorting - legacy code sorts by
    (start, index) to maintain deterministic ordering when start times are equal.
    """

    index: int  # Zero-based index (stable ordering key)
    start: float  # Start time in seconds
    end: float  # End time in seconds
    text: str  # Subtitle text

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return max(0.0, self.end - self.start)


@dataclass
class SyncSegment:
    """
    A segment in the sync timeline for playback-side A/V sync.

    Maps audio timeline (dst_*) to video timeline (src_*).
    Formula: video_time = src_start + (audio_time - dst_start) * speed

    The frontend player uses this mapping to adjust video playback speed
    in real-time to match the voiceover audio.
    """

    dst_start: float  # Audio timeline start (seconds)
    dst_end: float  # Audio timeline end (seconds)
    src_start: float  # Video timeline start (seconds)
    src_end: float  # Video timeline end (seconds)
    speed: float  # = (src_end - src_start) / (dst_end - dst_start)

    def to_dict(self) -> dict[str, float]:
        """
        Convert to dict for JSON serialization.

        IMPORTANT: The round(x, 3) is behavior-locked - it affects frontend
        playback synchronization precision. Do not change the precision.
        """
        return {
            "dst_start": round(self.dst_start, 3),
            "dst_end": round(self.dst_end, 3),
            "src_start": round(self.src_start, 3),
            "src_end": round(self.src_end, 3),
            "speed": round(self.speed, 3),
        }


# =============================================================================
# PURE FUNCTIONS
# =============================================================================

# Pre-compiled SRT timestamp pattern
_SRT_TIME_PATTERN = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*" r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def parse_srt_text(content: str) -> list[SubtitleSegment]:
    """
    Parse SRT content into SubtitleSegment list.

    This is a pure function - it only transforms text to data structures.
    The caller is responsible for reading the file.

    Args:
        content: Raw SRT file content

    Returns:
        List of SubtitleSegment with index, timing, and text
    """
    blocks = re.split(r"\n\s*\n", content.strip())
    segments: list[SubtitleSegment] = []

    for raw_index, block in enumerate(blocks):
        lines = [line.strip("\ufeff") for line in block.strip().split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        # Parse index (fallback to raw_index if invalid)
        try:
            index_line = int(lines[0].strip())
        except ValueError:
            index_line = raw_index

        # Parse timestamp
        time_line = lines[1].strip()
        m = _SRT_TIME_PATTERN.search(time_line)
        if not m:
            continue

        start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0
        end = int(m.group(5)) * 3600 + int(m.group(6)) * 60 + int(m.group(7)) + int(m.group(8)) / 1000.0

        # Parse text (remaining lines)
        text_lines = lines[2:]
        text = " ".join(t.strip() for t in text_lines).strip()
        if not text:
            continue

        segments.append(SubtitleSegment(index=index_line, start=start, end=end, text=text))

    return segments


def merge_sync_segments(
    segments: list[SyncSegment],
    tolerance: float = MERGE_TOLERANCE,
) -> list[SyncSegment]:
    """
    Merge adjacent segments with same speed.

    Merging reduces timeline JSON size and improves playback efficiency.
    Two segments are merged if:
    - Speed difference < tolerance
    - dst timeline is contiguous (within tolerance)
    - src timeline is contiguous (within tolerance)

    Args:
        segments: List of sync segments to merge
        tolerance: Threshold for considering values equal (default: 1e-3)

    Returns:
        Merged list of sync segments
    """
    if not segments:
        return []

    merged: list[SyncSegment] = []

    for seg in segments:
        if merged:
            last = merged[-1]
            same_speed = abs(seg.speed - last.speed) < tolerance
            contiguous_dst = abs(seg.dst_start - last.dst_end) < tolerance
            contiguous_src = abs(seg.src_start - last.src_end) < tolerance

            if same_speed and contiguous_dst and contiguous_src:
                # Merge: extend the last segment
                merged[-1] = SyncSegment(
                    dst_start=last.dst_start,
                    dst_end=seg.dst_end,
                    src_start=last.src_start,
                    src_end=seg.src_end,
                    speed=last.speed,
                )
                continue

        merged.append(seg)

    return merged


def calculate_slot_end(
    segment: SubtitleSegment,
    next_segment: SubtitleSegment | None,
) -> float:
    """
    Calculate the slot end time for a subtitle segment.

    The slot extends from segment.start to:
    - next_segment.start if there's a gap between segment.end and next start
    - segment.end otherwise

    This matches the legacy algorithm for determining how much time
    each subtitle "owns" for audio alignment.

    Args:
        segment: Current subtitle segment
        next_segment: Next subtitle segment (or None if last)

    Returns:
        Slot end time in seconds
    """
    slot_end = segment.end
    if next_segment is not None and segment.end < next_segment.start:
        slot_end = next_segment.start
    return slot_end
