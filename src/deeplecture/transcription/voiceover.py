"""
TTS voiceover generation aligned with a simple "subtitle slot" model.

Goals:

- Treat each subtitle as a time slot and generate one TTS clip per slot.
- Locally adjust per-slot audio duration by padding silence or using
  ffmpeg's atempo filter.
- Concatenate all adjusted clips and replace the video's original audio
  track with the final voiceover track.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from deeplecture.config.config import load_config
from deeplecture.infra.parallel_pool import ResourceWorkerPool
from deeplecture.infra.retry import RetryConfig
from deeplecture.tts.tts_factory import TTS, TTSFactory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SubtitleSegment:
    """Single subtitle entry, with timing in seconds."""

    index: int          # Zero-based index (stable ordering)
    start: float        # Start time in seconds
    end: float          # End time in seconds
    text: str           # Subtitle text

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


class SubtitleVoiceoverGenerator:
    """
    Generate a voiceover track from an SRT subtitle file and replace the
    video's audio track using ffmpeg.

    Processing steps:
    1. Parse SRT into a list of time-stamped sentences.
    2. Run TTS concurrently and produce one `subtitle_N.wav` per sentence.
    3. For each clip, align its duration to the "subtitle slot":
       - If the audio is shorter than the slot, pad trailing silence;
       - If the audio is longer than the slot, speed it up via atempo;
       - If there is a gap before the next subtitle, extend the slot up
         to the next subtitle's start time so the gap becomes silence at
         the end of the current clip.
    4. If the first subtitle does not start at 0, prepend a leading silence.
    5. Concatenate all adjusted wav clips into a single voiceover track.
    6. Use ffmpeg to replace the original video audio track.
    """

    def __init__(
        self,
        tts: Optional[TTS] = None,
        config: Optional[Dict[str, Any]] = None,
        task_name: str = "voiceover",
        tts_factory: Optional[TTSFactory] = None,
    ) -> None:
        if config is None:
            config = load_config()
        self._config = config

        config = config or {}
        tts_cfg = config.get("tts") or {}

        # Fixed worker count - actual rate limiting is handled by RateLimitedTTS
        max_workers = 16

        # Sample rate for generated silence / intermediate wav clips.
        # Default to 44100 for good compatibility with common media pipelines.
        self.sample_rate: int = int(tts_cfg.get("sample_rate", 44100))

        # Load retry settings from unified RetryConfig
        self._retry_config = RetryConfig.from_config(tts_cfg)

        # Use injected factory (with shared rate limiter) or create standalone
        self._tts_factory = tts_factory or TTSFactory()
        self._custom_tts_provided = tts is not None
        self._tts_task_name = str(task_name or "voiceover")
        # Route through the registry so task_models controls the backend.
        self.tts: TTS = tts or self._tts_factory.get_tts_for_task(self._tts_task_name)

        self._tts_pool = ResourceWorkerPool(
            name="voiceover_tts",
            max_workers=max_workers,
            resource_factory=self._make_tts_instance,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_voiceover_from_srt(
        self,
        video_path: str,
        subtitle_path: str,
        output_dir: str,
        language: str = "zh",
        audio_basename: Optional[str] = None,
        voiceover_id: Optional[str] = None,  # Kept for caller logging; unused here
    ) -> Tuple[str, str]:
        """
        Generate a voiceover track from SRT and replace the video's audio.

        Returns (voiceover_audio_path, dubbed_video_path).
        """
        del voiceover_id  # Not needed in this implementation

        os.makedirs(output_dir, exist_ok=True)

        segments = self._parse_srt(subtitle_path)
        if not segments:
            raise ValueError(f"No valid subtitle segments found in {subtitle_path}")

        # Ensure segments are sorted by time (even if the SRT is out-of-order).
        segments.sort(key=lambda s: (s.start, s.index))

        base_name = audio_basename or f"voiceover_{language}"

        # Temporary segment directory, namespaced per voiceover.
        segments_dir = os.path.join(output_dir, f"{base_name}_segments")
        os.makedirs(segments_dir, exist_ok=True)

        # Final outputs: keep .m4a + .mp4 naming to stay compatible with routes/UI.
        voiceover_audio_path = os.path.join(output_dir, f"{base_name}.m4a")
        dubbed_video_path = os.path.join(output_dir, f"{base_name}.mp4")

        logger.info(
            "Starting TTS voiceover generation: %s segments, audio_base=%s",
            len(segments),
            base_name,
        )

        # Step 2: concurrently generate one wav per subtitle: subtitle_1.wav, ...
        self._synthesize_segments_concurrently(segments, segments_dir)

        # Step 3–4: align durations (pad/speed) and add any leading silence.
        adjusted_files = self._build_aligned_segment_files(segments, segments_dir)

        # Step 5: concatenate all clips into a single voiceover track.
        self._concat_audio_files(
            adjusted_files, voiceover_audio_path, segments_dir
        )

        # Step 6: replace the video's audio track.
        self._replace_video_audio_track(
            video_path=video_path,
            audio_path=voiceover_audio_path,
            output_video_path=dubbed_video_path,
        )

        logger.info(
            "Completed voiceover generation. Audio=%s, Dubbed video=%s",
            voiceover_audio_path,
            dubbed_video_path,
        )
        return voiceover_audio_path, dubbed_video_path

    # ------------------------------------------------------------------ #
    # SRT parsing
    # ------------------------------------------------------------------ #

    def _parse_srt(self, subtitle_path: str) -> List[SubtitleSegment]:
        """
        Parse a basic SRT file into a list of SubtitleSegment objects.

        The parsing logic is intentionally simple:
        - Split blocks on blank lines;
        - Second line is the "start --> end" timestamp;
        - Remaining lines are joined into the subtitle text.
        """
        with open(subtitle_path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = re.split(r"\n\s*\n", content.strip())
        segments: List[SubtitleSegment] = []

        time_pattern = re.compile(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
        )

        for raw_index, block in enumerate(blocks):
            lines = [
                line.strip("\ufeff")
                for line in block.strip().split("\n")
                if line.strip()
            ]
            if len(lines) < 2:
                continue

            # First line is usually a numeric ID; we only use it for stable ordering.
            try:
                index_line = int(lines[0].strip())
            except ValueError:
                index_line = raw_index

            time_line = lines[1].strip()
            # Allow extra metadata after the timestamps (position tags etc.)
            m = time_pattern.search(time_line)
            if not m:
                logger.warning(
                    "Skipping subtitle block with invalid timestamp: %s", time_line
                )
                continue

            start = (
                int(m.group(1)) * 3600
                + int(m.group(2)) * 60
                + int(m.group(3))
                + int(m.group(4)) / 1000.0
            )
            end = (
                int(m.group(5)) * 3600
                + int(m.group(6)) * 60
                + int(m.group(7))
                + int(m.group(8)) / 1000.0
            )

            text_lines = lines[2:]
            text = " ".join(t.strip() for t in text_lines).strip()
            if not text:
                continue

            segments.append(
                SubtitleSegment(
                    index=index_line,
                    start=start,
                    end=end,
                    text=text,
                )
        )

        return segments

    def _make_tts_instance(self) -> TTS:
        """
        Provide one TTS engine per worker. If caller injected a custom TTS,
        reuse it; otherwise build a fresh instance so threads do not share
        mutable state.
        """
        if self._custom_tts_provided:
            return self.tts
        return self._tts_factory.get_tts_for_task(self._tts_task_name)

    # ------------------------------------------------------------------ #
    # Step 2: concurrent TTS
    # ------------------------------------------------------------------ #

    def _synthesize_segments_concurrently(
        self,
        segments: List[SubtitleSegment],
        segments_dir: str,
    ) -> None:
        """
        Run TTS for each subtitle in parallel and produce per-line wav files.

        Output filenames: subtitle_1.wav, subtitle_2.wav, ...
        All are mono 16-bit PCM with sample_rate = self.sample_rate.

        Failure policy:
        - Count failures; if more than half fail, abort the whole operation;
        - Otherwise, generate 0.5s of silence for failed subtitles.
        """
        total = len(segments)
        if total == 0:
            return

        errors: List[Optional[BaseException]] = [None] * total

        tasks = list(enumerate(segments))

        def handler(tts_engine: TTS, idx: int, seg: SubtitleSegment) -> bool:
            wav_path = os.path.join(segments_dir, f"subtitle_{idx + 1}.wav")

            ext = getattr(tts_engine, "file_extension", ".wav") or ".wav"
            ext = ext if ext.startswith(".") else f".{ext}"

            if ext.lower() == ".wav":
                tmp_path = wav_path
            else:
                tmp_path = os.path.join(segments_dir, f"subtitle_{idx + 1}{ext}")

            last_exc: Optional[BaseException] = None
            max_retries = self._retry_config.max_retries
            min_wait = self._retry_config.min_wait

            for attempt in range(1, max_retries + 2):  # +2 because first attempt is not a retry
                try:
                    audio_bytes = tts_engine.synthesize(seg.text)
                    if not audio_bytes:
                        raise RuntimeError("TTS returned empty audio bytes")

                    with open(tmp_path, "wb") as f:
                        f.write(audio_bytes)

                    if tmp_path != wav_path:
                        self._transcode_to_wav(tmp_path, wav_path)
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass

                    if self._get_audio_duration(wav_path) <= 0:
                        raise RuntimeError("Generated audio has invalid duration")

                    return True
                except BaseException as exc:  # Includes KeyboardInterrupt; caller owns process-level handling
                    last_exc = exc
                    logger.warning(
                        "TTS synthesis failed for segment %s (attempt %s/%s): %s",
                        idx + 1,
                        attempt,
                        max_retries + 1,
                        exc,
                    )
                    if attempt <= max_retries:
                        # Exponential backoff: min_wait * 2^(attempt-1), capped at max_wait
                        wait_time = min(
                            min_wait * (2 ** (attempt - 1)),
                            self._retry_config.max_wait
                        )
                        time.sleep(wait_time)

            errors[idx] = last_exc or RuntimeError("unknown TTS failure")
            raise errors[idx]

        def handle_error(exc: BaseException, idx: int) -> bool:
            errors[idx] = exc
            logger.error("TTS worker crashed for segment %s: %s", idx + 1, exc)
            return False

        self._tts_pool.map(tasks, handler, on_error=handle_error)

        # If more than half of the segments fail, abort to avoid very poor output.
        failures = [e for e in errors if e is not None]
        if failures and len(failures) > total // 2:
            first_error = failures[0]
            raise RuntimeError(
                f"Too many TTS failures: {len(failures)}/{total} failed, "
                f"first error: {first_error}"
            )

        # For failed entries generate 0.5s silence; for successful ones ensure the file exists.
        for idx, error in enumerate(errors):
            wav_path = os.path.join(segments_dir, f"subtitle_{idx + 1}.wav")
            if error is not None:
                logger.warning(
                    "Generating 0.5s silence for failed subtitle %s: %s",
                    idx + 1,
                    error,
                )
                self._generate_silence_wav(wav_path, 0.5)
            else:
                if not os.path.exists(wav_path):
                    raise RuntimeError(
                        f"TTS output file does not exist for subtitle {idx + 1}: "
                        f"{wav_path}"
                    )

    # ------------------------------------------------------------------ #
    # Step 3 & 4: duration alignment + leading silence
    # ------------------------------------------------------------------ #

    def _build_aligned_segment_files(
        self,
        segments: List[SubtitleSegment],
        segments_dir: str,
    ) -> List[str]:
        """
        Compute the target "slot" duration for each subtitle and adjust audio.

        Rules:
        - Base duration is end - start;
        - If the next subtitle starts after the current one ends, extend the
          slot from current start to next.start (gap becomes silence);
        - If the first subtitle does not start at 0, add leading silence.
        """
        if not segments:
            return []

        audio_files: List[str] = []
        debug_rows: List[Dict[str, float]] = []

        # Leading silence if the first subtitle does not start at 0.
        first_start = max(0.0, segments[0].start)
        track_time = 0.0
        if first_start > 0.01:
            silence_path = os.path.join(segments_dir, "silence_0.wav")
            self._generate_silence_wav(silence_path, first_start)
            audio_files.append(silence_path)
            silence_dur = self._get_audio_duration(silence_path)
            track_time += silence_dur
            debug_rows.append(
                {
                    "index": 0,
                    "srt_start": 0.0,
                    "srt_end": first_start,
                    "slot_target": first_start,
                    "raw_duration": first_start,
                    "adjusted_duration": silence_dur,
                    "track_start": 0.0,
                    "track_end": track_time,
                }
            )

        n = len(segments)
        for i, seg in enumerate(segments):
            # ---------------------------------------------------------------
            # Drift correction: if the audio track is AHEAD of the subtitle start
            # (i.e. track_time < seg.start), insert silence to catch up.
            # ---------------------------------------------------------------
            drift = seg.start - track_time
            if drift > 0.002:  # 2ms threshold (tighter sync)
                drift_silence_path = os.path.join(segments_dir, f"drift_{i + 1}.wav")
                self._generate_silence_wav(drift_silence_path, drift)
                audio_files.append(drift_silence_path)
                
                real_drift_dur = self._get_audio_duration(drift_silence_path)
                drift_start = track_time
                track_time += real_drift_dur
                
                debug_rows.append(
                    {
                        "index": float(i) + 0.5, # 0.5 indicates drift correction
                        "srt_start": drift_start,
                        "srt_end": track_time,
                        "slot_target": drift,
                        "raw_duration": drift,
                        "adjusted_duration": real_drift_dur,
                        "track_start": drift_start,
                        "track_end": track_time,
                    }
                )

            base_duration = max(0.0, seg.end - seg.start)
            target_duration = base_duration

            if i < n - 1:
                nxt = segments[i + 1]
                if seg.end < nxt.start:
                    # Extend the current slot to the next subtitle's start (cover the gap).
                    target_duration = max(0.0, nxt.start - seg.start)

            input_wav = os.path.join(segments_dir, f"subtitle_{i + 1}.wav")
            if not os.path.exists(input_wav):
                raise RuntimeError(f"Missing TTS wav for subtitle {i + 1}: {input_wav}")

            adjusted_wav = os.path.join(segments_dir, f"adjusted_{i + 1}.wav")
            raw_dur, adj_dur = self._adjust_audio_duration(
                input_wav,
                adjusted_wav,
                target_duration,
                segments_dir,
            )
            audio_files.append(adjusted_wav)
            seg_track_start = track_time
            track_time += adj_dur

            debug_rows.append(
                {
                    "index": float(i + 1),
                    "srt_start": segments[i].start,
                    "srt_end": segments[i].end,
                    "slot_target": target_duration,
                    "raw_duration": raw_dur,
                    "adjusted_duration": adj_dur,
                    "track_start": seg_track_start,
                    "track_end": track_time,
                }
            )

        # Persist a simple timing debug file to help diagnose alignment issues.
        debug_path = os.path.join(segments_dir, "timing_debug.tsv")
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(
                    "index\t"
                    "srt_start\t"
                    "srt_end\t"
                    "slot_target\t"
                    "raw_duration\t"
                    "adjusted_duration\t"
                    "track_start\t"
                    "track_end\n"
                )
                for row in debug_rows:
                    f.write(
                        f"{row['index']:.1f}\t"
                        f"{row['srt_start']:.3f}\t"
                        f"{row['srt_end']:.3f}\t"
                        f"{row['slot_target']:.3f}\t"
                        f"{row['raw_duration']:.3f}\t"
                        f"{row['adjusted_duration']:.3f}\t"
                        f"{row['track_start']:.3f}\t"
                        f"{row['track_end']:.3f}\n"
                    )
        except Exception as exc:  # pragma: no cover - best-effort debug output
            logger.warning("Failed to write timing debug file: %s", exc)

        return audio_files

    # ------------------------------------------------------------------ #
    # Step 3 details: stretch/shrink to target duration
    # ------------------------------------------------------------------ #

    def _adjust_audio_duration(
        self,
        input_file: str,
        output_file: str,
        target_duration: float,
        work_dir: str,
    ) -> Tuple[float, float]:
        """
        Adjust a single clip to exactly target_duration seconds.

        Behavior:
        - If audio is shorter than target: pad trailing silence;
        - If audio is longer than target: increase playback speed via atempo;
        - If durations are effectively equal (within a small epsilon): copy as-is.
        """
        target_duration = max(0.0, float(target_duration))

        audio_duration_before = self._get_audio_duration(input_file)
        if audio_duration_before <= 0:
            raise RuntimeError(f"Invalid audio duration for {input_file}")

        # If target is non-positive, or durations already match closely, just copy.
        if target_duration <= 0 or abs(audio_duration_before - target_duration) < 0.01:
            if os.path.abspath(input_file) == os.path.abspath(output_file):
                audio_duration_after = self._get_audio_duration(output_file)
                return audio_duration_before, audio_duration_after
            shutil.copy2(input_file, output_file)
            audio_duration_after = self._get_audio_duration(output_file)
            return audio_duration_before, audio_duration_after

        # Shorter than target: pad with silence using apad and trim to target.
        if audio_duration_before < target_duration:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                input_file,
                "-af",
                "apad",
                "-t",
                f"{target_duration:.6f}",
                os.path.abspath(output_file),
            ]
            subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                check=True,
            )
        else:
            # Longer than target: adjust playback rate with atempo and trim.
            speed = audio_duration_before / target_duration
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                input_file,
                "-filter:a",
                f"atempo={speed:.6f}",
                "-t",
                f"{target_duration:.6f}",
                os.path.abspath(output_file),
            ]
            subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                check=True,
            )

        audio_duration_after = self._get_audio_duration(output_file)
        return audio_duration_before, audio_duration_after

    # ------------------------------------------------------------------ #
    # Step 5: Concatenate all audio clips
    # ------------------------------------------------------------------ #

    def _concat_audio_files(
        self,
        audio_files: List[str],
        output_file: str,
        work_dir: str,
    ) -> None:
        """
        Concatenate a list of wav files into the final voiceover track.

        We use ffmpeg's concat demuxer and encode directly to AAC (.m4a),
        matching the existing frontend/route expectations.
        """
        if not audio_files:
            raise ValueError("No audio files provided for concatenation")

        list_file = os.path.join(work_dir, "audio_list.txt")

        def _escape(path: str) -> str:
            return path.replace("'", "\\'")

        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for path in audio_files:
                    basename = os.path.basename(path)
                    f.write(f"file '{_escape(basename)}'\n")

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
                "aac",
                "-b:a",
                "192k",
                os.path.abspath(output_file),
            ]
            subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                check=True,
            )
        finally:
            try:
                os.remove(list_file)
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Utilities: transcoding / duration / silence / track replacement
    # ------------------------------------------------------------------ #

    def _transcode_to_wav(self, input_file: str, output_file: str) -> None:
        """Transcode any supported audio into 16-bit mono PCM wav."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-ar",
            str(self.sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            os.path.abspath(output_file),
        ]
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
        )

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip())
        except Exception as exc:
            logger.error("Failed to get audio duration for %s: %s", audio_path, exc)
            return 0.0

    def _generate_silence_wav(self, output_file: str, duration: float) -> None:
        """Generate a silence wav file of the given duration (seconds)."""
        duration = max(0.0, float(duration))
        if duration <= 0:
            # Do not produce zero-length files; callers should skip silence instead.
            return

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=mono:sample_rate={self.sample_rate}",
            "-t",
            f"{duration:.3f}",
            "-ar",
            str(self.sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            os.path.abspath(output_file),
        ]
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
        )

    def _replace_video_audio_track(
        self,
        video_path: str,
        audio_path: str,
        output_video_path: str,
    ) -> None:
        """Replace the video's audio track with the given voiceover track."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            os.path.abspath(output_video_path),
        ]
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
        )
