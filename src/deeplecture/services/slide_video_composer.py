from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from deeplecture.app_context import get_app_context
from deeplecture.utils.fs import ensure_directory


logger = logging.getLogger(__name__)
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_media_path(path: str, allowed_extensions) -> Path:
    resolved = Path(path).resolve()
    if resolved.suffix.lower() not in allowed_extensions:
        raise ValueError(f"Invalid file extension: {resolved.suffix}")
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    ctx = get_app_context()
    ctx.init_paths()
    allowed_roots = {Path(ctx.content_dir).resolve(), Path(ctx.temp_dir).resolve()}
    if not any(_is_under(resolved, root) for root in allowed_roots):
        raise ValueError("Path outside allowed directories")
    return resolved


def _build_segment_task(args: Tuple[int, str, str, str, float]) -> Tuple[int, str]:
    """
    Build a single video segment (standalone for ProcessPoolExecutor).

    Args:
        args: (page_index, image_path, audio_path, output_path, duration)

    Returns:
        (page_index, output_path) on success
    """
    idx, img, wav, segment_path, dur = args
    img_path = _validate_media_path(img, ALLOWED_IMAGE_EXT)
    wav_path = _validate_media_path(wav, ALLOWED_AUDIO_EXT)

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-t", f"{dur:.6f}",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-an",
        os.path.abspath(segment_path),
    ]

    subprocess.run(cmd, capture_output=True, check=True, timeout=120)
    return (idx, segment_path)


