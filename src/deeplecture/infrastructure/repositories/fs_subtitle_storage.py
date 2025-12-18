"""File system implementation of SubtitleStorageProtocol."""

from __future__ import annotations

import json
import re
from pathlib import Path

from deeplecture.domain import Segment
from deeplecture.infrastructure.repositories.path_resolver import safe_join, validate_segment


class FsSubtitleStorage:
    """
    File system based subtitle storage.

    Implements SubtitleStorageProtocol.
    Stores subtitles as SRT files in content directories.
    """

    def __init__(self, content_dir: Path) -> None:
        self._content_dir = Path(content_dir).expanduser().resolve(strict=False)

    def save(self, content_id: str, segments: list[Segment], language: str) -> None:
        """Save segments as SRT file."""
        path = self._get_path(content_id, language)
        path.parent.mkdir(parents=True, exist_ok=True)

        srt_content = self._segments_to_srt(segments)
        path.write_text(srt_content, encoding="utf-8")

    def load(self, content_id: str, language: str) -> list[Segment] | None:
        """Load segments from SRT file."""
        path = self._get_path(content_id, language)

        if not path.exists():
            return None

        srt_content = path.read_text(encoding="utf-8")
        return self._parse_srt(srt_content)

    def exists(self, content_id: str, language: str) -> bool:
        """Check if subtitle file exists."""
        return self._get_path(content_id, language).exists()

    def delete(self, content_id: str, language: str) -> bool:
        """Delete subtitle file if it exists."""
        path = self._get_path(content_id, language)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_languages(self, content_id: str) -> list[str]:
        """
        List available language codes for a content item.

        Scans the content directory for files named subtitle_{language}.srt.
        """
        validate_segment(content_id, "content_id")
        content_path = safe_join(self._content_dir, content_id)
        if not content_path.is_dir():
            return []

        languages: set[str] = set()

        for path in content_path.glob("subtitle_*.srt"):
            name = path.name
            if not name.startswith("subtitle_") or not name.endswith(".srt"):
                continue
            language = name[len("subtitle_") : -len(".srt")]
            try:
                validate_segment(language, "language")
            except ValueError:
                continue
            languages.add(language)

        return sorted(languages)

    def save_background(self, content_id: str, data: dict) -> None:
        """Save background context as JSON."""
        validate_segment(content_id, "content_id")
        path = safe_join(self._content_dir, content_id, "background.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_path(self, content_id: str, language: str) -> Path:
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")
        return safe_join(self._content_dir, content_id, f"subtitle_{language}.srt")

    def _segments_to_srt(self, segments: list[Segment]) -> str:
        """Convert segments to SRT format."""
        blocks = []
        for i, seg in enumerate(segments, 1):
            start = self._format_time(seg.start)
            end = self._format_time(seg.end)
            blocks.append(f"{i}\n{start} --> {end}\n{seg.text}\n")
        return "\n".join(blocks)

    def _format_time(self, seconds: float) -> str:
        """Format seconds to SRT time: HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _parse_srt(self, content: str) -> list[Segment]:
        """Parse SRT content to segments."""
        segments = []
        pattern = re.compile(
            r"(\d+)\n" r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n" r"(.+?)(?=\n\n|\n*$)",
            re.DOTALL,
        )

        for match in pattern.finditer(content):
            start = self._parse_time(match.group(2))
            end = self._parse_time(match.group(3))
            text = match.group(4).strip()
            segments.append(Segment(start=start, end=end, text=text))

        return segments

    def _parse_time(self, time_str: str) -> float:
        """Parse SRT time string to seconds."""
        # Format: HH:MM:SS,mmm
        parts = time_str.replace(",", ":").split(":")
        hours, minutes, seconds, millis = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds + millis / 1000
