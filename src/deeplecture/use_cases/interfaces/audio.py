"""Audio processing protocol - abstraction for audio I/O operations.

This protocol abstracts FFmpeg/ffprobe operations so that:
1. VoiceoverUseCase can be tested with a mock implementation
2. The audio backend can be swapped (ffmpeg → sox → cloud service)
3. Business logic (thresholds, retry, etc.) stays in UseCase, not here

Design Decisions:
- Methods are minimal but complete for voiceover needs
- All methods are synchronous (async can be added later if needed)
- Failures raise exceptions (UseCase decides retry/fallback policy)
- No business logic here - this is pure I/O capability
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioProcessorProtocol(Protocol):
    """
    Contract for audio processing capabilities.

    This is an Interface Adapter abstraction (Clean Architecture Layer 3).
    The UseCase depends on this protocol, not on FFmpeg directly.

    Implementations:
    - FFmpegAudioProcessor: Production implementation using ffmpeg/ffprobe
    - FakeAudioProcessor: Test implementation that records calls without I/O
    """

    def probe_duration_seconds(self, path: str) -> float:
        """
        Get audio/video duration in seconds.

        Args:
            path: Path to media file

        Returns:
            Duration in seconds

        Raises:
            RuntimeError: If ffprobe fails or file is invalid
        """
        ...

    def transcode_to_wav(
        self,
        input_path: str,
        output_path: str,
        *,
        sample_rate: int,
        channels: int = 1,
    ) -> None:
        """
        Transcode media to WAV format.

        Output is 16-bit PCM WAV suitable for audio processing.

        Args:
            input_path: Source media file
            output_path: Destination WAV file
            sample_rate: Output sample rate (e.g., 44100)
            channels: Number of channels (default: 1 for mono)

        Raises:
            RuntimeError: If transcoding fails
        """
        ...

    def generate_silence_wav(
        self,
        output_path: str,
        *,
        duration: float,
        sample_rate: int,
        channels: int = 1,
    ) -> None:
        """
        Generate a silent WAV file.

        Args:
            output_path: Destination WAV file
            duration: Silence duration in seconds
            sample_rate: Output sample rate
            channels: Number of channels (default: 1 for mono)

        Raises:
            RuntimeError: If generation fails
        """
        ...

    def concat_wavs_to_m4a(
        self,
        input_paths: list[str],
        output_path: str,
        *,
        bitrate: str = "192k",
    ) -> None:
        """
        Concatenate WAV files and output as M4A (AAC).

        Args:
            input_paths: List of WAV files to concatenate (in order)
            output_path: Destination M4A file
            bitrate: Audio bitrate (default: 192k)

        Raises:
            RuntimeError: If concatenation fails
            ValueError: If input_paths is empty
        """
        ...

    def concat_wavs_to_wav(self, input_paths: list[str], output_path: str) -> None:
        """Concatenate WAV files to WAV output (not M4A)."""
        ...
