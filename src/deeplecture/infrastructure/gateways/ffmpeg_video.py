from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_media_path(
    path: str,
    allowed_extensions: set[str],
    *,
    must_exist: bool,
    allowed_roots: tuple[Path, ...],
) -> Path:
    resolved = Path(path).expanduser().resolve(strict=False)
    if resolved.suffix.lower() not in allowed_extensions:
        raise ValueError(f"Invalid file extension: {resolved.suffix}")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")
    if allowed_roots and not any(_is_under(resolved, root) for root in allowed_roots):
        raise ValueError("Path outside allowed directories")
    return resolved


class FFmpegVideoProcessor:
    def __init__(
        self,
        *,
        allowed_roots: set[str] | set[Path] | list[str] | list[Path] | tuple[str, ...],
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ) -> None:
        if not allowed_roots:
            raise ValueError("FFmpegVideoProcessor requires non-empty allowed_roots")
        root_strs = sorted({str(Path(p).expanduser().resolve(strict=False)) for p in allowed_roots})
        self._allowed_roots = tuple(Path(p) for p in root_strs)
        self._ffmpeg = ffmpeg_path
        self._ffprobe = ffprobe_path

    def build_still_segment(self, image_path: str, duration: float, output_path: str) -> None:
        if duration <= 0:
            raise ValueError("duration must be positive")
        img_path = _validate_media_path(
            image_path,
            ALLOWED_IMAGE_EXT,
            must_exist=True,
            allowed_roots=self._allowed_roots,
        )
        out_path = _validate_media_path(
            output_path,
            ALLOWED_VIDEO_EXT,
            must_exist=False,
            allowed_roots=self._allowed_roots,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(img_path),
            "-t",
            f"{duration:.6f}",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out_path),
        ]
        self._run(cmd, f"build_still_segment {img_path}")

    def concat_segments(self, segment_paths: list[str], output_path: str) -> None:
        if not segment_paths:
            raise ValueError("No segments to concatenate")

        out_path = _validate_media_path(
            output_path,
            ALLOWED_VIDEO_EXT,
            must_exist=False,
            allowed_roots=self._allowed_roots,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        work_dir = out_path.parent

        list_file: str | None = None
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, dir=str(work_dir), encoding="utf-8") as f:
                list_file = f.name
                for seg in segment_paths:
                    seg_path = _validate_media_path(
                        seg,
                        ALLOWED_VIDEO_EXT,
                        must_exist=True,
                        allowed_roots=self._allowed_roots,
                    )
                    f.write(f"file '{self._escape(str(seg_path))}'\n")

            cmd = [
                self._ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-c:v",
                "copy",
                "-an",
                str(out_path),
            ]
            self._run(cmd, f"concat_segments -> {out_path}")
        finally:
            if list_file:
                with contextlib.suppress(OSError):
                    os.remove(list_file)

    def mux_audio(self, video_path: str, audio_path: str, output_path: str) -> None:
        v = _validate_media_path(
            video_path,
            ALLOWED_VIDEO_EXT,
            must_exist=True,
            allowed_roots=self._allowed_roots,
        )
        a = _validate_media_path(
            audio_path,
            ALLOWED_AUDIO_EXT,
            must_exist=True,
            allowed_roots=self._allowed_roots,
        )
        out_path = _validate_media_path(
            output_path,
            ALLOWED_VIDEO_EXT,
            must_exist=False,
            allowed_roots=self._allowed_roots,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._ffmpeg,
            "-y",
            "-i",
            str(v),
            "-i",
            str(a),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        self._run(cmd, f"mux_audio -> {out_path}")

    def probe_duration(self, path: str) -> float:
        p = _validate_media_path(
            path,
            ALLOWED_VIDEO_EXT | ALLOWED_AUDIO_EXT,
            must_exist=True,
            allowed_roots=self._allowed_roots,
        )
        cmd = [
            self._ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(p),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            return float(result.stdout.strip())
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Probe timed out for {path}") from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            raise RuntimeError(f"Failed to probe duration for {path}: {stderr}") from e
        except ValueError as e:
            raise RuntimeError(f"Invalid duration value for {path}") from e

    def extract_frame(self, video_path: str, timestamp: float, output_path: str) -> None:
        """Extract a single frame from video at timestamp."""
        v = _validate_media_path(
            video_path,
            ALLOWED_VIDEO_EXT,
            must_exist=True,
            allowed_roots=self._allowed_roots,
        )
        out_path = _validate_media_path(
            output_path,
            ALLOWED_IMAGE_EXT,
            must_exist=False,
            allowed_roots=self._allowed_roots,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._ffmpeg,
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(v),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]
        self._run(cmd, f"extract_frame at {timestamp}s", timeout=30)

    @staticmethod
    def _escape(path: str) -> str:
        return path.replace("'", "\\'")

    def _run(self, cmd: list[str], operation: str, *, timeout: float = 600) -> None:
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            logger.error("FFmpeg timed out for %s after %.0fs", operation, timeout)
            raise RuntimeError(f"FFmpeg {operation} timed out after {timeout}s") from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            logger.error("FFmpeg failed for %s: %s", operation, stderr)
            raise RuntimeError(f"FFmpeg {operation} failed: {stderr}") from e
