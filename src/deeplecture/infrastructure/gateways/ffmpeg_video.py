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
ALLOWED_SUBTITLE_EXT = {".srt"}


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

    def export_mp4(
        self,
        video_path: str,
        output_path: str,
        *,
        audio_path: str | None = None,
        subtitle_path: str | None = None,
    ) -> None:
        """
        Export an MP4 with optional audio replacement and optional hard subtitles.

        - If `subtitle_path` is provided, video must be re-encoded (subtitle burn-in).
        - If no subtitles are requested, we first try stream-copy for speed and
          fall back to re-encode for compatibility.
        """
        v = _validate_media_path(
            video_path,
            ALLOWED_VIDEO_EXT,
            must_exist=True,
            allowed_roots=self._allowed_roots,
        )
        out_path = _validate_media_path(
            output_path,
            {".mp4"},
            must_exist=False,
            allowed_roots=self._allowed_roots,
        )
        a = (
            _validate_media_path(
                audio_path,
                ALLOWED_AUDIO_EXT,
                must_exist=True,
                allowed_roots=self._allowed_roots,
            )
            if audio_path
            else None
        )
        s = (
            _validate_media_path(
                subtitle_path,
                ALLOWED_SUBTITLE_EXT,
                must_exist=True,
                allowed_roots=self._allowed_roots,
            )
            if subtitle_path
            else None
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if s is None:
            fast_cmd = self._build_export_command(v, out_path, audio=a, subtitle=None, reencode_video=False)
            try:
                self._run(fast_cmd, f"export_mp4(copy) -> {out_path}")
                return
            except RuntimeError as exc:
                logger.warning(
                    "Fast export failed, retrying with re-encode. output=%s error=%s",
                    out_path,
                    exc,
                )

        cmd = self._build_export_command(v, out_path, audio=a, subtitle=s, reencode_video=True)
        self._run(cmd, f"export_mp4(reencode) -> {out_path}")

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

    @staticmethod
    def _escape_subtitle_filter_path(path: str) -> str:
        """
        Escape path for ffmpeg subtitles= filter argument.

        This is filter-level escaping (not shell escaping).
        """
        return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")

    def _build_export_command(
        self,
        video: Path,
        output: Path,
        *,
        audio: Path | None,
        subtitle: Path | None,
        reencode_video: bool,
    ) -> list[str]:
        cmd = [
            self._ffmpeg,
            "-y",
            "-i",
            str(video),
        ]
        if audio is not None:
            cmd.extend(["-i", str(audio)])

        if subtitle is not None:
            subtitle_filter_arg = self._escape_subtitle_filter_path(str(subtitle))
            cmd.extend(["-vf", f"subtitles={subtitle_filter_arg}"])

        cmd.extend(["-map", "0:v:0"])
        if audio is not None:
            cmd.extend(["-map", "1:a:0"])
        else:
            cmd.extend(["-map", "0:a:0?"])

        if reencode_video or subtitle is not None:
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                ]
            )
        else:
            cmd.extend(["-c:v", "copy"])

        # Always normalize audio to AAC for mp4 compatibility.
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        cmd.extend(["-movflags", "+faststart", str(output)])
        return cmd

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
