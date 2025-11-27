from __future__ import annotations

import dataclasses
import json
import logging
import os
import subprocess
from fractions import Fraction
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class VideoProbe:
    """Probed video stream properties."""

    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool
    pix_fmt: str = "yuv420p"
    sample_rate: int = 48000
    video_codec: str = "h264"
    audio_codec: str = "aac"


def probe_video(path: str) -> VideoProbe:
    """Probe video file properties using ffprobe (single call for all info)."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=width,height,avg_frame_rate,pix_fmt,codec_type,codec_name,sample_rate",
        "-of",
        "json",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    # Get duration from format
    format_info = data.get("format", {})
    duration = float(format_info.get("duration", 0))

    # Parse streams
    streams = data.get("streams", [])
    video_stream = None
    audio_stream = None
    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        elif codec_type == "audio" and audio_stream is None:
            audio_stream = stream

    if not video_stream:
        raise ValueError(f"No video stream found in {path}")

    width = int(video_stream.get("width", 1920))
    height = int(video_stream.get("height", 1080))
    pix_fmt = video_stream.get("pix_fmt", "yuv420p")
    video_codec = video_stream.get("codec_name", "h264")

    fps_str = video_stream.get("avg_frame_rate", "30/1")
    try:
        fps = float(Fraction(fps_str))
    except (ValueError, ZeroDivisionError):
        fps = 30.0

    has_audio = audio_stream is not None
    sample_rate = int(audio_stream.get("sample_rate", 48000)) if has_audio else 48000
    audio_codec = audio_stream.get("codec_name", "aac") if has_audio else "aac"

    return VideoProbe(
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


def check_videos_compatible(probes: List[VideoProbe]) -> bool:
    """
    Check if all videos have compatible formats for stream copy (no re-encoding).

    Returns True if all videos have matching:
    - Resolution (width, height)
    - Frame rate (within 0.1 fps tolerance)
    - Video codec
    - Pixel format
    - Audio presence (all have audio or all don't)
    - Audio codec and sample rate (if audio present)
    """
    if len(probes) < 2:
        return True

    ref = probes[0]
    for probe in probes[1:]:
        # Check video properties
        if probe.width != ref.width or probe.height != ref.height:
            return False
        if abs(probe.fps - ref.fps) > 0.1:
            return False
        if probe.video_codec != ref.video_codec:
            return False
        if probe.pix_fmt != ref.pix_fmt:
            return False

        # Check audio consistency
        if probe.has_audio != ref.has_audio:
            return False
        if ref.has_audio:
            if probe.audio_codec != ref.audio_codec:
                return False
            if probe.sample_rate != ref.sample_rate:
                return False

    return True


def probe_videos_compatibility(input_paths: List[str]) -> Dict:
    """
    Probe multiple videos and determine if they're compatible for fast merge.

    Returns a dict with:
    - compatible: bool - True if videos can be merged without re-encoding
    - probes: List[VideoProbe] - Probed info for each video
    - reason: str | None - Why videos are incompatible (if applicable)
    """
    if not input_paths:
        return {"compatible": False, "probes": [], "reason": "No input files"}

    probes: List[VideoProbe] = []
    for path in input_paths:
        if not os.path.exists(path):
            return {"compatible": False, "probes": [], "reason": f"File not found: {path}"}
        try:
            probes.append(probe_video(path))
        except Exception as exc:
            logger.warning("Failed to probe %s: %s", path, exc)
            return {"compatible": False, "probes": [], "reason": f"Failed to probe: {path}"}

    if len(probes) < 2:
        return {"compatible": True, "probes": probes, "reason": None}

    ref = probes[0]
    for i, probe in enumerate(probes[1:], start=1):
        if probe.width != ref.width or probe.height != ref.height:
            return {
                "compatible": False,
                "probes": probes,
                "reason": f"Resolution mismatch: {ref.width}x{ref.height} vs {probe.width}x{probe.height}",
            }
        if abs(probe.fps - ref.fps) > 0.1:
            return {
                "compatible": False,
                "probes": probes,
                "reason": f"Frame rate mismatch: {ref.fps:.2f} vs {probe.fps:.2f}",
            }
        if probe.video_codec != ref.video_codec:
            return {
                "compatible": False,
                "probes": probes,
                "reason": f"Video codec mismatch: {ref.video_codec} vs {probe.video_codec}",
            }
        if probe.pix_fmt != ref.pix_fmt:
            return {
                "compatible": False,
                "probes": probes,
                "reason": f"Pixel format mismatch: {ref.pix_fmt} vs {probe.pix_fmt}",
            }
        if probe.has_audio != ref.has_audio:
            return {
                "compatible": False,
                "probes": probes,
                "reason": "Audio track presence mismatch",
            }
        if ref.has_audio and probe.audio_codec != ref.audio_codec:
            return {
                "compatible": False,
                "probes": probes,
                "reason": f"Audio codec mismatch: {ref.audio_codec} vs {probe.audio_codec}",
            }
        if ref.has_audio and probe.sample_rate != ref.sample_rate:
            return {
                "compatible": False,
                "probes": probes,
                "reason": f"Sample rate mismatch: {ref.sample_rate} vs {probe.sample_rate}",
            }

    return {"compatible": True, "probes": probes, "reason": None}


def _merge_videos_fast(input_paths: List[str], output_path: str) -> None:
    """
    Fast merge using concat demuxer with stream copy (no re-encoding).

    Only works when all videos have identical formats.
    """
    import tempfile

    # Create concat list file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for path in input_paths:
            # Escape single quotes in path
            escaped_path = path.replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
        list_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info("Fast merging %d videos (stream copy): %s", len(input_paths), " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,  # 10 min should be enough for stream copy
        )
        logger.debug("FFmpeg stdout: %s", result.stdout)
    except subprocess.CalledProcessError as exc:
        logger.error("FFmpeg fast merge failed: %s\nstderr: %s", exc, exc.stderr)
        raise RuntimeError(f"Video fast merge failed: {exc.stderr}") from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("FFmpeg fast merge timed out")
        raise RuntimeError("Video fast merge timed out") from exc
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def merge_videos(input_paths: List[str], output_path: str, force_reencode: bool = False) -> None:
    """
    Merge multiple videos, automatically choosing the fastest method.

    If all videos have identical formats and force_reencode is False,
    uses stream copy (instant). Otherwise, re-encodes to normalize formats.

    Args:
        input_paths: List of video file paths to merge
        output_path: Output file path
        force_reencode: If True, always re-encode even if formats match
    """
    if not input_paths:
        raise ValueError("No input paths provided")

    for path in input_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Video file not found: {path}")

    # Probe all inputs
    probes: List[VideoProbe] = []
    probe_failed = False
    for path in input_paths:
        try:
            probes.append(probe_video(path))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to probe %s: %s, using defaults", path, exc)
            probe_failed = True
            probes.append(
                VideoProbe(
                    width=1920,
                    height=1080,
                    fps=30.0,
                    duration=10.0,
                    has_audio=False,
                ),
            )

    # Try fast merge if formats are compatible
    if not force_reencode and not probe_failed and check_videos_compatible(probes):
        logger.info("All %d videos have compatible formats, using fast stream copy", len(input_paths))
        _merge_videos_fast(input_paths, output_path)
        return

    logger.info("Videos require re-encoding for merge (format differences detected)")

    # Determine target format (highest resolution, common framerate)
    max_width = max(probe.width for probe in probes)
    max_height = max(probe.height for probe in probes)
    # Ensure even dimensions for H.264
    target_w = (max_width + 1) // 2 * 2
    target_h = (max_height + 1) // 2 * 2

    # Use mode framerate or default to 30fps
    fps_counts: Dict[float, int] = {}
    for probe in probes:
        rounded = round(probe.fps)
        fps_counts[rounded] = fps_counts.get(rounded, 0) + 1
    target_fps = max(fps_counts, key=fps_counts.get) if fps_counts else 30

    # Check if any input has audio
    any_has_audio = any(probe.has_audio for probe in probes)

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y"]
    for path in input_paths:
        cmd.extend(["-i", path])

    # Build filter_complex
    input_count = len(input_paths)
    filter_parts: List[str] = []

    for index, probe in enumerate(probes):
        # Video filter: scale, pad, fps, format, setsar
        vf = (
            f"[{index}:v]"
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"fps={target_fps},"
            f"format=yuv420p,"
            f"setsar=1"
            f"[v{index}]"
        )
        filter_parts.append(vf)

        # Audio filter: resample or generate silence with duration limit
        if any_has_audio:
            if probe.has_audio:
                # Trim audio to video duration and normalize format
                af = (
                    f"[{index}:a]"
                    f"atrim=end={probe.duration:.6f},"
                    f"asetpts=PTS-STARTPTS,"
                    f"aresample=48000,"
                    f"aformat=sample_fmts=fltp:channel_layouts=stereo"
                    f"[a{index}]"
                )
            else:
                # Generate silence matching the video duration (must include duration)
                af = (
                    f"anullsrc=channel_layout=stereo:sample_rate=48000:d={probe.duration:.6f},"
                    f"asetpts=PTS-STARTPTS"
                    f"[a{index}]"
                )
            filter_parts.append(af)

    # Concat all streams
    concat_inputs = "".join(
        f"[v{index}][a{index}]" if any_has_audio else f"[v{index}]"
        for index in range(input_count)
    )
    if any_has_audio:
        concat_filter = f"{concat_inputs}concat=n={input_count}:v=1:a=1[outv][outa]"
    else:
        concat_filter = f"{concat_inputs}concat=n={input_count}:v=1:a=0[outv]"
    filter_parts.append(concat_filter)

    filter_complex = ";".join(filter_parts)
    cmd.extend(["-filter_complex", filter_complex])

    # Map outputs
    cmd.extend(["-map", "[outv]"])
    if any_has_audio:
        cmd.extend(["-map", "[outa]"])

    # Encoding settings
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
        ],
    )
    if any_has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
    cmd.extend(["-movflags", "+faststart", output_path])

    logger.info("Merging %d videos: %s", input_count, " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=3600,
        )
        logger.debug("FFmpeg stdout: %s", result.stdout)
    except subprocess.CalledProcessError as exc:
        logger.error("FFmpeg merge failed: %s\nstderr: %s", exc, exc.stderr)
        raise RuntimeError(f"Video merge failed: {exc.stderr}") from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("FFmpeg merge timed out after 1 hour")
        raise RuntimeError("Video merge timed out") from exc


def merge_pdfs(input_paths: List[str], output_path: str) -> None:
    import pypdfium2 as pdfium

    documents = []
    try:
        for path in input_paths:
            if not os.path.exists(path):
                raise FileNotFoundError(f"PDF file not found: {path}")
            documents.append(pdfium.PdfDocument(path))

        out_doc = pdfium.PdfDocument.new()
        try:
            for doc in documents:
                out_doc.import_pages(doc)
            out_doc.save(output_path)
        finally:
            out_doc.close()
    finally:
        for doc in documents:
            doc.close()
