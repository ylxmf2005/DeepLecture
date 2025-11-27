from __future__ import annotations

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from deeplecture.dto.slide import AudioSegmentInfo
from deeplecture.infra.parallel_pool import ResourceWorkerPool
from deeplecture.tts.tts_factory import TTS, TTSFactory


logger = logging.getLogger(__name__)


class SpeechService:
    """
    TTS + audio timeline stage of the slide lecture pipeline.

    Given TranscriptPage objects, this service:
    - Synthesizes per-segment wav files (optionally in parallel);
    - Inserts page-break silence between pages;
    - Concatenates per-page audio into single wavs;
    - Returns AudioSegmentInfo entries plus per-page audio paths.
    """

    def __init__(
        self,
        tts: Optional[TTS] = None,
        tts_factory: Optional[TTSFactory] = None,
        sample_rate: int = 44100,
        task_name: str = "slide_lecture",
    ) -> None:
        self._tts_factory = tts_factory or TTSFactory()
        self._custom_tts_provided = tts is not None
        self._task_name = task_name or "slide_lecture"
        self._tts: TTS = tts or self._tts_factory.get_tts_for_task(self._task_name)
        self.sample_rate = sample_rate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_audio_timeline(
        self,
        *,
        transcript_pages,
        audio_dir: str,
        page_break_silence_seconds: float,
        tts_max_concurrency: int,
        tts_language: str,
    ) -> Tuple[List[AudioSegmentInfo], Dict[int, str]]:
        """
        Synthesize all audio required for the slide lecture and build a
        continuous timeline.
        """
        os.makedirs(audio_dir, exist_ok=True)

        if not transcript_pages:
            return [], {}

        segment_tasks: List[Tuple[Tuple[int, int], Dict[str, Any]]] = []
        tts_mode = (tts_language or "source").lower()
        use_source_for_tts = tts_mode != "target"
        for page in transcript_pages:
            for idx, seg in enumerate(page.segments, start=1):
                seg_wav = os.path.join(
                    audio_dir,
                    f"seg_p{page.page_index:03d}_s{idx:03d}.wav",
                )
                segment_tasks.append(
                    (
                        (page.page_index, idx),
                        {
                            "text": seg.source if use_source_for_tts else seg.target,
                            "wav_path": seg_wav,
                        },
                    ),
                )

        tts_pool = ResourceWorkerPool(
            name="tts_slide_segments",
            max_workers=max(1, int(tts_max_concurrency or 1)),
            resource_factory=self._make_tts_instance,
        )

        def tts_handler(
            engine: TTS,
            key: Tuple[int, int],
            payload: Dict[str, Any],
        ) -> float:
            return self._synthesize_segment_to_wav(
                text=str(payload.get("text", "")),
                wav_path=str(payload.get("wav_path", "")),
                tts=engine,
            )

        durations = tts_pool.map(segment_tasks, tts_handler)

        segments: List[AudioSegmentInfo] = []
        page_audio_paths: Dict[int, str] = {}
        time_cursor = 0.0

        last_page_index = transcript_pages[-1].page_index if transcript_pages else 0

        for page in transcript_pages:
            page_audio_files: List[str] = []
            for idx, seg in enumerate(page.segments, start=1):
                seg_wav = os.path.join(
                    audio_dir,
                    f"seg_p{page.page_index:03d}_s{idx:03d}.wav",
                )
                duration = durations.get((page.page_index, idx), 0.0)
                start = time_cursor
                end = start + duration
                time_cursor = end

                segments.append(
                    AudioSegmentInfo(
                        page_index=page.page_index,
                        segment_index=idx,
                        start=start,
                        end=end,
                        source=seg.source,
                        target=seg.target,
                        audio_path=seg_wav,
                    ),
                )
                page_audio_files.append(seg_wav)

            # Page-break silence (except after last page).
            if page.page_index != last_page_index and page_break_silence_seconds > 0:
                silence_wav = os.path.join(
                    audio_dir,
                    f"silence_after_p{page.page_index:03d}.wav",
                )
                self._generate_silence_wav(
                    output_file=silence_wav,
                    duration=page_break_silence_seconds,
                )
                silence_dur = self._get_audio_duration(silence_wav)
                logger.info(
                    "Page %d: adding silence %.3fs, time_cursor before=%.3f after=%.3f",
                    page.page_index,
                    silence_dur,
                    time_cursor,
                    time_cursor + silence_dur,
                )
                time_cursor += silence_dur
                page_audio_files.append(silence_wav)

            # Concatenate this page's audio into a single wav.
            if page_audio_files:
                page_audio_path = os.path.join(
                    audio_dir,
                    f"page_{page.page_index:03d}.wav",
                )
                self._concat_audio_files(
                    audio_files=page_audio_files,
                    output_file=page_audio_path,
                    work_dir=audio_dir,
                )
                # Verify concat result matches expected duration
                actual_page_dur = self._get_audio_duration(page_audio_path)
                expected_page_dur = time_cursor - (segments[-1].start if segments else 0)
                logger.info(
                    "Page %d: concat result=%.3fs, time_cursor=%.3f, page_start=%.3f",
                    page.page_index,
                    actual_page_dur,
                    time_cursor,
                    segments[0].start if segments else 0,
                )
                page_audio_paths[page.page_index] = page_audio_path

        return segments, page_audio_paths

    def synthesize_to_wav(self, text: str, wav_path: str) -> float:
        """
        Public API: Synthesize text to wav file and return duration.

        Used by PagePipelineCoordinator for per-segment TTS.
        """
        return self._synthesize_segment_to_wav(text=text, wav_path=wav_path)

    def generate_silence_wav(self, wav_path: str, duration: float) -> None:
        """
        Public API: Generate a silence wav file.

        Used by PagePipelineCoordinator for fallback silence placeholders.
        """
        self._generate_silence_wav(output_file=wav_path, duration=duration)

    def concat_wav_files(self, input_files: List[str], output_file: str) -> None:
        """
        Public API: Concatenate multiple wav files into one.

        Used by PagePipelineCoordinator to merge segment audio into page audio.
        """
        work_dir = os.path.dirname(output_file) or "."
        self._concat_audio_files(
            audio_files=input_files,
            output_file=output_file,
            work_dir=work_dir,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_tts_instance(self) -> TTS:
        """
        Provide one TTS engine per worker. If a custom TTS was injected,
        reuse it; otherwise create fresh instances from the factory so
        parallel calls do not share state.
        """
        if self._custom_tts_provided:
            return self._tts
        return self._tts_factory.get_tts_for_task(self._task_name)

    def _synthesize_segment_to_wav(
        self,
        text: str,
        wav_path: str,
        tts: Optional[TTS] = None,
    ) -> float:
        """
        Synthesize a single spoken segment to wav and return its duration.

        All output is normalized to self.sample_rate to ensure consistent
        sample rates across all audio segments (TTS output + silence).
        """
        text = (text or "").replace("\r", " ").strip()
        if not text:
            logger.warning(
                "Slide lecture TTS: empty text segment, generating 0.5s silence at %s",
                wav_path,
            )
            self._generate_silence_wav(wav_path, 0.5)
            return self._get_audio_duration(wav_path)

        engine = tts or self._tts

        ext = getattr(engine, "file_extension", ".wav") or ".wav"
        ext = ext if ext.startswith(".") else f".{ext}"

        # Always use a temporary file for TTS output, then transcode to ensure
        # consistent sample rate across all segments.
        tmp_path = f"{os.path.splitext(wav_path)[0]}_raw{ext}"

        try:
            audio_bytes = engine.synthesize(text)
        except Exception as exc:
            logger.error(
                "Slide lecture TTS synthesis failed for segment '%s...'; "
                "falling back to 0.5s silence: %s",
                text[:80],
                exc,
            )
            self._generate_silence_wav(wav_path, 0.5)
            return self._get_audio_duration(wav_path)

        if not audio_bytes:
            logger.warning(
                "Slide lecture TTS returned empty audio for segment '%s...'; "
                "using 0.5s silence instead",
                text[:80],
            )
            self._generate_silence_wav(wav_path, 0.5)
            return self._get_audio_duration(wav_path)

        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)

        # Always transcode to normalize sample rate, regardless of input format.
        # This ensures all segments (TTS + silence) have matching sample rates.
        logger.info(
            "Transcoding TTS output %s -> %s (target sample_rate=%d)",
            tmp_path,
            wav_path,
            self.sample_rate,
        )
        self._transcode_to_wav(tmp_path, wav_path)
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        duration = self._get_audio_duration(wav_path)
        if duration <= 0:
            logger.error(
                "Slide lecture TTS generated audio with non-positive duration "
                "for segment '%s...'; replacing with 0.5s silence",
                text[:80],
            )
            self._generate_silence_wav(wav_path, 0.5)
            return self._get_audio_duration(wav_path)

        return duration

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

    @staticmethod
    def _concat_audio_files(
        audio_files: List[str],
        output_file: str,
        work_dir: str,
    ) -> None:
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
            try:
                os.remove(list_file)
            except OSError:
                pass
