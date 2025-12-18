"""
FFmpeg Audio Processor - Implementation of AudioProcessorProtocol.

This is an Interface Adapter (Clean Architecture Layer 3) that:
- Wraps ffmpeg/ffprobe command-line tools
- Provides reliable audio I/O primitives for UseCase
- Handles all subprocess details and error reporting

Design Decisions:
- All methods are synchronous (matches legacy behavior)
- Exceptions include stderr for debugging
- Uses absolute paths to avoid cwd issues
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import AudioProcessorProtocol

logger = logging.getLogger(__name__)


def _validate_concat_path(path: str) -> None:
    """Reject paths containing newlines to prevent concat list injection."""
    if "\n" in path or "\r" in path:
        raise ValueError(f"Invalid path (contains newline): {path!r}")


class FFmpegAudioProcessor:
    """
    FFmpeg/ffprobe implementation of AudioProcessorProtocol.

    This class contains NO business logic - it only executes I/O operations.
    """

    def __init__(
        self,
        *,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ) -> None:
        """
        Initialize FFmpegAudioProcessor.

        Args:
            ffmpeg_path: Path to ffmpeg executable
            ffprobe_path: Path to ffprobe executable
        """
        self._ffmpeg = ffmpeg_path
        self._ffprobe = ffprobe_path

    def probe_duration_seconds(self, path: str) -> float:
        """
        Get media duration in seconds using ffprobe.

        Args:
            path: Path to media file

        Returns:
            Duration in seconds

        Raises:
            RuntimeError: If ffprobe fails or returns invalid data
        """
        cmd = [
            self._ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            return float(result.stdout.strip())
        except subprocess.TimeoutExpired as e:
            logger.error("ffprobe timed out for %s", path)
            raise RuntimeError(f"Probe timed out for {path}") from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            logger.error("ffprobe failed for %s: %s", path, stderr)
            raise RuntimeError(f"Failed to probe duration for {path}: {stderr}") from e
        except ValueError as e:
            logger.error("Invalid duration value for %s: %s", path, e)
            raise RuntimeError(f"Invalid duration value for {path}") from e

    def transcode_to_wav(
        self,
        input_path: str,
        output_path: str,
        *,
        sample_rate: int,
        channels: int = 1,
    ) -> None:
        """
        Transcode media to 16-bit PCM WAV.

        Args:
            input_path: Source media file
            output_path: Destination WAV file
            sample_rate: Output sample rate (e.g., 44100)
            channels: Number of channels (default: 1 for mono)

        Raises:
            RuntimeError: If transcoding fails
        """
        cmd = [
            self._ffmpeg,
            "-y",
            "-i",
            input_path,
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            os.path.abspath(output_path),
        ]
        self._run_ffmpeg(cmd, f"transcode {input_path}")

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
        if duration <= 0:
            # Nothing to generate
            return

        channel_layout = "mono" if channels == 1 else "stereo"
        cmd = [
            self._ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout={channel_layout}:sample_rate={sample_rate}",
            "-t",
            f"{duration:.3f}",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            os.path.abspath(output_path),
        ]
        self._run_ffmpeg(cmd, f"generate silence {output_path}")

    def concat_wavs_to_wav(self, input_paths: list[str], output_path: str) -> None:
        """
        Concatenate WAV files to a single WAV output.

        Uses FFmpeg's concat demuxer with a temporary file list.
        Output preserves PCM format from input files.

        Args:
            input_paths: List of WAV files to concatenate (in order)
            output_path: Destination WAV file

        Raises:
            ValueError: If input_paths is empty
            RuntimeError: If concatenation fails
        """
        if not input_paths:
            raise ValueError("No audio files to concatenate")

        work_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(work_dir, exist_ok=True)

        list_file: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                dir=work_dir,
                delete=False,
                encoding="utf-8",
            ) as f:
                list_file = f.name
                for path in input_paths:
                    _validate_concat_path(path)
                    abs_path = os.path.abspath(path)
                    _validate_concat_path(abs_path)
                    escaped = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            cmd = [
                self._ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-c:a",
                "copy",
                os.path.abspath(output_path),
            ]
            self._run_ffmpeg(cmd, "concat to wav")
        finally:
            if list_file:
                with contextlib.suppress(OSError):
                    os.remove(list_file)

    def concat_wavs_to_m4a(
        self,
        input_paths: list[str],
        output_path: str,
        *,
        bitrate: str = "192k",
    ) -> None:
        """
        Concatenate WAV files and output as M4A (AAC).

        Uses FFmpeg's concat demuxer with a temporary file list.

        Args:
            input_paths: List of WAV files to concatenate (in order)
            output_path: Destination M4A file
            bitrate: Audio bitrate (default: 192k)

        Raises:
            ValueError: If input_paths is empty
            RuntimeError: If concatenation fails
        """
        if not input_paths:
            raise ValueError("No audio files to concatenate")

        work_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(work_dir, exist_ok=True)

        list_file: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                dir=work_dir,
                delete=False,
                encoding="utf-8",
            ) as f:
                list_file = f.name
                for path in input_paths:
                    _validate_concat_path(path)
                    abs_path = os.path.abspath(path)
                    _validate_concat_path(abs_path)
                    escaped = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            cmd = [
                self._ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-c:a",
                "aac",
                "-b:a",
                bitrate,
                os.path.abspath(output_path),
            ]
            self._run_ffmpeg(cmd, "concat to m4a")
        finally:
            if list_file:
                with contextlib.suppress(OSError):
                    os.remove(list_file)

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _run_ffmpeg(
        self,
        cmd: list[str],
        operation: str,
        *,
        cwd: str | None = None,
        timeout: float = 600,
    ) -> None:
        """
        Run FFmpeg command with error handling.

        Args:
            cmd: Command line arguments
            operation: Description for error messages
            cwd: Working directory (optional)
            timeout: Maximum execution time in seconds (default: 600)

        Raises:
            RuntimeError: If FFmpeg fails or times out
        """
        try:
            subprocess.run(cmd, cwd=cwd, capture_output=True, check=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            logger.error("FFmpeg timed out for %s after %.0fs", operation, timeout)
            raise RuntimeError(f"FFmpeg {operation} timed out after {timeout}s") from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else str(e)
            logger.error("FFmpeg failed for %s: %s", operation, stderr)
            raise RuntimeError(f"FFmpeg {operation} failed: {stderr}") from e


# Type assertion for Protocol compliance
def _check_protocol_compliance() -> None:
    """Verify FFmpegAudioProcessor implements AudioProcessorProtocol."""
    from deeplecture.use_cases.interfaces import AudioProcessorProtocol

    processor: AudioProcessorProtocol = FFmpegAudioProcessor()
    assert isinstance(processor, AudioProcessorProtocol)
