"""
Page pipeline coordinator for slide lecture generation.

Coordinates pipelined parallel execution of TTS and video segment
generation as each page transcript completes.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Dict, List, Tuple, TYPE_CHECKING

from deeplecture.dto.slide import PageAudioArtifacts, PageVideoArtifacts, TranscriptPage

if TYPE_CHECKING:
    from deeplecture.services.slide_speech_service import SpeechService
    from deeplecture.services.slide_video_composer import VideoComposer

logger = logging.getLogger(__name__)


class PagePipelineCoordinator:
    """
    Coordinates pipelined TTS and video generation.

    As each page transcript completes, immediately starts:
    1. TTS synthesis for that page's segments
    2. Video segment generation (chained after TTS completes)

    This enables overlapping of LLM generation with TTS/video work.
    """

    def __init__(
        self,
        *,
        speech_service: "SpeechService",
        video_composer: "VideoComposer",
        page_images: Dict[int, str],
        audio_dir: str,
        video_segments_dir: str,
        tts_language: str = "source",
        tts_workers: int = 2,
        video_workers: int = 1,
    ):
        self._speech_service = speech_service
        self._video_composer = video_composer
        self._page_images = page_images
        self._audio_dir = audio_dir
        self._video_segments_dir = video_segments_dir
        self._tts_language = tts_language

        # Thread pools for parallel TTS/video work
        self._tts_pool = ThreadPoolExecutor(
            max_workers=max(1, tts_workers),
            thread_name_prefix="tts_pipeline"
        )
        self._video_pool = ThreadPoolExecutor(
            max_workers=max(1, video_workers),
            thread_name_prefix="video_pipeline"
        )

        # Track futures for each page
        self._audio_futures: Dict[int, Future[PageAudioArtifacts]] = {}
        self._video_futures: Dict[int, Future[PageVideoArtifacts]] = {}

        # Track errors
        self._errors: Dict[int, Exception] = {}

    def submit(self, page: TranscriptPage) -> None:
        """
        Submit a completed transcript for TTS and video generation.

        Called as callback from TranscriptService.stream_pages().
        """
        page_index = page.page_index
        image_path = self._page_images.get(page_index)

        if not image_path:
            logger.error(
                "No image found for page %d, skipping pipeline",
                page_index
            )
            return

        logger.info(
            "Submitting page %d to TTS pipeline",
            page_index
        )

        # Submit TTS task
        audio_future = self._tts_pool.submit(
            self._render_page_audio,
            page=page,
        )
        self._audio_futures[page_index] = audio_future

        # Chain video task to run after TTS completes
        def on_audio_complete(fut: Future[PageAudioArtifacts]) -> None:
            try:
                audio_artifacts = fut.result()

                logger.info(
                    "Page %d TTS complete (%.2fs), submitting to video pipeline",
                    page_index, audio_artifacts.page_duration
                )

                video_future = self._video_pool.submit(
                    self._build_page_segment,
                    page_index=page_index,
                    image_path=image_path,
                    audio_path=audio_artifacts.page_audio_path,
                    duration=audio_artifacts.page_duration,
                )
                self._video_futures[page_index] = video_future

            except Exception as e:
                logger.error(
                    "TTS failed for page %d: %s",
                    page_index, e
                )
                self._errors[page_index] = e

        audio_future.add_done_callback(on_audio_complete)

    def wait_for_completion(
        self,
    ) -> Tuple[List[PageAudioArtifacts], List[str], Dict[int, Exception]]:
        """
        Wait for all submitted work to complete.

        Returns:
            (audio_artifacts, segment_paths, errors) tuple
            - audio_artifacts: List of PageAudioArtifacts in page order
            - segment_paths: List of video segment file paths in page order
            - errors: Dict of page_index -> Exception for any failures
        """
        # Wait for all audio tasks
        audio_artifacts: Dict[int, PageAudioArtifacts] = {}
        for page_index, future in self._audio_futures.items():
            try:
                artifacts = future.result()
                audio_artifacts[page_index] = artifacts
            except Exception as e:
                logger.error("Audio failed for page %d: %s", page_index, e)
                self._errors[page_index] = e

        # Wait for all video tasks
        segment_paths: Dict[int, str] = {}
        for page_index, future in self._video_futures.items():
            try:
                video_artifacts = future.result()
                segment_paths[page_index] = video_artifacts.segment_path
            except Exception as e:
                logger.error("Video failed for page %d: %s", page_index, e)
                self._errors[page_index] = e

        # Sort by page index
        sorted_audio = [
            audio_artifacts[idx]
            for idx in sorted(audio_artifacts.keys())
        ]
        sorted_segments = [
            segment_paths[idx]
            for idx in sorted(segment_paths.keys())
        ]

        return sorted_audio, sorted_segments, self._errors

    def shutdown(self) -> None:
        """Shutdown thread pools."""
        self._tts_pool.shutdown(wait=True)
        self._video_pool.shutdown(wait=True)

    def _render_page_audio(
        self,
        page: TranscriptPage,
    ) -> PageAudioArtifacts:
        """Render TTS audio for a single page."""
        os.makedirs(self._audio_dir, exist_ok=True)

        page_index = page.page_index
        use_source = (self._tts_language or "source").lower() != "target"

        # Synthesize each segment
        segment_durations: List[float] = []
        segment_wav_paths: List[str] = []

        for idx, seg in enumerate(page.segments, start=1):
            text = seg.source if use_source else seg.target
            if not text:
                continue

            wav_path = os.path.join(
                self._audio_dir,
                f"seg_p{page_index:03d}_s{idx:03d}.wav"
            )

            try:
                duration = self._speech_service.synthesize_to_wav(
                    text=text,
                    wav_path=wav_path,
                )
                segment_durations.append(duration)
                segment_wav_paths.append(wav_path)
            except Exception as e:
                logger.error(
                    "TTS segment failed for page %d seg %d: %s",
                    page_index, idx, e
                )
                # Create silence placeholder
                duration = 1.0
                self._speech_service.generate_silence_wav(
                    wav_path,
                    duration,
                )
                segment_durations.append(duration)
                segment_wav_paths.append(wav_path)

        # Concatenate segments into page audio
        page_audio_path = os.path.join(
            self._audio_dir,
            f"page_{page_index:03d}.wav"
        )

        if segment_wav_paths:
            self._speech_service.concat_wav_files(
                segment_wav_paths,
                page_audio_path,
            )
        else:
            # Create minimal silence if no segments
            self._speech_service.generate_silence_wav(
                page_audio_path,
                1.0,
            )
            segment_durations = [1.0]

        total_duration = sum(segment_durations)

        return PageAudioArtifacts(
            page_index=page_index,
            page_audio_path=page_audio_path,
            page_duration=total_duration,
            segment_durations=segment_durations,
        )

    def _build_page_segment(
        self,
        *,
        page_index: int,
        image_path: str,
        audio_path: str,
        duration: float,
    ) -> PageVideoArtifacts:
        """Build video segment for a single page."""
        os.makedirs(self._video_segments_dir, exist_ok=True)

        segment_path = os.path.join(
            self._video_segments_dir,
            f"page_{page_index:03d}.mp4"
        )

        self._video_composer.build_single_segment(
            image_path=image_path,
            audio_path=audio_path,
            duration=duration,
            output_path=segment_path,
        )

        return PageVideoArtifacts(
            page_index=page_index,
            segment_path=segment_path,
        )
