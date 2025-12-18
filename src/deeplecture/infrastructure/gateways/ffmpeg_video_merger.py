"""FFmpeg-based implementation of VideoMergerProtocol."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from deeplecture.domain.errors import VideoMergeError

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
# Control chars and newlines that could inject into concat list
_DANGEROUS_PATH_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_video_path(
    path: str,
    *,
    must_exist: bool,
    allowed_roots: tuple[Path, ...],
) -> Path:
    # Check for control chars/newlines that could inject into concat list
    if _DANGEROUS_PATH_CHARS.search(path):
        raise VideoMergeError("Path contains invalid control characters")
    resolved = Path(path).expanduser().resolve(strict=False)
    if resolved.suffix.lower() not in ALLOWED_VIDEO_EXT:
        raise VideoMergeError(f"Invalid video extension: {resolved.suffix}")
    if must_exist and not resolved.exists():
        raise VideoMergeError(f"Video not found: {resolved}")
    if allowed_roots and not any(_is_under(resolved, root) for root in allowed_roots):
        raise VideoMergeError("Path outside allowed directories")
    return resolved


@dataclass(frozen=True, slots=True)
class _VideoProbe:
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool
    pix_fmt: str
    sample_rate: int
    video_codec: str
    audio_codec: str


class FFmpegVideoMerger:
    """
    Merge multiple videos using ffmpeg.

    Strategy:
    - If all inputs are format-compatible and force_reencode=False, do stream-copy concat.
    - Otherwise normalize via re-encoding and concat filter.
    """

    def __init__(
        self,
        *,
        allowed_roots: set[str] | set[Path] | list[str] | list[Path] | tuple[str, ...],
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ) -> None:
        if not allowed_roots:
            raise ValueError("FFmpegVideoMerger requires non-empty allowed_roots")
        root_strs = sorted({str(Path(p).expanduser().resolve(strict=False)) for p in allowed_roots})
        self._allowed_roots = tuple(Path(p) for p in root_strs)
        self._ffmpeg = ffmpeg_path
        self._ffprobe = ffprobe_path

    def merge_videos(self, input_paths: list[str], output_path: str, force_reencode: bool = False) -> None:
        if not input_paths:
            raise VideoMergeError("No input videos provided")

        inputs = [_validate_video_path(p, must_exist=True, allowed_roots=self._allowed_roots) for p in input_paths]
        out = _validate_video_path(output_path, must_exist=False, allowed_roots=self._allowed_roots)
        out.parent.mkdir(parents=True, exist_ok=True)

        probes = [self._probe_video(str(p)) for p in inputs]
        compatible = self._check_compatible(probes)

        try:
            if compatible and not force_reencode:
                self._merge_fast(inputs, out)
                return
            self._merge_reencode(inputs, out, probes)
        except FileNotFoundError as exc:
            raise VideoMergeError(f"ffmpeg/ffprobe not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise VideoMergeError("FFmpeg merge timed out") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (
                exc.stderr.decode("utf-8", errors="replace")
                if isinstance(exc.stderr, bytes | bytearray)
                else (exc.stderr or "")
            )
            raise VideoMergeError(stderr.strip() or str(exc), len(inputs)) from exc
        except VideoMergeError:
            raise
        except Exception as exc:
            raise VideoMergeError(str(exc), len(inputs)) from exc

    def _probe_video(self, path: str) -> _VideoProbe:
        cmd = [
            self._ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=width,height,avg_frame_rate,pix_fmt,codec_type,codec_name,sample_rate",
            "-of",
            "json",
            path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        except subprocess.TimeoutExpired as exc:
            raise VideoMergeError(f"Probe timed out for {path}") from exc
        data = json.loads(result.stdout)

        duration = float((data.get("format") or {}).get("duration") or 0)
        streams = data.get("streams") or []

        video_stream = None
        audio_stream = None
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream

        if not video_stream:
            raise VideoMergeError(f"No video stream found in {path}")

        width = int(video_stream.get("width") or 1920)
        height = int(video_stream.get("height") or 1080)
        pix_fmt = str(video_stream.get("pix_fmt") or "yuv420p")
        video_codec = str(video_stream.get("codec_name") or "h264")

        fps_str = str(video_stream.get("avg_frame_rate") or "30/1")
        try:
            fps = float(Fraction(fps_str))
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        has_audio = audio_stream is not None
        sample_rate = int(audio_stream.get("sample_rate") or 48000) if has_audio else 48000
        audio_codec = str(audio_stream.get("codec_name") or "aac") if has_audio else "aac"

        return _VideoProbe(
            width=width,
            height=height,
            fps=fps,
            duration=duration,
            has_audio=has_audio,
            pix_fmt=pix_fmt,
            sample_rate=sample_rate,
            video_codec=video_codec,
            audio_codec=audio_codec,
        )

    @staticmethod
    def _check_compatible(probes: list[_VideoProbe]) -> bool:
        if len(probes) < 2:
            return True
        ref = probes[0]
        for p in probes[1:]:
            if p.width != ref.width or p.height != ref.height:
                return False
            if abs(p.fps - ref.fps) > 0.1:
                return False
            if p.video_codec != ref.video_codec:
                return False
            if p.pix_fmt != ref.pix_fmt:
                return False
            if p.has_audio != ref.has_audio:
                return False
            if ref.has_audio:
                if p.audio_codec != ref.audio_codec:
                    return False
                if p.sample_rate != ref.sample_rate:
                    return False
        return True

    def _merge_fast(self, inputs: list[Path], output: Path) -> None:
        list_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                list_file = f.name
                for p in inputs:
                    # FFmpeg concat list escaping: backslash then single quote
                    escaped = str(p).replace("\\", "\\\\").replace("'", "'\\''")
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
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            ]
            logger.info("FFmpeg fast merge %d videos -> %s", len(inputs), output)
            subprocess.run(cmd, capture_output=True, check=True, timeout=600)
        finally:
            if list_file:
                with contextlib.suppress(OSError):
                    os.remove(list_file)

    def _merge_reencode(self, inputs: list[Path], output: Path, probes: list[_VideoProbe]) -> None:
        max_width = max(p.width for p in probes)
        max_height = max(p.height for p in probes)
        target_w = (max_width + 1) // 2 * 2
        target_h = (max_height + 1) // 2 * 2

        fps_counts: dict[int, int] = {}
        for p in probes:
            rounded = round(p.fps)
            fps_counts[rounded] = fps_counts.get(rounded, 0) + 1
        target_fps = max(fps_counts, key=lambda k: fps_counts[k]) if fps_counts else 30

        any_has_audio = any(p.has_audio for p in probes)

        cmd: list[str] = [self._ffmpeg, "-y"]
        for p in inputs:
            cmd.extend(["-i", str(p)])

        filter_parts: list[str] = []
        for idx, pr in enumerate(probes):
            vf = (
                f"[{idx}:v]"
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fps={target_fps},format=yuv420p,setsar=1"
                f"[v{idx}]"
            )
            filter_parts.append(vf)

            if any_has_audio:
                if pr.has_audio:
                    af = (
                        f"[{idx}:a]"
                        f"atrim=end={pr.duration:.6f},asetpts=PTS-STARTPTS,"
                        f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
                        f"[a{idx}]"
                    )
                else:
                    af = (
                        f"anullsrc=channel_layout=stereo:sample_rate=48000:d={pr.duration:.6f},"
                        f"asetpts=PTS-STARTPTS[a{idx}]"
                    )
                filter_parts.append(af)

        concat_inputs = "".join(f"[v{idx}][a{idx}]" if any_has_audio else f"[v{idx}]" for idx in range(len(inputs)))
        if any_has_audio:
            filter_parts.append(f"{concat_inputs}concat=n={len(inputs)}:v=1:a=1[outv][outa]")
        else:
            filter_parts.append(f"{concat_inputs}concat=n={len(inputs)}:v=1:a=0[outv]")

        cmd.extend(["-filter_complex", ";".join(filter_parts)])
        cmd.extend(["-map", "[outv]"])
        if any_has_audio:
            cmd.extend(["-map", "[outa]"])

        cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"])
        if any_has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        cmd.extend(["-movflags", "+faststart", str(output)])

        logger.info("FFmpeg reencode merge %d videos -> %s", len(inputs), output)
        subprocess.run(cmd, capture_output=True, check=True, timeout=3600)
