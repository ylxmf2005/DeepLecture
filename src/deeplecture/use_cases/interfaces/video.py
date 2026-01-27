"""Video processing protocol."""

from __future__ import annotations

from typing import Protocol


class VideoProcessorProtocol(Protocol):
    """Protocol for video processing operations."""

    def get_duration(self, video_path: str) -> float:
        """Get video duration in seconds.

        Args:
            video_path: Path to video file.

        Returns:
            Duration in seconds.
        """
        ...

    def get_resolution(self, video_path: str) -> tuple[int, int]:
        """Get video resolution.

        Args:
            video_path: Path to video file.

        Returns:
            Tuple of (width, height).
        """
        ...

    def extract_frame(
        self,
        video_path: str,
        timestamp: float,
        output_path: str,
    ) -> str:
        """Extract a frame from video.

        Args:
            video_path: Path to video file.
            timestamp: Timestamp in seconds.
            output_path: Output image path.

        Returns:
            Path to extracted frame.
        """
        ...

    def trim(
        self,
        video_path: str,
        output_path: str,
        *,
        start: float | None = None,
        end: float | None = None,
    ) -> str:
        """Trim video to time range.

        Args:
            video_path: Path to video file.
            output_path: Output file path.
            start: Start timestamp in seconds.
            end: End timestamp in seconds.

        Returns:
            Path to trimmed video.
        """
        ...

    def add_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        *,
        replace: bool = True,
    ) -> str:
        """Add or replace audio track.

        Args:
            video_path: Path to video file.
            audio_path: Path to audio file.
            output_path: Output file path.
            replace: Whether to replace existing audio.

        Returns:
            Path to output video.
        """
        ...
