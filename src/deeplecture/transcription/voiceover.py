"""
TTS voiceover generation with playback-side sync.

Architecture:
- Server generates: voiceover audio (m4a) + sync_timeline.json
- Client handles: real-time video speed adjustment during playback
- No server-side video processing (eliminates 60-90min encoding time)

The sync_timeline.json maps audio time → video time with speed factors,
enabling the frontend player to sync video playback to the voiceover audio.
"""

from __future__ import annotations

import dataclasses
import json
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
class SyncSegment:
    """
    A segment in the sync timeline for playback-side A/V sync.

    Maps audio timeline (dst_*) to video timeline (src_*).
    Formula: video_time = src_start + (audio_time - dst_start) * speed
    """

    dst_start: float    # Audio timeline start (seconds)
    dst_end: float      # Audio timeline end (seconds)
    src_start: float    # Video timeline start (seconds)
    src_end: float      # Video timeline end (seconds)
    speed: float        # = (src_end - src_start) / (dst_end - dst_start)

    def to_dict(self) -> Dict[str, float]:
        return {
            "dst_start": round(self.dst_start, 3),
            "dst_end": round(self.dst_end, 3),
            "src_start": round(self.src_start, 3),
            "src_end": round(self.src_end, 3),
            "speed": round(self.speed, 3),
        }


@dataclasses.dataclass
class VoiceoverResult:
    """Result of voiceover generation."""

    audio_path: str         # Path to voiceover audio file (m4a)
    timeline_path: str      # Path to sync_timeline.json
    audio_duration: float   # Total audio duration in seconds
    video_duration: float   # Original video duration in seconds


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


