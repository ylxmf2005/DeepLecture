"""Time utilities shared across layers (domain/use_cases/infrastructure)."""

from __future__ import annotations

from datetime import datetime, timezone

# Python 3.11+ provides datetime.UTC, older versions do not.
UTC = getattr(datetime, "UTC", timezone.utc)


def format_srt_time(seconds: float) -> str:
    """Format seconds to SRT time: HH:MM:SS,mmm."""
    if seconds < 0:
        raise ValueError("seconds must be >= 0")

    total_ms = int(seconds * 1000)
    hours, remainder = divmod(total_ms, 3600 * 1000)
    minutes, remainder = divmod(remainder, 60 * 1000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
