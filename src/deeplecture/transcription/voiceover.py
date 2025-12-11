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


@dataclasses.dataclass
class SegmentTiming:
    """Timing info for a single segment in the output video."""

    # Original video timing
    src_start: float    # Source video start time
    src_end: float      # Source video end time

    # Output timing
    out_start: float    # Output video start time
    out_duration: float # Output duration after speed adjustment

    # Speed factor (1.0 = normal, >1.0 = faster)
    speed: float = 1.0

    # Whether this is a silence/drift segment (no video content to speed up)
    is_filler: bool = False

    @property
    def src_duration(self) -> float:
        return max(0.0, self.src_end - self.src_start)


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
        voiceover_cfg = config.get("voiceover") or {}

        # Fixed worker count - actual rate limiting is handled by RateLimitedTTS
        max_workers = 16

        # Sample rate for generated silence / intermediate wav clips.
        # Default to 44100 for good compatibility with common media pipelines.
        self.sample_rate: int = int(tts_cfg.get("sample_rate", 44100))

        # Voiceover-specific settings for silence handling
        # If silence gap > threshold, speed up video instead of padding silence
        self.silence_threshold: float = float(voiceover_cfg.get("silence_threshold", 1.0))
        self.max_speed_factor: float = float(voiceover_cfg.get("max_speed_factor", 2.5))

        # Speed quantization buckets for optimization (reduces ffmpeg filter complexity)
        # By quantizing speeds to fixed buckets, adjacent segments with same speed can be merged
        self._speed_buckets: List[float] = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]

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

        # Get video duration for trailing segment handling
        video_duration = self._get_video_duration(video_path)

        logger.info(
            "Starting TTS voiceover generation: %s segments, audio_base=%s, "
            "silence_threshold=%.2fs, max_speed=%.2fx, video_duration=%.2fs",
            len(segments),
            base_name,
            self.silence_threshold,
            self.max_speed_factor,
            video_duration or 0.0,
        )

        # Step 2: concurrently generate one wav per subtitle: subtitle_1.wav, ...
        self._synthesize_segments_concurrently(segments, segments_dir)

        # Step 3–4: align durations and compute video speed adjustments.
        # Returns (audio_files, segment_timings) where segment_timings contains
        # the speed factor for each video segment.
        adjusted_files, segment_timings = self._build_aligned_segment_files(
            segments, segments_dir, video_duration=video_duration
        )

        # Step 5: concatenate all clips into a single voiceover track.
        self._concat_audio_files(
            adjusted_files, voiceover_audio_path, segments_dir
        )

        # Step 6: replace the video's audio track with optional video speed adjustment.
        self._replace_video_audio_track(
            video_path=video_path,
            audio_path=voiceover_audio_path,
            output_video_path=dubbed_video_path,
            segment_timings=segment_timings,
            work_dir=segments_dir,
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
    # Speed quantization for optimization
    # ------------------------------------------------------------------ #

    def _quantize_speed(self, speed: float) -> float:
        """
        Quantize speed to the smallest bucket >= speed for optimization.

        By using ceil-style quantization (smallest bucket >= speed), we ensure:
        1. Video is never slower than required (would cause audio to be longer than video)
        2. Adjacent segments with same quantized speed can be merged
        3. When speed is slightly above 1.0 (e.g., 1.05), we use the next bucket
           rather than falling back to 1.0 which would defeat the speed-up purpose

        If speed is <= 1.0, returns 1.0 (no speed-up needed).
        """
        if speed <= 1.0:
            return 1.0
        # Find the smallest bucket that is >= speed and doesn't exceed max_speed_factor
        valid_buckets = [b for b in self._speed_buckets if b <= self.max_speed_factor and b >= speed]
        if valid_buckets:
            return min(valid_buckets)
        # If no bucket >= speed exists (speed > all buckets), use the largest valid bucket
        capped_buckets = [b for b in self._speed_buckets if b <= self.max_speed_factor]
        if capped_buckets:
            return max(capped_buckets)
        return 1.0

    # ------------------------------------------------------------------ #
    # Step 3 & 4: duration alignment + leading silence
    # ------------------------------------------------------------------ #

    def _build_aligned_segment_files(
        self,
        segments: List[SubtitleSegment],
        segments_dir: str,
        video_duration: Optional[float] = None,
    ) -> Tuple[List[str], List[SegmentTiming]]:
        """
        Compute the target "slot" duration for each subtitle and adjust audio.

        Returns:
            (audio_files, segment_timings): List of adjusted audio files and
            corresponding timing info for video speed adjustment.

        Algorithm:
        1. Each subtitle defines a "slot" from seg.start to slot_end (next subtitle start or seg.end)
        2. TTS audio is generated for each slot
        3. If TTS duration < slot duration:
           - Gap <= threshold: Pad audio with silence, video plays at 1x
           - Gap > threshold: Keep audio as-is, video speeds up to match
        4. If TTS duration > slot duration: Speed up audio, video plays at 1x
        5. Leading segment (0 to first subtitle): Video at 1x with silence audio
        6. Trailing segment (after last subtitle to video end): Video at 1x with silence audio
        """
        if not segments:
            return [], []

        audio_files: List[str] = []
        segment_timings: List[SegmentTiming] = []
        debug_rows: List[Dict[str, Any]] = []

        out_time = 0.0  # Cumulative output timeline position

        # Leading segment: video from 0 to first subtitle start
        first_start = max(0.0, segments[0].start)
        if first_start > 0.01:
            silence_path = os.path.join(segments_dir, "silence_0.wav")
            self._generate_silence_wav(silence_path, first_start)
            audio_files.append(silence_path)
            silence_dur = self._get_audio_duration(silence_path)

            # Leading segment: video plays at 1x, audio is silence
            segment_timings.append(SegmentTiming(
                src_start=0.0,
                src_end=first_start,
                out_start=0.0,
                out_duration=silence_dur,
                speed=1.0,
                is_filler=False,  # NOT filler - this is real video content
            ))

            out_time = silence_dur

            debug_rows.append({
                "index": 0,
                "type": "leading",
                "src_start": 0.0,
                "src_end": first_start,
                "slot_target": first_start,
                "raw_duration": first_start,
                "adjusted_duration": silence_dur,
                "out_start": 0.0,
                "out_end": out_time,
                "video_speed": 1.0,
            })

        n = len(segments)
        for i, seg in enumerate(segments):
            # Calculate slot: from seg.start to next subtitle start (or seg.end)
            slot_end = seg.end
            if i < n - 1:
                nxt = segments[i + 1]
                if seg.end < nxt.start:
                    # Extend slot to cover gap until next subtitle
                    slot_end = nxt.start

            slot_duration = max(0.0, slot_end - seg.start)

            input_wav = os.path.join(segments_dir, f"subtitle_{i + 1}.wav")
            if not os.path.exists(input_wav):
                raise RuntimeError(f"Missing TTS wav for subtitle {i + 1}: {input_wav}")

            raw_dur = self._get_audio_duration(input_wav)
            if raw_dur <= 0:
                raise RuntimeError(f"Invalid audio duration for {input_wav}")

            adjusted_wav = os.path.join(segments_dir, f"adjusted_{i + 1}.wav")
            video_speed = 1.0
            adj_dur = slot_duration  # Default: audio matches slot

            # Skip zero/near-zero slot duration segments entirely to avoid timeline drift
            # These can occur when subtitles have identical start/end times
            if slot_duration < 1e-3:
                logger.warning(
                    "Segment %d has near-zero slot duration (%.6fs), skipping to avoid drift",
                    i + 1, slot_duration
                )
                continue

            silence_gap = slot_duration - raw_dur

            if silence_gap > self.silence_threshold:
                # Large gap: speed up video instead of padding silence
                # Quantize speed for optimization (enables merging adjacent same-speed segments)
                required_speed = slot_duration / raw_dur
                video_speed = self._quantize_speed(min(required_speed, self.max_speed_factor))

                # Calculate target output duration based on quantized speed
                # Video output duration = slot_duration / video_speed
                # Audio output duration must match exactly to maintain A/V sync
                target_out_dur = slot_duration / video_speed

                if abs(target_out_dur - raw_dur) < 1e-3:
                    # Quantized speed matches almost exactly, just copy audio
                    adj_dur = raw_dur
                    shutil.copy2(input_wav, adjusted_wav)
                elif target_out_dur < raw_dur:
                    # Quantized speed is higher than required, need to speed up audio to match
                    # This happens when quantization rounds UP to a faster bucket
                    audio_speed = raw_dur / target_out_dur
                    self._speed_up_audio(input_wav, adjusted_wav, audio_speed, target_out_dur, segments_dir)
                    adj_dur = self._get_audio_duration(adjusted_wav)
                else:
                    # Need to pad audio to match the (longer) quantized video duration
                    self._pad_audio_to_duration(input_wav, adjusted_wav, target_out_dur, segments_dir)
                    # Re-read actual duration to avoid ffmpeg rounding drift
                    adj_dur = self._get_audio_duration(adjusted_wav)

                logger.debug(
                    "Segment %d: slot=%.2fs, tts=%.2fs, gap=%.2fs > threshold, "
                    "video_speed=%.2fx (quantized), out_dur=%.2fs",
                    i + 1, slot_duration, raw_dur, silence_gap, video_speed, adj_dur
                )
            elif silence_gap >= -0.01:
                # Small positive gap OR near-match: always pad to slot duration
                self._pad_audio_to_duration(input_wav, adjusted_wav, slot_duration, segments_dir)
                adj_dur = self._get_audio_duration(adjusted_wav)
            else:
                # TTS is longer than slot - speed up audio
                audio_speed = raw_dur / slot_duration
                self._speed_up_audio(input_wav, adjusted_wav, audio_speed, slot_duration, segments_dir)
                adj_dur = self._get_audio_duration(adjusted_wav)

            audio_files.append(adjusted_wav)

            seg_out_start = out_time
            segment_timings.append(SegmentTiming(
                src_start=seg.start,
                src_end=slot_end,
                out_start=seg_out_start,
                out_duration=adj_dur,
                speed=video_speed,
                is_filler=False,
            ))

            out_time += adj_dur

            debug_rows.append({
                "index": float(i + 1),
                "type": "subtitle",
                "src_start": seg.start,
                "src_end": slot_end,
                "slot_target": slot_duration,
                "raw_duration": raw_dur,
                "adjusted_duration": adj_dur,
                "out_start": seg_out_start,
                "out_end": out_time,
                "video_speed": video_speed,
            })

        # Trailing segment: video from last slot_end to video end
        if segment_timings:
            last_src_end = segment_timings[-1].src_end
            if video_duration is None:
                # ffprobe failed - warn user that audio may not match video length
                logger.warning(
                    "Could not determine video duration (ffprobe failed). "
                    "Audio track may be shorter than video. Last subtitle ends at %.2fs",
                    last_src_end
                )
            elif video_duration > last_src_end + 0.01:
                tail_duration = video_duration - last_src_end
                tail_silence_path = os.path.join(segments_dir, "silence_tail.wav")
                self._generate_silence_wav(tail_silence_path, tail_duration)
                audio_files.append(tail_silence_path)
                tail_audio_dur = self._get_audio_duration(tail_silence_path)

                tail_out_start = out_time
                segment_timings.append(SegmentTiming(
                    src_start=last_src_end,
                    src_end=video_duration,
                    out_start=tail_out_start,
                    out_duration=tail_audio_dur,
                    speed=1.0,
                    is_filler=False,  # Real video content
                ))

                out_time += tail_audio_dur

                debug_rows.append({
                    "index": n + 1,
                    "type": "trailing",
                    "src_start": last_src_end,
                    "src_end": video_duration,
                    "slot_target": tail_duration,
                    "raw_duration": tail_duration,
                    "adjusted_duration": tail_audio_dur,
                    "out_start": tail_out_start,
                    "out_end": out_time,
                    "video_speed": 1.0,
                })

        # Persist timing debug file
        debug_path = os.path.join(segments_dir, "timing_debug.tsv")
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(
                    "index\ttype\tsrc_start\tsrc_end\tslot_target\t"
                    "raw_duration\tadjusted_duration\tout_start\tout_end\tvideo_speed\n"
                )
                for row in debug_rows:
                    f.write(
                        f"{row['index']:.1f}\t{row['type']}\t"
                        f"{row['src_start']:.3f}\t{row['src_end']:.3f}\t"
                        f"{row['slot_target']:.3f}\t{row['raw_duration']:.3f}\t"
                        f"{row['adjusted_duration']:.3f}\t{row['out_start']:.3f}\t"
                        f"{row['out_end']:.3f}\t{row['video_speed']:.2f}\n"
                    )
        except Exception as exc:
            logger.warning("Failed to write timing debug file: %s", exc)

        # Log summary and validate
        speed_segments = [t for t in segment_timings if t.speed > 1.0]
        if speed_segments:
            logger.info(
                "Video speed-up applied to %d/%d segments (threshold=%.1fs)",
                len(speed_segments), len(segment_timings), self.silence_threshold
            )

        # Validation: ensure timing consistency
        # Use stricter threshold (0.02s) to catch accumulated drift early
        total_out_duration = sum(t.out_duration for t in segment_timings)
        expected_video_duration = sum(t.src_duration / t.speed for t in segment_timings)
        timing_diff = abs(total_out_duration - expected_video_duration)
        if timing_diff > 0.02:
            logger.warning(
                "Timing mismatch detected: audio=%.3fs, expected_video=%.3fs (diff=%.3fs). "
                "This may cause audio-video desync.",
                total_out_duration, expected_video_duration, timing_diff
            )

        return audio_files, segment_timings

    # ------------------------------------------------------------------ #
    # Audio duration adjustment helpers
    # ------------------------------------------------------------------ #

    def _pad_audio_to_duration(
        self,
        input_file: str,
        output_file: str,
        target_duration: float,
        work_dir: str,
    ) -> None:
        """Pad audio with silence to reach target duration."""
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
        subprocess.run(cmd, cwd=work_dir, capture_output=True, check=True)

    def _speed_up_audio(
        self,
        input_file: str,
        output_file: str,
        speed: float,
        target_duration: float,
        work_dir: str,
    ) -> None:
        """Speed up audio using atempo filter.

        FFmpeg's atempo filter only supports range [0.5, 2.0].
        For speeds outside this range, we chain multiple atempo filters.
        For example: speed=4.0 → atempo=2.0,atempo=2.0
        """
        # Build atempo filter chain for speeds outside [0.5, 2.0] range
        atempo_filters = []
        remaining_speed = speed

        # Handle speed > 2.0 by chaining atempo=2.0 filters
        while remaining_speed > 2.0:
            atempo_filters.append("atempo=2.0")
            remaining_speed /= 2.0

        # Handle speed < 0.5 by chaining atempo=0.5 filters
        while remaining_speed < 0.5:
            atempo_filters.append("atempo=0.5")
            remaining_speed /= 0.5

        # Add the final atempo for remaining speed adjustment
        if abs(remaining_speed - 1.0) > 0.001:
            atempo_filters.append(f"atempo={remaining_speed:.6f}")

        # If no filters needed (speed ≈ 1.0), just copy
        if not atempo_filters:
            shutil.copy2(input_file, output_file)
            return

        filter_string = ",".join(atempo_filters)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-filter:a",
            filter_string,
            "-t",
            f"{target_duration:.6f}",
            os.path.abspath(output_file),
        ]
        subprocess.run(cmd, cwd=work_dir, capture_output=True, check=True)

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

    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """Get video duration in seconds using ffprobe."""
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
                    video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip())
        except Exception as exc:
            logger.warning("Failed to get video duration for %s: %s", video_path, exc)
            return None

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
        segment_timings: Optional[List[SegmentTiming]] = None,
        work_dir: Optional[str] = None,
    ) -> None:
        """
        Replace the video's audio track with the given voiceover track.

        If segment_timings contains segments with speed > 1.0, apply segment-based
        video speed adjustment using FFmpeg complex filter.
        """
        # Check if any segments need speed adjustment
        need_speed_adjustment = (
            segment_timings
            and any(t.speed > 1.0 for t in segment_timings)
        )

        if not need_speed_adjustment:
            # Simple case: just replace audio track (fast, uses copy codec)
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
            subprocess.run(cmd, capture_output=True, check=True)
            return

        # Complex case: need to apply segment-based video speed adjustment
        # First, merge adjacent segments with same speed to reduce filter complexity
        merged_timings = self._merge_segment_timings(segment_timings)

        logger.info(
            "Applying segment-based video speed adjustment (%d segments after merge)",
            len(merged_timings),
        )

        # Build FFmpeg complex filter for video speed adjustment
        filter_complex, concat_inputs = self._build_video_speed_filter(merged_timings)

        # Use work_dir for intermediate files if provided
        if work_dir:
            temp_video = os.path.join(work_dir, "speed_adjusted_video.mp4")
            filter_script_path = os.path.join(work_dir, "filter_complex.txt")
        else:
            temp_video = output_video_path + ".temp.mp4"
            filter_script_path = output_video_path + ".filter.txt"

        try:
            # Write filter_complex to a script file to avoid command line length limits
            # This is especially important after merging (still potentially 100+ segments)
            with open(filter_script_path, "w", encoding="utf-8") as f:
                f.write(filter_complex)

            # Step 1: Apply video speed adjustment using filter script
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                video_path,
                "-filter_complex_script",
                filter_script_path,
                "-map",
                "[vout]",
                "-an",  # No audio in intermediate file
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                os.path.abspath(temp_video),
            ]

            logger.debug("FFmpeg video speed command (using filter script): %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("FFmpeg video speed adjustment failed: %s", result.stderr)
                raise RuntimeError(f"FFmpeg video speed adjustment failed: {result.stderr}")

            # Step 2: Combine speed-adjusted video with voiceover audio
            # Use -shortest to ensure output matches the shorter of video/audio
            # This handles any minor timing drift from ffmpeg rounding
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                temp_video,
                "-i",
                audio_path,
                "-c:v",
                "copy",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",  # Match output to shorter stream to avoid drift
                os.path.abspath(output_video_path),
            ]
            subprocess.run(cmd, capture_output=True, check=True)

        finally:
            # Clean up intermediate files
            for cleanup_path in [temp_video, filter_script_path]:
                if cleanup_path and cleanup_path != output_video_path and os.path.exists(cleanup_path):
                    try:
                        os.remove(cleanup_path)
                    except OSError:
                        pass

    def _merge_segment_timings(
        self,
        segment_timings: List[SegmentTiming],
        tolerance: float = 1e-3,
    ) -> List[SegmentTiming]:
        """
        Merge adjacent segments with the same speed to reduce ffmpeg filter complexity.

        This optimization can reduce segment count from ~2000 to ~100-200 for a typical
        2-hour video, dramatically improving processing time.

        Args:
            segment_timings: List of SegmentTiming objects
            tolerance: Time tolerance for considering segments as adjacent (seconds)

        Returns:
            Merged list of SegmentTiming objects
        """
        if not segment_timings:
            return []

        merged: List[SegmentTiming] = []

        for timing in segment_timings:
            if merged:
                last = merged[-1]
                # Check if segments can be merged:
                # 1. Same speed (exact match since we quantize)
                # 2. Contiguous in source timeline (src_end ≈ next src_start)
                same_speed = abs(timing.speed - last.speed) < tolerance
                contiguous = abs(timing.src_start - last.src_end) < tolerance

                if same_speed and contiguous:
                    # Merge: extend last segment
                    merged[-1] = SegmentTiming(
                        src_start=last.src_start,
                        src_end=timing.src_end,
                        out_start=last.out_start,
                        out_duration=last.out_duration + timing.out_duration,
                        speed=last.speed,
                        is_filler=last.is_filler and timing.is_filler,
                    )
                    continue

            merged.append(timing)

        original_count = len(segment_timings)
        merged_count = len(merged)
        if original_count > merged_count:
            logger.info(
                "Merged %d segments into %d (%.1f%% reduction)",
                original_count,
                merged_count,
                100 * (1 - merged_count / original_count),
            )

        return merged

    def _build_video_speed_filter(
        self,
        segment_timings: List[SegmentTiming],
    ) -> Tuple[str, int]:
        """
        Build FFmpeg complex filter for segment-based video speed adjustment.

        Returns:
            (filter_complex_string, num_concat_inputs)

        The filter:
        1. Trims video into segments based on src_start/src_end
        2. Applies setpts to speed up segments where speed > 1.0
        3. Concatenates all segments back together
        """
        filter_parts = []
        concat_inputs = []

        for i, timing in enumerate(segment_timings):
            segment_label = f"seg{i}"

            # Trim the source video segment
            trim_filter = (
                f"[0:v]trim=start={timing.src_start:.6f}:end={timing.src_end:.6f},"
                f"setpts=PTS-STARTPTS"
            )

            if timing.speed > 1.0:
                # Apply speed adjustment: setpts=PTS/speed
                # For speed=2.0, setpts=PTS/2.0 plays at 2x speed
                trim_filter += f",setpts=PTS/{timing.speed:.6f}"

            trim_filter += f"[{segment_label}]"
            filter_parts.append(trim_filter)
            concat_inputs.append(f"[{segment_label}]")

        # Concatenate all segments
        concat_filter = "".join(concat_inputs) + f"concat=n={len(segment_timings)}:v=1:a=0[vout]"
        filter_parts.append(concat_filter)

        filter_complex = ";".join(filter_parts)
        return filter_complex, len(segment_timings)