class SubtitleVoiceoverGenerator:
    """
    Generate a voiceover track and sync timeline from an SRT subtitle file.

    Processing steps:
    1. Parse SRT into a list of time-stamped sentences.
    2. Run TTS concurrently and produce one wav per sentence.
    3. Align each clip's duration to its subtitle slot.
    4. Concatenate all clips into a single voiceover track.
    5. Generate sync_timeline.json for playback-side A/V sync.

    No video processing is done - the client handles real-time sync.
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

        max_workers = 16

        self.sample_rate: int = int(tts_cfg.get("sample_rate", 44100))

        # If silence gap > threshold, video speeds up instead of audio padding
        self.silence_threshold: float = float(voiceover_cfg.get("silence_threshold", 1.0))
        self.max_speed_factor: float = float(voiceover_cfg.get("max_speed_factor", 2.5))

        # Speed quantization buckets (enables segment merging)
        self._speed_buckets: List[float] = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]

        self._retry_config = RetryConfig.from_config(tts_cfg)

        self._tts_factory = tts_factory or TTSFactory()
        self._custom_tts_provided = tts is not None
        self._tts_task_name = str(task_name or "voiceover")
        self.tts: TTS = tts or self._tts_factory.get_tts_for_task(self._tts_task_name)

        self._tts_pool = ResourceWorkerPool(
            name="voiceover_tts",
            max_workers=max_workers,
            resource_factory=self._make_tts_instance,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_voiceover(
        self,
        video_path: str,
        subtitle_path: str,
        output_dir: str,
        language: str = "zh",
        audio_basename: Optional[str] = None,
    ) -> VoiceoverResult:
        """
        Generate voiceover audio and sync timeline from SRT.

        Returns VoiceoverResult with paths to audio and timeline files.
        """
        os.makedirs(output_dir, exist_ok=True)

        segments = self._parse_srt(subtitle_path)
        if not segments:
            raise ValueError(f"No valid subtitle segments found in {subtitle_path}")

        segments.sort(key=lambda s: (s.start, s.index))

        base_name = audio_basename or f"voiceover_{language}"
        segments_dir = os.path.join(output_dir, f"{base_name}_segments")
        os.makedirs(segments_dir, exist_ok=True)

        voiceover_audio_path = os.path.join(output_dir, f"{base_name}.m4a")
        timeline_path = os.path.join(output_dir, f"{base_name}_sync_timeline.json")

        video_duration = self._get_video_duration(video_path) or 0.0

        logger.info(
            "Starting voiceover generation: %d segments, video_duration=%.2fs",
            len(segments),
            video_duration,
        )

        # Step 1: Generate TTS for each subtitle
        self._synthesize_segments_concurrently(segments, segments_dir)

        # Step 2: Align durations and build sync timeline
        audio_files, sync_segments = self._build_aligned_segments(
            segments, segments_dir, video_duration
        )

        # Step 3: Concatenate audio
        self._concat_audio_files(audio_files, voiceover_audio_path, segments_dir)

        audio_duration = self._get_audio_duration(voiceover_audio_path)

        # Step 4: Merge adjacent same-speed segments and write timeline
        merged_segments = self._merge_sync_segments(sync_segments)
        self._write_sync_timeline(
            timeline_path,
            merged_segments,
            video_duration,
            audio_duration,
        )

        # Clean up intermediate files
        try:
            shutil.rmtree(segments_dir)
        except OSError as e:
            logger.warning("Failed to clean up segments dir: %s", e)

        logger.info(
            "Voiceover generation complete: audio=%s, timeline=%s, "
            "%d sync segments (merged from %d)",
            voiceover_audio_path,
            timeline_path,
            len(merged_segments),
            len(sync_segments),
        )

        return VoiceoverResult(
            audio_path=voiceover_audio_path,
            timeline_path=timeline_path,
            audio_duration=audio_duration,
            video_duration=video_duration,
        )

    # ------------------------------------------------------------------ #
    # SRT parsing
    # ------------------------------------------------------------------ #

    def _parse_srt(self, subtitle_path: str) -> List[SubtitleSegment]:
        """Parse SRT file into SubtitleSegment list."""
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

            try:
                index_line = int(lines[0].strip())
            except ValueError:
                index_line = raw_index

            time_line = lines[1].strip()
            m = time_pattern.search(time_line)
            if not m:
                logger.warning("Skipping block with invalid timestamp: %s", time_line)
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

            segments.append(SubtitleSegment(index=index_line, start=start, end=end, text=text))

        return segments

    def _make_tts_instance(self) -> TTS:
        """Provide one TTS engine per worker."""
        if self._custom_tts_provided:
            return self.tts
        return self._tts_factory.get_tts_for_task(self._tts_task_name)

    # ------------------------------------------------------------------ #
    # TTS synthesis
    # ------------------------------------------------------------------ #

    def _synthesize_segments_concurrently(
        self,
        segments: List[SubtitleSegment],
        segments_dir: str,
    ) -> None:
        """Run TTS for each subtitle in parallel."""
        total = len(segments)
        if total == 0:
            return

        errors: List[Optional[BaseException]] = [None] * total
        tasks = list(enumerate(segments))

        def handler(tts_engine: TTS, idx: int, seg: SubtitleSegment) -> bool:
            wav_path = os.path.join(segments_dir, f"subtitle_{idx + 1}.wav")
            ext = getattr(tts_engine, "file_extension", ".wav") or ".wav"
            ext = ext if ext.startswith(".") else f".{ext}"

            tmp_path = wav_path if ext.lower() == ".wav" else os.path.join(
                segments_dir, f"subtitle_{idx + 1}{ext}"
            )

            last_exc: Optional[BaseException] = None
            max_retries = self._retry_config.max_retries
            min_wait = self._retry_config.min_wait

            for attempt in range(1, max_retries + 2):
                try:
                    audio_bytes = tts_engine.synthesize(seg.text)
                    if not audio_bytes:
                        raise RuntimeError("TTS returned empty audio")

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
                except BaseException as exc:
                    last_exc = exc
                    logger.warning(
                        "TTS failed for segment %d (attempt %d/%d): %s",
                        idx + 1, attempt, max_retries + 1, exc,
                    )
                    if attempt <= max_retries:
                        wait_time = min(min_wait * (2 ** (attempt - 1)), self._retry_config.max_wait)
                        time.sleep(wait_time)

            errors[idx] = last_exc or RuntimeError("unknown TTS failure")
            raise errors[idx]

        def handle_error(exc: BaseException, idx: int) -> bool:
            errors[idx] = exc
            logger.error("TTS worker crashed for segment %d: %s", idx + 1, exc)
            return False

        self._tts_pool.map(tasks, handler, on_error=handle_error)

        failures = [e for e in errors if e is not None]
        if failures and len(failures) > total // 2:
            raise RuntimeError(f"Too many TTS failures: {len(failures)}/{total}")

        # Generate silence for failed segments
        for idx, error in enumerate(errors):
            wav_path = os.path.join(segments_dir, f"subtitle_{idx + 1}.wav")
            if error is not None:
                logger.warning("Generating silence for failed segment %d", idx + 1)
                self._generate_silence_wav(wav_path, 0.5)
            elif not os.path.exists(wav_path):
                raise RuntimeError(f"TTS output missing for segment {idx + 1}")

    # ------------------------------------------------------------------ #
    # Speed quantization
    # ------------------------------------------------------------------ #

    def _quantize_speed(self, speed: float) -> float:
        """Quantize to smallest bucket >= speed (ceil-style)."""
        if speed <= 1.0:
            return 1.0
        valid = [b for b in self._speed_buckets if b <= self.max_speed_factor and b >= speed]
        if valid:
            return min(valid)
        capped = [b for b in self._speed_buckets if b <= self.max_speed_factor]
        return max(capped) if capped else 1.0

    # ------------------------------------------------------------------ #
    # Duration alignment and sync timeline generation
    # ------------------------------------------------------------------ #

    def _build_aligned_segments(
        self,
        segments: List[SubtitleSegment],
        segments_dir: str,
        video_duration: float,
    ) -> Tuple[List[str], List[SyncSegment]]:
        """
        Align audio durations and build sync timeline.

        Returns (audio_files, sync_segments).
        """
        if not segments:
            return [], []

        audio_files: List[str] = []
        sync_segments: List[SyncSegment] = []
        dst_time = 0.0  # Audio timeline position

        # Leading silence: video 0 → first subtitle
        first_start = max(0.0, segments[0].start)
        if first_start > 0.01:
            silence_path = os.path.join(segments_dir, "silence_0.wav")
            self._generate_silence_wav(silence_path, first_start)
            audio_files.append(silence_path)
            silence_dur = self._get_audio_duration(silence_path)

            sync_segments.append(SyncSegment(
                dst_start=dst_time,
                dst_end=dst_time + silence_dur,
                src_start=0.0,
                src_end=first_start,
                speed=1.0,
            ))
            dst_time += silence_dur

        n = len(segments)
        for i, seg in enumerate(segments):
            # Slot: seg.start → next subtitle start (or seg.end)
            slot_end = seg.end
            if i < n - 1 and seg.end < segments[i + 1].start:
                slot_end = segments[i + 1].start

            slot_duration = max(0.0, slot_end - seg.start)
            if slot_duration < 1e-3:
                logger.warning("Skipping near-zero slot for segment %d", i + 1)
                continue

            input_wav = os.path.join(segments_dir, f"subtitle_{i + 1}.wav")
            if not os.path.exists(input_wav):
                raise RuntimeError(f"Missing TTS wav for segment {i + 1}")

            raw_dur = self._get_audio_duration(input_wav)
            if raw_dur <= 0:
                raise RuntimeError(f"Invalid audio duration for segment {i + 1}")

            adjusted_wav = os.path.join(segments_dir, f"adjusted_{i + 1}.wav")
            silence_gap = slot_duration - raw_dur

            if silence_gap > self.silence_threshold:
                # Large gap: video speeds up
                required_speed = slot_duration / raw_dur
                video_speed = self._quantize_speed(min(required_speed, self.max_speed_factor))
                target_out_dur = slot_duration / video_speed

                if abs(target_out_dur - raw_dur) < 1e-3:
                    shutil.copy2(input_wav, adjusted_wav)
                    adj_dur = raw_dur
                elif target_out_dur < raw_dur:
                    audio_speed = raw_dur / target_out_dur
                    self._speed_up_audio(input_wav, adjusted_wav, audio_speed, target_out_dur, segments_dir)
                    adj_dur = self._get_audio_duration(adjusted_wav)
                else:
                    self._pad_audio_to_duration(input_wav, adjusted_wav, target_out_dur, segments_dir)
                    adj_dur = self._get_audio_duration(adjusted_wav)
            elif silence_gap >= -0.01:
                # Small gap or match: pad to slot
                self._pad_audio_to_duration(input_wav, adjusted_wav, slot_duration, segments_dir)
                adj_dur = self._get_audio_duration(adjusted_wav)
                video_speed = 1.0
            else:
                # TTS longer than slot: speed up audio
                audio_speed = raw_dur / slot_duration
                self._speed_up_audio(input_wav, adjusted_wav, audio_speed, slot_duration, segments_dir)
                adj_dur = self._get_audio_duration(adjusted_wav)
                video_speed = 1.0

            audio_files.append(adjusted_wav)

            # Recalculate actual speed based on real durations
            # Formula: speed = src_delta / dst_delta = (slot_end - seg.start) / adj_dur
            src_delta = slot_end - seg.start
            actual_speed = src_delta / adj_dur if adj_dur > 1e-6 else 1.0

            sync_segments.append(SyncSegment(
                dst_start=dst_time,
                dst_end=dst_time + adj_dur,
                src_start=seg.start,
                src_end=slot_end,
                speed=actual_speed,
            ))
            dst_time += adj_dur

        # Trailing silence: last slot → video end
        if sync_segments and video_duration > 0:
            last_src_end = sync_segments[-1].src_end
            if video_duration > last_src_end + 0.01:
                tail_duration = video_duration - last_src_end
                tail_path = os.path.join(segments_dir, "silence_tail.wav")
                self._generate_silence_wav(tail_path, tail_duration)
                audio_files.append(tail_path)
                tail_dur = self._get_audio_duration(tail_path)

                sync_segments.append(SyncSegment(
                    dst_start=dst_time,
                    dst_end=dst_time + tail_dur,
                    src_start=last_src_end,
                    src_end=video_duration,
                    speed=1.0,
                ))

        return audio_files, sync_segments

    def _merge_sync_segments(
        self,
        segments: List[SyncSegment],
        tolerance: float = 1e-3,
    ) -> List[SyncSegment]:
        """Merge adjacent segments with same speed."""
        if not segments:
            return []

        merged: List[SyncSegment] = []
        for seg in segments:
            if merged:
                last = merged[-1]
                same_speed = abs(seg.speed - last.speed) < tolerance
                contiguous_dst = abs(seg.dst_start - last.dst_end) < tolerance
                contiguous_src = abs(seg.src_start - last.src_end) < tolerance

                if same_speed and contiguous_dst and contiguous_src:
                    merged[-1] = SyncSegment(
                        dst_start=last.dst_start,
                        dst_end=seg.dst_end,
                        src_start=last.src_start,
                        src_end=seg.src_end,
                        speed=last.speed,
                    )
                    continue

            merged.append(seg)

        if len(segments) > len(merged):
            logger.info(
                "Merged %d sync segments into %d (%.1f%% reduction)",
                len(segments), len(merged), 100 * (1 - len(merged) / len(segments)),
            )

        return merged

    def _write_sync_timeline(
        self,
        path: str,
        segments: List[SyncSegment],
        video_duration: float,
        audio_duration: float,
    ) -> None:
        """Write sync_timeline.json."""
        timeline = {
            "version": 1,
            "source_video_duration": round(video_duration, 3),
            "voiceover_audio_duration": round(audio_duration, 3),
            "segments": [s.to_dict() for s in segments],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    # Audio helpers
    # ------------------------------------------------------------------ #

    def _pad_audio_to_duration(
        self,
        input_file: str,
        output_file: str,
        target_duration: float,
        work_dir: str,
    ) -> None:
        """Pad audio with silence to target duration."""
        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-af", "apad", "-t", f"{target_duration:.6f}",
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
        """Speed up audio using atempo filter chain."""
        atempo_filters = []
        remaining = speed

        while remaining > 2.0:
            atempo_filters.append("atempo=2.0")
            remaining /= 2.0

        while remaining < 0.5:
            atempo_filters.append("atempo=0.5")
            remaining /= 0.5

        if abs(remaining - 1.0) > 0.001:
            atempo_filters.append(f"atempo={remaining:.6f}")

        if not atempo_filters:
            shutil.copy2(input_file, output_file)
            return

        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-filter:a", ",".join(atempo_filters),
            "-t", f"{target_duration:.6f}",
            os.path.abspath(output_file),
        ]
        subprocess.run(cmd, cwd=work_dir, capture_output=True, check=True)

    def _concat_audio_files(
        self,
        audio_files: List[str],
        output_file: str,
        work_dir: str,
    ) -> None:
        """Concatenate wav files into m4a."""
        if not audio_files:
            raise ValueError("No audio files to concatenate")

        list_file = os.path.join(work_dir, "audio_list.txt")
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for path in audio_files:
                    escaped = os.path.basename(path).replace("'", "\\'")
                    f.write(f"file '{escaped}'\n")

            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", os.path.basename(list_file),
                "-c:a", "aac", "-b:a", "192k",
                os.path.abspath(output_file),
            ]
            subprocess.run(cmd, cwd=work_dir, capture_output=True, check=True)
        finally:
            try:
                os.remove(list_file)
            except OSError:
                pass

    def _transcode_to_wav(self, input_file: str, output_file: str) -> None:
        """Transcode to 16-bit mono PCM wav."""
        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-ar", str(self.sample_rate), "-ac", "1", "-c:a", "pcm_s16le",
            os.path.abspath(output_file),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    def _get_audio_duration(self, path: str) -> float:
        """Get audio duration in seconds."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except Exception as e:
            logger.error("Failed to get audio duration for %s: %s", path, e)
            return 0.0

    def _get_video_duration(self, path: str) -> Optional[float]:
        """Get video duration in seconds."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except Exception as e:
            logger.warning("Failed to get video duration for %s: %s", path, e)
            return None

    def _generate_silence_wav(self, output_file: str, duration: float) -> None:
        """Generate silence wav file."""
        duration = max(0.0, float(duration))
        if duration <= 0:
            return

        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=mono:sample_rate={self.sample_rate}",
            "-t", f"{duration:.3f}", "-ar", str(self.sample_rate),
            "-ac", "1", "-c:a", "pcm_s16le",
            os.path.abspath(output_file),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