class VideoComposer:
    """
    FFmpeg-based video composition for slide lectures.

    Given per-page images and audio tracks, this component builds one MP4
    segment per page and concatenates them into the final lecture video.
    """

    def compose_from_pages(
        self,
        *,
        deck_dir: str,
        page_images: Dict[int, str],
        page_audio_paths: Dict[int, str],
        output_video_path: str,
    ) -> None:
        """
        Build the final lecture video so that the audio timeline stays
        identical to the one used for subtitles.

        Steps:
        1. Concatenate all per-page wav tracks into a single lecture_audio.wav.
        2. For each page, build a video-only segment whose duration matches
           that page's wav duration (no audio track).
        3. Concat all video-only segments into a single video-only MP4.
        4. Mux the video-only MP4 with lecture_audio.wav into the final video.
        """
        video_segments_dir = ensure_directory(deck_dir, "video_segments")

        pages: List[int] = sorted(page_images.keys())
        paired_pages: List[int] = []
        safe_images: Dict[int, Path] = {}
        safe_audio: Dict[int, Path] = {}

        for idx in pages:
            img = page_images.get(idx)
            wav = page_audio_paths.get(idx)
            try:
                img_path = _validate_media_path(img, ALLOWED_IMAGE_EXT)
                wav_path = _validate_media_path(wav, ALLOWED_AUDIO_EXT)
            except (ValueError, FileNotFoundError) as exc:
                logger.warning(
                    "Skipping page %s due to invalid media path: %s",
                    idx,
                    exc,
                )
                continue
            safe_images[idx] = img_path
            safe_audio[idx] = wav_path
            paired_pages.append(idx)

        if not paired_pages:
            raise RuntimeError("No usable page image+audio pairs for slide lecture")

        audio_files: List[str] = []
        for idx in paired_pages:
            wav = safe_audio[idx]
            audio_files.append(str(wav))

        lecture_audio_path = os.path.join(video_segments_dir, "lecture_audio.wav")
        self._concat_audio_files(
            audio_files=audio_files,
            output_file=lecture_audio_path,
            work_dir=video_segments_dir,
        )

        # Prepare all segment build tasks
        segment_tasks: List[Tuple[int, str, str, str, float]] = []
        for idx in paired_pages:
            img_path = safe_images[idx]
            wav_path = safe_audio[idx]
            dur = self._get_audio_duration(str(wav_path))
            if dur <= 0:
                logger.warning(
                    "Non-positive duration for page %s audio (%s); skipping segment",
                    idx,
                    wav_path,
                )
                continue

            segment_name = f"page_{idx:03d}.mp4"
            segment_path = os.path.join(video_segments_dir, segment_name)
            segment_tasks.append((idx, str(img_path), str(wav_path), segment_path, dur))

        if not segment_tasks:
            raise RuntimeError("No valid segments to build for slide lecture")

        # Build segments in parallel (use half the CPU cores to avoid overload)
        max_workers = max(1, min((os.cpu_count() or 4) // 2, 4))
        logger.info(
            "Building %d video segments in parallel with %d workers",
            len(segment_tasks),
            max_workers,
        )

        segment_results: Dict[int, str] = {}
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_build_segment_task, task): task[0]
                for task in segment_tasks
            }

            for future in as_completed(futures):
                page_idx = futures[future]
                try:
                    idx, path = future.result()
                    segment_results[idx] = path
                    logger.debug("Segment for page %d completed: %s", idx, path)
                except Exception as exc:
                    logger.error("Failed to build segment for page %d: %s", page_idx, exc)
                    raise

        # Order segments by page index
        segment_files: List[str] = [
            segment_results[idx] for idx in sorted(segment_results.keys())
        ]

        if not segment_files:
            raise RuntimeError("No video segments produced for slide lecture")

        list_file: Optional[str] = None

        try:
            with tempfile.NamedTemporaryFile(
                "w",
                delete=False,
                dir=video_segments_dir,
                encoding="utf-8",
            ) as f:
                list_file = f.name
                for path in segment_files:
                    name = os.path.basename(path)
                    f.write(f"file '{self._escape(name)}'\n")

            video_only_path = os.path.join(video_segments_dir, "video_only.mp4")
            cmd_concat = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                os.path.basename(list_file),
                "-c:v",
                "copy",
                os.path.abspath(video_only_path),
            ]
            subprocess.run(
                cmd_concat,
                cwd=video_segments_dir,
                capture_output=True,
                check=True,
            )

            cmd_mux = [
                "ffmpeg",
                "-y",
                "-i",
                video_only_path,
                "-i",
                lecture_audio_path,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                os.path.abspath(output_video_path),
            ]
            subprocess.run(
                cmd_mux,
                cwd=video_segments_dir,
                capture_output=True,
                check=True,
            )
        finally:
            if list_file and os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except OSError:
                    pass

    def build_single_segment(
        self,
        *,
        image_path: str,
        audio_path: str,
        duration: float,
        output_path: str,
    ) -> None:
        """
        Build a single VIDEO-ONLY segment for one page (no audio track).

        Creates a video from a static image with the given duration.
        Audio will be muxed separately in the final step to avoid
        AAC encoder delay accumulation from per-page encoding.
        """
        img_path = _validate_media_path(image_path, ALLOWED_IMAGE_EXT)
        # audio_path is used only to validate existence; actual muxing happens later
        _validate_media_path(audio_path, ALLOWED_AUDIO_EXT)
        output_resolved = Path(output_path).resolve()

        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", str(img_path),
            "-t", f"{duration:.6f}",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-an",  # No audio - will be muxed separately
            str(output_resolved),
        ]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Failed to build video segment %s: %s",
                output_path,
                exc.stderr.decode("utf-8", errors="replace")
            )
            raise

    def concatenate_segments(
        self,
        *,
        segment_paths: List[str],
        output_path: str,
        lecture_audio_path: Optional[str] = None,
    ) -> None:
        """
        Concatenate multiple video segments into a single video.

        Uses FFmpeg concat demuxer to combine video-only segments.
        If lecture_audio_path is provided, muxes the audio track with
        a single AAC encoding pass to avoid encoder delay accumulation.
        """
        if not segment_paths:
            raise ValueError("No segments to concatenate")

        # Create a temporary file list for concat
        work_dir = os.path.dirname(output_path)
        if work_dir:
            os.makedirs(work_dir, exist_ok=True)
        list_file: Optional[str] = None
        video_only_path: Optional[str] = None

        try:
            with tempfile.NamedTemporaryFile(
                "w",
                delete=False,
                dir=work_dir or None,
                encoding="utf-8",
            ) as f:
                list_file = f.name
                for path in segment_paths:
                    validated = _validate_media_path(path, ALLOWED_VIDEO_EXT)
                    f.write(f"file '{self._escape(str(validated))}'\n")

            if lecture_audio_path:
                # Two-step: concat video-only, then mux audio with single AAC encode
                video_only_path = os.path.join(work_dir, "video_only_temp.mp4")
                cmd_concat = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file,
                    "-c:v", "copy",
                    "-an",
                    video_only_path,
                ]
                subprocess.run(
                    cmd_concat,
                    capture_output=True,
                    check=True,
                )

                # Mux audio with single AAC encoding
                audio_validated = _validate_media_path(lecture_audio_path, ALLOWED_AUDIO_EXT)
                cmd_mux = [
                    "ffmpeg",
                    "-y",
                    "-i", video_only_path,
                    "-i", str(audio_validated),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    os.path.abspath(output_path),
                ]
                subprocess.run(
                    cmd_mux,
                    capture_output=True,
                    check=True,
                )
            else:
                # Original behavior: just concat (for video-only or pre-muxed segments)
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file,
                    "-c", "copy",
                    os.path.abspath(output_path),
                ]
                subprocess.run(
                    cmd,
                    capture_output=True,
                    check=True,
                )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "Failed to concatenate segments: %s",
                exc.stderr.decode("utf-8", errors="replace")
            )
            raise
        finally:
            if list_file and os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except OSError:
                    pass
            if video_only_path and os.path.exists(video_only_path):
                try:
                    os.remove(video_only_path)
                except OSError:
                    pass

    @staticmethod
    def _escape(path: str) -> str:
        return path.replace("'", "\\'")

    @staticmethod
    def _concat_audio_files(
        audio_files: List[str],
        output_file: str,
        work_dir: str,
    ) -> None:
        if not audio_files:
            raise ValueError("No audio files provided for concatenation")

        os.makedirs(work_dir, exist_ok=True)
        list_file: Optional[str] = None

        try:
            with tempfile.NamedTemporaryFile(
                "w",
                delete=False,
                dir=work_dir or None,
                encoding="utf-8",
            ) as f:
                list_file = f.name
                for path in audio_files:
                    validated = _validate_media_path(path, ALLOWED_AUDIO_EXT)
                    f.write(f"file '{VideoComposer._escape(str(validated))}'\n")

            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                os.path.basename(list_file),
                "-c:a",
                "pcm_s16le",
                os.path.abspath(output_file),
            ]
            subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                check=True,
            )
        finally:
            if list_file and os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except OSError:
                    pass

    @staticmethod
    def _get_audio_duration(audio_path: str) -> float:
        try:
            validated = _validate_media_path(audio_path, ALLOWED_AUDIO_EXT)
        except Exception as exc:
            logger.error("Invalid audio path %s: %s", audio_path, exc)
            return 0.0

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(validated),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to get audio duration for %s: %s", audio_path, exc)
            return 0.0

        txt = result.stdout.strip()
        try:
            return float(txt)
        except ValueError:
            logger.error(
                "Invalid audio duration output for %s: %r",
                audio_path,
                txt,
            )
            return 0.0
