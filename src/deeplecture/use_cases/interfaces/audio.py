"""Audio processing protocol."""

from __future__ import annotations

from typing import Protocol


class AudioProcessorProtocol(Protocol):
    """Protocol for audio file processing."""

    def extract_audio(
        self,
        video_path: str,
        output_path: str,
        *,
        sample_rate: int = 16000,
        mono: bool = True,
    ) -> str:
        """Extract audio from video file.

        Args:
            video_path: Path to video file.
            output_path: Output audio file path.
            sample_rate: Target sample rate in Hz.
            mono: Whether to convert to mono.

        Returns:
            Path to extracted audio file.
        """
        ...

    def get_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds.

        Args:
            audio_path: Path to audio file.

        Returns:
            Duration in seconds.
        """
        ...

    def normalize(
        self,
        input_path: str,
        output_path: str,
        *,
        target_db: float = -20.0,
    ) -> str:
        """Normalize audio volume.

        Args:
            input_path: Input audio path.
            output_path: Output audio path.
            target_db: Target volume in dB.

        Returns:
            Path to normalized audio.
        """
        ...
