"""
Faster-whisper based subtitle engine for cross-platform support.
Faster-whisper is 4x faster than OpenAI Whisper with same accuracy.
Works well on Windows, Linux and macOS without requiring compilation.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import timedelta
from typing import Any, ClassVar, Dict, List, Optional

from deeplecture.transcription.whisper_engine import SubtitleEngine


class FasterWhisperEngine(SubtitleEngine):
    """
    Faster-whisper based subtitle generator with model caching.

    Features:
    - Class-level model cache to avoid repeated loading (saves 5-10s per call)
    - Thread-safe model access
    - 4x faster than original OpenAI Whisper
    - Uses less memory
    - Works on Windows/Linux/Mac without compilation
    - Supports GPU acceleration with CUDA
    """

    # Class-level model cache (shared across instances)
    _model_cache: ClassVar[Dict[str, Any]] = {}
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        *,
        model_size: str = "medium",
        device: str = "auto",
        compute_type: str = "auto",
        download_root: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the Faster-whisper engine.

        Args:
            model_size: Size of model to use (tiny, base, small, medium, large, large-v2, large-v3)
            device: Device to use ("cpu", "cuda", "auto")
            compute_type: Compute type ("int8", "float16", "float32", "auto")
            download_root: Directory to download models to
            logger: Logger instance
        """
        self._logger = logger or logging.getLogger(__name__)
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._download_root = download_root or os.path.expanduser("~/.cache/whisper")
        self._model = None

    def _get_cache_key(self) -> str:
        """Generate a cache key for the current model settings."""
        return f"{self._model_size}_{self._device}_{self._compute_type}"

    def _ensure_model(self) -> bool:
        """
        Lazy load the model on first use with caching.

        Uses class-level cache to avoid reloading the same model configuration
        across multiple instances, saving 5-10 seconds per call.
        """
        if self._model is not None:
            return True

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            self._logger.error(
                "faster-whisper is not installed. Install it with: "
                "pip install faster-whisper"
            )
            return False

        # Check the cache (thread-safe)
        cache_key = self._get_cache_key()

        with self._cache_lock:
            if cache_key in self._model_cache:
                self._model = self._model_cache[cache_key]
                self._logger.info(
                    "Using cached faster-whisper model: %s", cache_key
                )
                return True

        try:
            # Auto-detect device if set to auto
            device = self._device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"

            # Auto-select compute type based on device
            compute_type = self._compute_type
            if compute_type == "auto":
                if device == "cuda":
                    compute_type = "float16"
                else:
                    compute_type = "int8"

            self._logger.info(
                "Loading faster-whisper model: size=%s, device=%s, compute=%s",
                self._model_size, device, compute_type
            )

            model = WhisperModel(
                self._model_size,
                device=device,
                compute_type=compute_type,
                download_root=self._download_root,
            )

            # Save into the cache (thread-safe)
            with self._cache_lock:
                # Double-check to avoid duplicate loads
                if cache_key not in self._model_cache:
                    self._model_cache[cache_key] = model
                    self._logger.info(
                        "Faster-whisper model loaded and cached: %s", cache_key
                    )
                else:
                    # Another thread loaded it first; reuse the cached model
                    model = self._model_cache[cache_key]
                    self._logger.info(
                        "Using model cached by another thread: %s", cache_key
                    )

            self._model = model
            return True

        except Exception as e:
            self._logger.error("Failed to load faster-whisper model: %s", e)
            return False

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the model cache (free memory)."""
        with cls._cache_lock:
            cls._model_cache.clear()
            logging.getLogger(__name__).info("Faster-whisper model cache cleared")

    @classmethod
    def get_cache_info(cls) -> Dict[str, Any]:
        """Return cache inspection info."""
        with cls._cache_lock:
            return {
                "cached_models": list(cls._model_cache.keys()),
                "count": len(cls._model_cache),
            }

    def generate_subtitles(
        self,
        video_path: str,
        output_path: str,
        language: str = "en",
    ) -> bool:
        """
        Generate subtitles for the given video file.

        Args:
            video_path: Path to input video/audio file
            output_path: Path where SRT file should be saved
            language: Language code for transcription

        Returns:
            True if successful, False otherwise
        """
        # Ensure model is loaded
        if not self._ensure_model():
            return False

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            self._logger.info(
                "Starting transcription: %s -> %s (language: %s)",
                video_path, output_path, language
            )

            # Transcribe with faster-whisper
            # Note: faster-whisper handles audio extraction internally using PyAV
            #
            # Anti-hallucination settings (see _archive/notes/whisper.md):
            # - beam_size=1: lowest hallucination rate (arXiv 2501.11378)
            # - condition_on_previous_text=False: prevents hallucination propagation (WhisperX default)
            # - Tighter VAD parameters: more aggressive silence filtering
            assert self._model is not None  # Guaranteed by _ensure_model() above
            segments, info = self._model.transcribe(
                video_path,
                language=language,
                beam_size=1,  # Minimizes hallucination (was 5)
                best_of=1,    # Consistent with beam_size=1
                patience=1,
                length_penalty=1,
                temperature=0,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=False,  # Prevents hallucination propagation (was True)
                initial_prompt=None,
                word_timestamps=False,
                prepend_punctuations="\"'([{-",
                append_punctuations="\"'.,!?:)]}",
                vad_filter=True,  # Voice Activity Detection for better accuracy
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    max_speech_duration_s=float('inf'),
                    min_silence_duration_ms=500,  # More aggressive (was 2000)
                    speech_pad_ms=200,  # Tighter padding (was 400)
                ),
            )

            self._logger.info(
                "Detected language: %s (probability: %.2f)",
                info.language, info.language_probability
            )

            # Convert segments to SRT format
            srt_content = self._segments_to_srt(segments)

            # Write SRT file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

            self._logger.info("Subtitles generated successfully: %s", output_path)
            return True

        except Exception as e:
            self._logger.error("Transcription failed: %s", e)
            return False

    def _segments_to_srt(self, segments) -> str:
        """Convert faster-whisper segments to SRT format."""
        srt_lines = []

        for i, segment in enumerate(segments, start=1):
            # Convert timestamps to SRT format (HH:MM:SS,mmm)
            start_time = self._seconds_to_srt_time(segment.start)
            end_time = self._seconds_to_srt_time(segment.end)

            # Clean up text
            text = segment.text.strip()

            # Add SRT entry
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(text)
            srt_lines.append("")  # Empty line between entries

        return "\n".join(srt_lines)

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = int(td.total_seconds() % 60)
        # Round milliseconds properly to avoid floating point precision issues
        millis = round((td.total_seconds() % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class FasterWhisperBatchEngine(FasterWhisperEngine):
    """
    Enhanced version with batch processing for multiple files.
    Useful for processing multiple videos efficiently.
    """

    def generate_subtitles_batch(
        self,
        video_paths: List[str],
        output_dir: str,
        language: str = "en",
    ) -> Dict[str, bool]:
        """
        Generate subtitles for multiple videos.

        Args:
            video_paths: List of video file paths
            output_dir: Directory to save SRT files
            language: Language code for transcription

        Returns:
            Dictionary mapping video path to success status
        """
        results = {}

        # Ensure model is loaded once for all files
        if not self._ensure_model():
            return {path: False for path in video_paths}

        for video_path in video_paths:
            # Generate output filename
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}.srt")

            # Process individual file
            success = self.generate_subtitles(video_path, output_path, language)
            results[video_path] = success

        return results
