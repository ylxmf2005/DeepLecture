"""
Voiceover Use Case - Business logic for voiceover generation.

This UseCase orchestrates:
1. SRT parsing → SubtitleSegment[]
2. Concurrent TTS synthesis → WAV files
3. Plan stage (pure) → AlignmentPlan
4. Apply stage (I/O) → audio_files + SyncSegment[]
5. Concatenation → M4A
6. Timeline merge → sync_timeline.json

Design Decisions:
- Plan+Apply split enables pure function testing of alignment logic
- All thresholds are imported from Domain layer (no magic numbers here)
- Actual durations are used for speed calculation (matches legacy, handles ffmpeg errors)
- Concurrent TTS with failure threshold and silence fallback
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import time
from typing import TYPE_CHECKING

from deeplecture.domain.entities import (
    LEADING_SILENCE_THRESHOLD,
    SLOT_SKIP_THRESHOLD,
    SubtitleSegment,
    SyncSegment,
    calculate_slot_end,
    merge_sync_segments,
)
from deeplecture.use_cases.dto.voiceover import (
    AlignmentPlan,
    VoiceoverResult,
)
from deeplecture.use_cases.shared.subtitle import get_preferred_subtitle_languages

if TYPE_CHECKING:
    from deeplecture.config.settings import VoiceoverConfig
    from deeplecture.use_cases.dto.voiceover import GenerateVoiceoverRequest
    from deeplecture.use_cases.interfaces import (
        AudioProcessorProtocol,
        FileStorageProtocol,
        ParallelRunnerProtocol,
        SubtitleStorageProtocol,
        TTSProtocol,
    )
    from deeplecture.use_cases.interfaces.tts_provider import TTSProviderProtocol

logger = logging.getLogger(__name__)


class VoiceoverUseCase:
    """
    Voiceover generation use case.

    Orchestrates the complete voiceover generation pipeline:
    - SRT parsing and segment extraction
    - Concurrent TTS synthesis with retry and fallback
    - Audio alignment using Plan+Apply pattern
    - Timeline generation for playback-side sync

    This class contains ALL business logic and policy decisions:
    - Retry policy, failure thresholds, silence fallback
    - Alignment thresholds (imported from Domain)
    - Output naming and structure
    """

    def __init__(
        self,
        *,
        audio: AudioProcessorProtocol,
        file_storage: FileStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        tts_provider: TTSProviderProtocol,
        parallel_runner: ParallelRunnerProtocol,
        config: VoiceoverConfig,
    ) -> None:
        """
        Initialize VoiceoverUseCase.

        Args:
            audio: Audio processor for ffmpeg operations
            file_storage: File storage operations abstraction
            subtitle_storage: Subtitle storage for transcript loading
            tts_provider: TTS provider for runtime model selection
            parallel_runner: Parallel execution adapter (injected via DI)
            config: Voiceover configuration (injected from settings)
        """
        self._audio = audio
        self._file_storage = file_storage
        self._subtitles = subtitle_storage
        self._tts_provider = tts_provider
        self._parallel = parallel_runner
        self._config = config

    def generate(self, request: GenerateVoiceoverRequest) -> VoiceoverResult:
        """
        Generate voiceover audio and sync timeline.

        Args:
            request: Generation parameters

        Returns:
            VoiceoverResult with paths to generated files

        Raises:
            ValueError: If no valid subtitle segments found
            RuntimeError: If too many TTS failures
        """
        self._file_storage.makedirs(request.output_dir)

        # Step 1: Load subtitle segments (prefer enhanced, fallback to base)
        segments = self._load_subtitle_segments(request.content_id, request.subtitle_language)
        if not segments:
            raise ValueError(
                f"No valid subtitle segments found for content_id={request.content_id} "
                f"subtitle_language={request.subtitle_language}"
            )

        # Sort by (start, index) for stable ordering (matches legacy)
        segments.sort(key=lambda s: (s.start, s.index))

        # Setup paths
        base_name = request.audio_basename or f"voiceover_{request.language}"
        segments_dir = os.path.join(request.output_dir, f"{base_name}_segments")
        self._file_storage.makedirs(segments_dir)

        voiceover_audio_path = os.path.join(request.output_dir, f"{base_name}.m4a")
        timeline_path = os.path.join(request.output_dir, f"{base_name}_sync_timeline.json")

        # Get video duration (best-effort, 0.0 on failure)
        try:
            video_duration = self._audio.probe_duration_seconds(request.video_path)
        except (RuntimeError, OSError) as e:
            logger.warning("Failed to get video duration for %s: %s", request.video_path, e)
            video_duration = 0.0

        logger.info(
            "Starting voiceover generation: %d segments, video_duration=%.2fs",
            len(segments),
            video_duration,
        )

        try:
            # Step 2: Synthesize TTS for each segment
            raw_wav_paths = self._synthesize_segments_concurrently(segments, segments_dir, tts_model=request.tts_model)

            # Step 3: Probe raw durations
            raw_durations = [self._audio.probe_duration_seconds(p) for p in raw_wav_paths]

            # Step 4: Plan alignment (pure function)
            plan = self._plan_alignment(
                segments=segments,
                raw_wav_paths=raw_wav_paths,
                raw_durations=raw_durations,
                video_duration=video_duration,
                segments_dir=segments_dir,
            )

            # Fail-fast if no valid clips (all slots skipped or invalid timings)
            if not plan.clips:
                msg = "No valid subtitle slots for voiceover generation (all segments skipped or invalid)"
                raise ValueError(msg)

            # Step 5: Apply alignment (I/O operations)
            audio_files, sync_segments = self._apply_alignment_plan(plan)

            # Step 6: Concatenate to M4A
            self._audio.concat_wavs_to_m4a(audio_files, voiceover_audio_path)

            # Step 7: Get final audio duration
            audio_duration = self._audio.probe_duration_seconds(voiceover_audio_path)

            # Step 8: Merge adjacent same-speed segments
            merged_segments = merge_sync_segments(sync_segments)

            # Step 9: Write timeline JSON
            self._write_sync_timeline(
                timeline_path,
                merged_segments,
                video_duration,
                audio_duration,
            )

            logger.info(
                "Voiceover generation complete: audio=%s, timeline=%s, %d sync segments (merged from %d)",
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

        finally:
            # Clean up intermediate files
            with contextlib.suppress(OSError):
                self._file_storage.remove_dir(segments_dir)

    def _load_subtitle_segments(self, content_id: str, language: str) -> list[SubtitleSegment]:
        """
        Load subtitle segments with fallback, filtering empty text before fallback decision.

        Unlike the generic shared utility which only checks segment existence,
        voiceover requires non-empty text. We iterate through candidates and
        apply text filtering BEFORE deciding to fallback, ensuring we don't
        skip valid base subtitles when enhanced ones have empty text.
        """
        for lang_key in get_preferred_subtitle_languages(language):
            segments = self._subtitles.load(content_id, lang_key)
            if not segments:
                continue

            out: list[SubtitleSegment] = []
            for idx, seg in enumerate(segments):
                # Normalize all whitespace (newlines, tabs, multiple spaces) to single space
                text = " ".join((seg.text or "").split())
                if not text:
                    continue
                out.append(
                    SubtitleSegment(
                        index=idx,
                        start=seg.start,
                        end=seg.end,
                        text=text,
                    )
                )

            if out:
                logger.info(
                    "Loaded subtitles: content_id=%s, language=%s, segments=%d",
                    content_id,
                    lang_key,
                    len(out),
                )
                return out

        return []

    # =========================================================================
    # STEP 2: CONCURRENT TTS SYNTHESIS
    # =========================================================================

    def _synthesize_segments_concurrently(
        self,
        segments: list[SubtitleSegment],
        segments_dir: str,
        *,
        tts_model: str | None,
    ) -> list[str]:
        """
        Synthesize TTS for all segments concurrently.

        Uses ParallelRunner for parallel execution.
        Failed segments are replaced with silence.

        Args:
            segments: List of subtitle segments
            segments_dir: Directory for intermediate files
            tts_model: TTS model ID (None = use default)

        Returns:
            List of WAV file paths (one per segment)

        Raises:
            RuntimeError: If failure ratio exceeds threshold
        """
        total = len(segments)
        if total == 0:
            return []

        # Track errors via closure (thread-safe: each index written once)
        errors: list[Exception | None] = [None] * total

        def process_segment(item: tuple[int, SubtitleSegment]) -> str | None:
            """Process a single segment with retry."""
            idx, seg = item
            wav_path = os.path.join(segments_dir, f"subtitle_{idx + 1}.wav")

            last_error: Exception | None = None

            for attempt in range(1, self._config.max_retries + 2):
                try:
                    tts = self._get_tts_instance(tts_model)
                    audio_bytes = tts.synthesize(seg.text)

                    if not audio_bytes:
                        raise RuntimeError("TTS returned empty audio")

                    # Get file extension from TTS
                    ext = getattr(tts, "file_extension", ".wav") or ".wav"
                    ext = ext if ext.startswith(".") else f".{ext}"

                    # Always transcode to ensure consistent sample_rate/channels
                    # (TTS may return different formats, e.g., 24kHz vs 44.1kHz)
                    tmp_path = os.path.join(segments_dir, f"subtitle_{idx + 1}_raw{ext}")
                    self._file_storage.write_bytes(tmp_path, audio_bytes)
                    self._audio.transcode_to_wav(
                        tmp_path,
                        wav_path,
                        sample_rate=self._config.sample_rate,
                    )
                    with contextlib.suppress(OSError):
                        self._file_storage.remove_file(tmp_path)

                    # Validate duration
                    dur = self._audio.probe_duration_seconds(wav_path)
                    if dur <= 0:
                        raise RuntimeError("Generated audio has invalid duration")

                    return wav_path

                except Exception as e:
                    last_error = e
                    logger.warning(
                        "TTS failed for segment %d (attempt %d/%d): %s",
                        idx + 1,
                        attempt,
                        self._config.max_retries + 1,
                        e,
                    )
                    if attempt <= self._config.max_retries:
                        wait_time = self._config.calculate_retry_wait_time(attempt)
                        time.sleep(wait_time)

            # All retries exhausted - record error and return None
            errors[idx] = last_error
            return None

        # Execute with ParallelRunner
        items = list(enumerate(segments))
        results = self._parallel.map_ordered(
            items,
            process_segment,
            group="voiceover_tts",
        )

        # Check failure ratio (triggers when more than threshold proportion fail)
        failures = sum(1 for e in errors if e is not None)
        if failures > total * self._config.failure_threshold_ratio:
            raise RuntimeError(f"Too many TTS failures: {failures}/{total}")

        # Build final wav_paths, generating silence for failed segments
        wav_paths: list[str] = []
        for idx, path in enumerate(results):
            wav_path = os.path.join(segments_dir, f"subtitle_{idx + 1}.wav")
            if path is None:
                logger.warning("Generating silence for failed segment %d", idx + 1)
                self._audio.generate_silence_wav(
                    wav_path,
                    duration=self._config.silence_fallback_duration,
                    sample_rate=self._config.sample_rate,
                )
                wav_paths.append(wav_path)
            elif not self._file_storage.file_exists(path):
                raise RuntimeError(f"TTS output missing for segment {idx + 1}")
            else:
                wav_paths.append(path)

        return wav_paths

    def _get_tts_instance(self, tts_model: str | None) -> TTSProtocol:
        """Get TTS instance from provider."""
        return self._tts_provider.get(tts_model)

    # =========================================================================
    # STEP 4: PLAN ALIGNMENT (PURE FUNCTION)
    # =========================================================================

    def _plan_alignment(
        self,
        *,
        segments: list[SubtitleSegment],
        raw_wav_paths: list[str],
        raw_durations: list[float],
        video_duration: float,
        segments_dir: str,
    ) -> AlignmentPlan:
        """
        Plan audio alignment operations (pure computation, no I/O).

        New architecture: audio is always kept at constant speed.
        For each subtitle slot, we only copy the raw TTS clip.
        Playback speed is derived as: speed = slot_duration / tts_duration.

        Args:
            segments: Sorted subtitle segments
            raw_wav_paths: Paths to raw TTS WAV files
            raw_durations: Durations of raw TTS files
            video_duration: Total video duration
            segments_dir: Directory for output files

        Returns:
            AlignmentPlan with all clips to process
        """
        plan = AlignmentPlan()

        if not segments:
            return plan

        n = len(segments)
        clip_counter = 0

        # Leading silence: video 0 → first subtitle
        first_start = max(0.0, segments[0].start)
        if first_start > LEADING_SILENCE_THRESHOLD:
            output_path = os.path.join(segments_dir, f"silence_{clip_counter}.wav")
            plan.add_clip(
                src_start=0.0,
                src_end=first_start,
                kind="silence",
                input_path=None,
                output_path=output_path,
                target_duration=first_start,
            )
            clip_counter += 1

        # Process each segment: just copy raw TTS, no processing
        for i, seg in enumerate(segments):
            # Calculate slot end
            next_seg = segments[i + 1] if i < n - 1 else None
            slot_end = calculate_slot_end(seg, next_seg)
            slot_duration = max(0.0, slot_end - seg.start)

            # Skip near-zero slots (matches legacy)
            if slot_duration < SLOT_SKIP_THRESHOLD:
                logger.warning("Skipping near-zero slot for segment %d", i + 1)
                continue

            raw_dur = raw_durations[i]
            if raw_dur <= 0:
                raise RuntimeError(f"Invalid audio duration for segment {i + 1}")

            input_wav = raw_wav_paths[i]
            output_path = os.path.join(segments_dir, f"adjusted_{i + 1}.wav")

            # Copy raw TTS audio as-is (frontend handles video speed adjustment)
            plan.add_clip(
                src_start=seg.start,
                src_end=slot_end,
                kind="copy",
                input_path=input_wav,
                output_path=output_path,
                target_duration=raw_dur,
            )

        # Trailing silence: last slot → video end
        if plan.clips and video_duration > 0:
            last_src_end = plan.clips[-1].src_end
            if video_duration > last_src_end + LEADING_SILENCE_THRESHOLD:
                tail_duration = video_duration - last_src_end
                output_path = os.path.join(segments_dir, "silence_tail.wav")
                plan.add_clip(
                    src_start=last_src_end,
                    src_end=video_duration,
                    kind="silence",
                    input_path=None,
                    output_path=output_path,
                    target_duration=tail_duration,
                )

        return plan

    # =========================================================================
    # STEP 5: APPLY ALIGNMENT (I/O OPERATIONS)
    # =========================================================================

    def _apply_alignment_plan(
        self,
        plan: AlignmentPlan,
    ) -> tuple[list[str], list[SyncSegment]]:
        """
        Apply alignment plan by executing audio operations.

        This is the I/O counterpart to _plan_alignment.
        It executes each operation and derives speed from slot/tts duration.

        Args:
            plan: Alignment plan from _plan_alignment

        Returns:
            Tuple of (audio_files, sync_segments)
        """
        audio_files: list[str] = []
        sync_segments: list[SyncSegment] = []
        dst_time = 0.0

        for clip in plan.clips:
            op = clip.op

            # Execute operation based on kind (only silence and copy now)
            if op.kind == "silence":
                self._audio.generate_silence_wav(
                    op.output_path,
                    duration=op.target_duration,
                    sample_rate=self._config.sample_rate,
                )
                # Probe silence for accuracy verification
                adj_dur = self._audio.probe_duration_seconds(op.output_path)
            elif op.kind == "copy":
                if op.input_path is None:
                    msg = "Copy operation must have input path"
                    raise ValueError(msg)
                self._file_storage.copy_file(op.input_path, op.output_path)
                # Copy uses already-probed duration from planning stage
                adj_dur = op.target_duration
            else:
                msg = f"Unknown operation kind: {op.kind}"
                raise ValueError(msg)

            # Hard fail on invalid duration (corrupted file, NaN, Inf, or generation failure)
            src_delta = clip.src_end - clip.src_start
            if not math.isfinite(adj_dur) or adj_dur < 1e-6:
                msg = f"Invalid audio duration {adj_dur}s for {op.output_path}"
                raise RuntimeError(msg)
            if not math.isfinite(src_delta) or src_delta < 1e-6:
                msg = f"Invalid slot duration {src_delta}s for segment {clip.src_start}-{clip.src_end}"
                raise RuntimeError(msg)

            audio_files.append(op.output_path)

            # Calculate speed from slot/tts duration
            actual_speed = src_delta / adj_dur

            sync_segments.append(
                SyncSegment(
                    dst_start=dst_time,
                    dst_end=dst_time + adj_dur,
                    src_start=clip.src_start,
                    src_end=clip.src_end,
                    speed=actual_speed,
                )
            )
            dst_time += adj_dur

        return audio_files, sync_segments

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _write_sync_timeline(
        self,
        path: str,
        segments: list[SyncSegment],
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
        self._file_storage.write_text(path, json.dumps(timeline, ensure_ascii=False, indent=2))
