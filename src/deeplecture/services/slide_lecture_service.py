from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from deeplecture.app_context import AppContext, get_app_context
from deeplecture.config.config import load_config
from deeplecture.dto.slide import (
    AudioSegmentInfo,
    SlideGenerationContext,
    SlideDeckDTO,
    SlideLectureGenerationResult,
)
from deeplecture.dto.storage import ContentMetadata
from deeplecture.services.content_service import ContentService, get_default_content_service
from deeplecture.services.slide_pipeline_coordinator import PagePipelineCoordinator
from deeplecture.services.slide_speech_service import SpeechService
from deeplecture.services.slide_transcript_service import TranscriptService
from deeplecture.services.slide_video_composer import VideoComposer
from deeplecture.storage.fs_subtitle_storage import SubtitleStorage, get_default_subtitle_storage
from deeplecture.storage.metadata_storage import MetadataStorage, get_default_metadata_storage
from deeplecture.tts.tts_factory import TTS, TTSFactory
from deeplecture.utils.fs import ensure_directory
from deeplecture.workers import TaskManager
from deeplecture.workers.task_manager import Task

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)


# Workspace for temp generation artifacts
WORK_SUBDIR = "temp"
VIDEO_OUTPUT_SUBDIR = "videos"


class SlideLectureService:
    """
    Application service for PDF slide lecture generation.

    Pipeline:
    1. Upload PDF -> SlideDeckDTO (register_deck).
    2. Background job:
       - Render pages to PNG.
       - For each page: call vision LLM to produce JSON transcript segments.
       - Run TTS on the chosen subtitle language, measure durations.
       - Build bilingual SRT using real audio durations (+ fixed page breaks).
       - Compose per-page videos and concat into a final lecture video.
    """

    def __init__(
        self,
        task_manager: Optional[TaskManager] = None,
        tts: Optional[TTS] = None,
        tts_factory: Optional[TTSFactory] = None,
        metadata_storage: Optional[MetadataStorage] = None,
        content_service: Optional[ContentService] = None,
        upload_folder: Optional[str] = None,
        output_folder: Optional[str] = None,
        app_context: Optional[AppContext] = None,
        task_runner: Optional[TaskManager] = None,
    ) -> None:
        ctx = app_context or get_app_context()
        ctx.init_paths()

        # Accept legacy task_runner alias for backward compatibility with older callers/tests.
        self._task_manager: Optional[TaskManager] = task_manager or task_runner
        if tts_factory is None:
            ctx.ensure_initialized()
            tts_factory = ctx.tts_factory
        self._tts_factory: TTSFactory = tts_factory or TTSFactory()
        self._custom_tts_provided = tts is not None
        self._tts_task_name = "slide_lecture"
        self._tts: TTS = tts or self._tts_factory.get_tts_for_task(self._tts_task_name)
        self._metadata_storage: MetadataStorage = metadata_storage or get_default_metadata_storage()
        self._content_service: ContentService = content_service or get_default_content_service()
        # Reuse the same content-scoped subtitle layout as SubtitleService so
        # that all content types share outputs/subtitles/<content_id>/...
        self._subtitle_storage: SubtitleStorage = get_default_subtitle_storage(self._content_service)
        self._upload_folder = upload_folder or ctx.upload_folder
        self._output_folder = output_folder or ctx.output_folder

        # Cache lecture config with TTL (time-to-live) refresh mechanism.
        self._lecture_cfg: Optional[Dict[str, Any]] = None
        self._lecture_cfg_loaded_at: Optional[datetime] = None
        self._lecture_cfg_ttl_minutes: int = 5  # Refresh config every 5 minutes

        # Workdir for temp artifacts, plus stable outputs for video/subtitles.
        self._workspace_root = ensure_directory(
            self._output_folder,
            WORK_SUBDIR,
        )
        self._video_output_dir = ensure_directory(
            self._output_folder,
            VIDEO_OUTPUT_SUBDIR,
        )

        # Orchestrated sub-services.
        from deeplecture.services.slide_deck_ingest_service import DeckIngestService

        self._deck_ingest = DeckIngestService(
            metadata_storage=self._metadata_storage,
            upload_folder=self._upload_folder,
            workspace_root=self._output_folder,
        )
        self._transcript_service = TranscriptService()
        self._speech_service = SpeechService(
            tts=self._tts,
            tts_factory=self._tts_factory,
            task_name=self._tts_task_name,
        )
        self._video_composer = VideoComposer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_deck(self, file_obj, filename: str) -> SlideDeckDTO:
        """
        Save an uploaded PDF and return basic deck metadata.

        Thin wrapper over DeckIngestService so that existing routes stay
        unchanged while ingest logic lives in a smaller service.
        """
        return self._deck_ingest.register_deck(file_obj, filename)

    def start_generate_lecture(
        self,
        deck_id: str,
        *,
        tts_language: Optional[str] = None,
        page_break_silence_seconds: Optional[float] = None,
        force: bool = False,
    ) -> SlideLectureGenerationResult:
        """
        Start background slide lecture generation.

        Args:
            deck_id: The ID of the slide deck.
            tts_language: Optional TTS language override.
            page_break_silence_seconds: Optional page break silence override.
            force: If True, regenerate even if video already exists.
        """
        ctx = self._build_generation_context(deck_id)
        metadata = self._metadata_storage.get(deck_id)

        # Skip early return checks if force is True
        if not force:
            if metadata and metadata.video_status == "ready":
                if os.path.exists(ctx.video_output_path) and os.path.exists(ctx.subtitle_path):
                    return SlideLectureGenerationResult(
                        deck_id=deck_id,
                        lecture_video_path=ctx.video_output_path,
                        subtitle_path=ctx.subtitle_path,
                        status="ready",
                        message="Slide lecture already generated",
                        job_id=None,
                    )

            if os.path.exists(ctx.video_output_path) and os.path.exists(ctx.subtitle_path):
                return SlideLectureGenerationResult(
                    deck_id=deck_id,
                    lecture_video_path=ctx.video_output_path,
                    subtitle_path=ctx.subtitle_path,
                    status="ready",
                    message="Slide lecture already generated",
                    job_id=None,
                    )

        cfg = self._get_effective_lecture_config(
            tts_language=tts_language,
            page_break_silence_seconds=page_break_silence_seconds,
        )

        def _run() -> None:
            self.generate_lecture_sync(deck_id, cfg, ctx=ctx)

        task_mgr = self._require_task_manager()
        task_id = task_mgr.submit_task(
            deck_id,
            "video_generation",
            metadata={
                "deck_id": deck_id,
                "lecture_video_path": ctx.video_output_path,
                "subtitle_path": ctx.subtitle_path,
                "config": cfg,
                "tts_language": cfg.get("tts_language"),
                "page_break_silence_seconds": cfg.get("page_break_silence_seconds"),
            },
        )

        # Persist processing status for unified metadata
        try:
            self._metadata_storage.update_feature_status(deck_id, "video", "processing", task_id)
        except Exception as exc:
            logger.warning("Failed to update video status to processing for %s: %s", deck_id, exc)

        return SlideLectureGenerationResult(
            deck_id=deck_id,
            lecture_video_path=ctx.video_output_path,
            subtitle_path=ctx.subtitle_path,
            status="processing",
            message="Slide lecture generation started",
            job_id=task_id,
        )

    def get_deck_meta(self, deck_id: str) -> Dict[str, Any]:
        """
        Public accessor for deck metadata.

        Returns the contents of metadata for the given deck_id or raises
        FileNotFoundError if the deck does not exist.
        """
        metadata = self._get_deck_metadata(deck_id)
        if metadata:
            return {
                "deck_id": metadata.id,
                "filename": metadata.original_filename,
                "pdf_path": metadata.source_file,
                "output_dir": self._deck_dir(deck_id),
                "page_count": metadata.pdf_page_count,
                "created_at": metadata.created_at,
                "lecture_video_path": metadata.video_file,
                "subtitle_path": metadata.subtitle_path,
                "status": metadata.video_status,
            }

        raise FileNotFoundError(f"Slide deck not found: {deck_id}")

    def generate_lecture_sync(
        self,
        deck_id: str,
        cfg: Dict[str, Any],
        ctx: Optional[SlideGenerationContext] = None,
    ) -> None:
        """
        Blocking slide lecture generation for a single deck.

        Uses sequential transcript generation with pipelined TTS/video processing.
        As each page transcript is generated, it's immediately sent for TTS and video
        generation in parallel with continuing LLM work on subsequent pages.
        """
        ctx = ctx or self._build_generation_context(deck_id)

        if not os.path.exists(ctx.pdf_path):
            raise FileNotFoundError(
                f"PDF file for deck {deck_id} not found at {ctx.pdf_path}",
            )

        deck_dir = ctx.workspace_dir
        ensure_directory(deck_dir)

        page_count = ctx.page_count
        if page_count <= 0:
            page_count = self._get_pdf_page_count(ctx.pdf_path)

        logger.info(
            "Starting slide lecture generation for deck %s (%s pages)",
            deck_id,
            page_count,
        )

        pages_dir = ensure_directory(deck_dir, "pages")
        transcripts_dir = ensure_directory(deck_dir, "transcripts")
        audio_dir = ensure_directory(deck_dir, "audio")
        video_segments_dir = ensure_directory(deck_dir, "video_segments")

        try:
            # 1. Render pages as PNG images.
            page_image_paths = self._render_pages_to_images(
                pdf_path=ctx.pdf_path,
                pages_dir=pages_dir,
                expected_page_count=page_count,
            )
            if not page_image_paths:
                raise RuntimeError(f"No pages rendered for deck {deck_id}")

            # Persist page images outside the temp workspace so they remain
            # available even after temp cleanup.
            self._persist_page_images(deck_id, page_image_paths)

            # 2. Create pipeline coordinator for TTS/video generation.
            # Determine TTS concurrency from deeplecture.config.
            tts_max_concurrency = int(cfg.get("tts_max_concurrency", 2))
            video_workers = 1  # Video generation is typically sequential

            coordinator = PagePipelineCoordinator(
                speech_service=self._speech_service,
                video_composer=self._video_composer,
                page_images=page_image_paths,
                audio_dir=audio_dir,
                video_segments_dir=video_segments_dir,
                tts_language=str(cfg.get("tts_language", "source")),
                tts_workers=tts_max_concurrency,
                video_workers=video_workers,
            )

            # 3. Stream transcript generation with immediate pipeline processing.
            # As each page transcript completes, the callback sends it to the
            # coordinator for TTS and video generation.
            transcript_pages = self._transcript_service.stream_pages(
                deck_id=deck_id,
                page_images=page_image_paths,
                transcripts_dir=transcripts_dir,
                source_language=str(cfg["source_language"]),
                target_language=str(cfg["target_language"]),
                neighbor_images=str(cfg.get("neighbor_images", "none")),
                transcript_lookback_pages=int(cfg.get("transcript_lookback_pages", -1)),
                summary_lookback_pages=int(cfg.get("summary_lookback_pages", -1)),
                callback=coordinator.submit,  # Pipeline each page as it completes
            )

            # 4. Wait for all pipelined TTS and video work to complete.
            audio_artifacts, segment_paths, errors = coordinator.wait_for_completion()

            # Check for critical errors
            if errors:
                logger.error(
                    "Pipeline errors occurred for deck %s: %d pages failed",
                    deck_id, len(errors)
                )
                for page_idx, error in errors.items():
                    logger.error("  Page %d: %s", page_idx, error)

            # 5. Build timeline and SRT from completed audio.
            # Convert audio artifacts to the format expected by the timeline builder.
            segments = []
            current_time = 0.0
            page_break_silence = float(cfg["page_break_silence_seconds"])

            for audio_artifact in audio_artifacts:
                page_idx = audio_artifact.page_index
                page = next((p for p in transcript_pages if p.page_index == page_idx), None)
                if not page:
                    continue

                # Add segments for this page
                for seg_idx, duration in enumerate(audio_artifact.segment_durations):
                    if seg_idx < len(page.segments):
                        seg = page.segments[seg_idx]
                        segments.append(AudioSegmentInfo(
                            source=seg.source,
                            target=seg.target,
                            start=current_time,
                            end=current_time + duration,
                            page_index=page_idx,
                            segment_index=seg_idx + 1,
                        ))
                        current_time += duration

                # Add page break silence
                current_time += page_break_silence

            # 6. Write subtitle files.
            deck_subtitle_path = ctx.subtitle_path
            ensure_directory(os.path.dirname(deck_subtitle_path))

            target_lang = str(cfg.get("target_language", "zh"))

            # Original subtitles always follow the global source_language.
            self._write_monolingual_srt(
                segments=segments,
                subtitle_path=deck_subtitle_path,
                use_source=True,
            )

            # Translated subtitles always follow the global target_language.
            translated_subtitle_path = self._subtitle_storage.build_translation_path(
                deck_id,
                target_lang,
            )
            self._write_monolingual_srt(
                segments=segments,
                subtitle_path=translated_subtitle_path,
                use_source=False,
            )

            # 7. Concatenate video segments into final lecture video.
            lecture_video_path = ctx.video_output_path
            ensure_directory(os.path.dirname(lecture_video_path))

            # Filter out any segments that failed
            valid_segments = [path for path in segment_paths if path and os.path.exists(path)]
            if not valid_segments:
                raise RuntimeError(f"No video segments generated for deck {deck_id}")

            self._video_composer.concatenate_segments(
                segment_paths=valid_segments,
                output_path=lecture_video_path,
            )

            # 8. Update unified content metadata and artifact registry.
            try:
                # Ensure subtitles and translated subtitles are tracked.
                self._content_service.mark_subtitles_generated(
                    deck_id,
                    deck_subtitle_path,
                )
                self._content_service.mark_translation_generated(
                    deck_id,
                    translated_subtitle_path,
                )
                # Mark slide video as generated and ready.
                self._content_service.mark_video_generated(
                    deck_id,
                    lecture_video_path,
                )

                # Backfill ancillary fields that ContentService does not manage.
                metadata = self._metadata_storage.get(deck_id)
                if metadata:
                    metadata.video_job_id = None
                    if metadata.pdf_page_count is None:
                        metadata.pdf_page_count = page_count
                    metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
                    self._metadata_storage.save(metadata)
            except Exception as exc:
                logger.warning(
                    "Failed to update unified content metadata for deck %s: %s",
                    deck_id,
                    exc,
                )

            logger.info(
                "Completed slide lecture generation for deck %s: video=%s, subtitles=%s",
                deck_id,
                lecture_video_path,
                deck_subtitle_path,
            )
        finally:
            # Shutdown the coordinator to clean up thread pools.
            coordinator.shutdown()

            # Clean up temporary files (audio/video segments and temp workspace)
            # according to configuration, even if the pipeline fails partway.
            cleanup_temp = bool(cfg.get("cleanup_temp", True))
            if not cleanup_temp:
                logger.debug(
                    "Skipping temporary workspace cleanup for deck %s (cleanup_temp=false)",
                    deck_id,
                )
            if cleanup_temp:
                self._cleanup_temp_files(ctx)

    def resolve_subtitle_path(self, deck_id: str) -> str:
        """Resolve subtitle path from unified metadata."""
        metadata = self._get_deck_metadata(deck_id)
        if not metadata or metadata.type != "slide":
            raise FileNotFoundError(f"Slide deck not found: {deck_id}")
        if not metadata.subtitle_path:
            raise FileNotFoundError(f"Subtitle path missing for deck {deck_id}")
        return str(metadata.subtitle_path)

    def resolve_lecture_video_path(self, deck_id: str) -> str:
        """Resolve lecture video path from unified metadata."""
        metadata = self._get_deck_metadata(deck_id)
        if not metadata or metadata.type != "slide":
            raise FileNotFoundError(f"Slide deck not found: {deck_id}")
        if not metadata.video_file:
            raise FileNotFoundError(f"Lecture video path missing for deck {deck_id}")
        return str(metadata.video_file)

    def get_page_image_path(self, deck_id: str, page_index: int) -> str:
        """Resolve page image path with unified metadata awareness."""
        filename = f"page_{page_index:03d}.png"

        # Preferred: stable screenshots directory scoped by content ID so page
        # images survive temp workspace cleanup.
        try:
            stable_path = self._content_service.build_content_path(
                str(deck_id),
                "screenshots",
                filename,
            )
            if os.path.exists(stable_path):
                return stable_path
        except Exception:
            # If ContentService path resolution fails, fall back to legacy
            # temp workspace layout.
            pass

        # Legacy fallback: temp workspace under outputs/temp/<deck_id>/pages.
        deck_dir = self._deck_dir(deck_id)
        return os.path.join(deck_dir, "pages", filename)

    def get_job(self, job_id: str) -> Optional[Task]:
        if self._task_manager is None:
            return None
        return self._task_manager.get_task(job_id)

    def list_decks(self) -> List[Dict[str, Any]]:
        """
        List all slide decks with their metadata.

        Returns a list of deck metadata dictionaries.
        """
        decks: List[Dict[str, Any]] = []
        try:
            for metadata in self._metadata_storage.list_all():
                if metadata.type != "slide":
                    continue
                decks.append({
                    "deck_id": metadata.id,
                    "filename": metadata.original_filename,
                    "pdf_path": metadata.source_file,
                    "output_dir": self._deck_dir(metadata.id),
                    "page_count": metadata.pdf_page_count,
                    "created_at": metadata.created_at,
                    "lecture_video_path": metadata.video_file,
                    "subtitle_path": metadata.subtitle_path,
                    "status": metadata.video_status,
                })
        except Exception as exc:
            logger.error("Failed to list slide decks: %s", exc)

        # Sort by created_at descending (newest first)
        decks.sort(
            key=lambda d: d.get("created_at", ""),
            reverse=True,
        )
        return decks

    # ------------------------------------------------------------------
    # Generation context helpers
    # ------------------------------------------------------------------

    def _build_generation_context(self, deck_id: str) -> SlideGenerationContext:
        """
        Build generation context from unified metadata storage.
        """
        metadata = self._get_deck_metadata(deck_id)
        if not metadata:
            raise FileNotFoundError(f"Slide deck not found: {deck_id}")

        if metadata.type != "slide":
            raise ValueError(f"Content {deck_id} is not a slide deck")

        # Extract PDF path
        pdf_path = metadata.source_file
        if not pdf_path:
            raise FileNotFoundError(f"PDF path missing for deck {deck_id}")

        # Determine page count
        page_count = int(metadata.pdf_page_count or 0)
        if page_count <= 0 and pdf_path and os.path.exists(pdf_path):
            page_count = self._get_pdf_page_count(pdf_path)

        # Set up workspace directories
        workspace_dir = ensure_directory(self._deck_dir(deck_id))
        pages_dir = ensure_directory(workspace_dir, "pages")
        transcripts_dir = ensure_directory(workspace_dir, "transcripts")
        audio_dir = ensure_directory(workspace_dir, "audio")

        # Make sure all slide-lecture workspace directories are indexed so
        # that delete_content can reliably clean them up.
        try:
            self._content_service.register_artifact(
                deck_id,
                workspace_dir,
                kind="dir:slide_lecture:workspace",
                is_directory=True,
            )
            self._content_service.register_artifact(
                deck_id,
                pages_dir,
                kind="dir:slide_lecture:pages",
                is_directory=True,
            )
            self._content_service.register_artifact(
                deck_id,
                transcripts_dir,
                kind="dir:slide_lecture:transcripts",
                is_directory=True,
            )
            self._content_service.register_artifact(
                deck_id,
                audio_dir,
                kind="dir:slide_lecture:audio",
                is_directory=True,
            )
        except Exception as exc:  # pragma: no cover - best-effort indexing
            logger.warning(
                "Failed to register slide lecture workspace for %s: %s",
                deck_id,
                exc,
            )

        # Determine output paths. For subtitles, reuse the same content-scoped
        # layout as SubtitleService/FsSubtitleStorage:
        # outputs/subtitles/<deck_id>/original.srt
        canonical_subtitle_path = self._subtitle_storage.build_original_path(deck_id)
        subtitle_path = metadata.subtitle_path or canonical_subtitle_path
        video_output_path = metadata.video_file or os.path.join(
            self._video_output_dir,
            f"{deck_id}.mp4",
        )

        return SlideGenerationContext(
            deck_id=deck_id,
            pdf_path=pdf_path,
            page_count=page_count,
            workspace_dir=workspace_dir,
            pages_dir=pages_dir,
            transcripts_dir=transcripts_dir,
            audio_dir=audio_dir,
            subtitle_path=subtitle_path,
            video_output_path=video_output_path,
        )

    # ------------------------------------------------------------------
    # Config / meta helpers
    # ------------------------------------------------------------------

    def _get_effective_lecture_config(
        self,
        *,
        tts_language: Optional[str],
        page_break_silence_seconds: Optional[float],
    ) -> Dict[str, Any]:
        """
        Resolve the effective slide-lecture configuration for this job.

        Rules:
        - The two subtitle languages always come from the global subtitle
          settings: subtitle.source_language and subtitle.translation.target_language.
        - slides.lecture.tts_language selects which of these two is spoken
          by TTS ("source" or "target").
        - Per-request overrides can change tts_language and
          page_break_silence_seconds, but never introduce a third language.

        Config caching: Configuration is cached with a 5-minute TTL to allow
        dynamic updates without requiring service restart.
        """
        # Check if config needs refresh (first load or TTL expired)
        from datetime import timedelta

        needs_refresh = (
            self._lecture_cfg is None
            or self._lecture_cfg_loaded_at is None
            or (
                datetime.now(UTC).replace(tzinfo=None) - self._lecture_cfg_loaded_at
                > timedelta(minutes=self._lecture_cfg_ttl_minutes)
            )
        )

        if needs_refresh:
            config = load_config() or {}
            llm_cfg = config.get("llm") or {}
            slides_cfg = config.get("slides") or {}
            lecture_cfg = slides_cfg.get("lecture") or {}
            subtitle_cfg = config.get("subtitle") or {}
            translation_cfg = subtitle_cfg.get("translation") or {}
            tts_cfg = config.get("tts") or {}

            # Global subtitle language pair.
            source_lang = str(subtitle_cfg.get("source_language", "en"))
            target_lang = str(translation_cfg.get("target_language", "zh"))

            # Which of the above should be spoken by TTS for slide lectures.
            tts_mode = str(lecture_cfg.get("tts_language", "source")).lower()
            if tts_mode not in ("source", "target"):
                tts_mode = "source"

            max_rpm_raw = llm_cfg.get("max_rpm", 60)
            try:
                max_rpm = int(max_rpm_raw)
            except (TypeError, ValueError):
                max_rpm = 60
            if max_rpm <= 0:
                max_rpm = 1

            # Neighbor images setting for context (previous/next page)
            neighbor_raw = str(lecture_cfg.get("neighbor_images", "next")).lower()
            if neighbor_raw not in ("none", "next", "prev_next"):
                neighbor_raw = "next"

            # Transcript lookback pages (-1 for all, 0 for none, positive for specific count)
            lookback_raw = lecture_cfg.get("transcript_lookback_pages", -1)
            try:
                transcript_lookback_pages = int(lookback_raw)
            except (TypeError, ValueError):
                transcript_lookback_pages = -1

            # Summary lookback pages (-1 for all, 0 for none, positive for specific count)
            summary_lookback_raw = lecture_cfg.get("summary_lookback_pages", -1)
            try:
                summary_lookback_pages = int(summary_lookback_raw)
            except (TypeError, ValueError):
                summary_lookback_pages = -1

            # Fixed worker count - actual rate limiting is handled by RateLimitedTTS
            tts_max_concurrency = 16

            # Whether to remove temporary slide-lecture workspaces.
            cleanup_raw = lecture_cfg.get("cleanup_temp", True)
            cleanup_temp = True
            if isinstance(cleanup_raw, bool):
                cleanup_temp = cleanup_raw
            elif isinstance(cleanup_raw, str):
                lowered = cleanup_raw.strip().lower()
                if lowered in ("true", "1", "yes", "y", "on"):
                    cleanup_temp = True
                elif lowered in ("false", "0", "no", "n", "off"):
                    cleanup_temp = False

            self._lecture_cfg = {
                # Language settings.
                "source_language": source_lang,
                "target_language": target_lang,
                "tts_language": tts_mode,
                # Context settings for sequential generation.
                "neighbor_images": neighbor_raw,
                "transcript_lookback_pages": transcript_lookback_pages,
                "summary_lookback_pages": summary_lookback_pages,
                "max_rpm": max_rpm,
                "page_break_silence_seconds": float(
                    lecture_cfg.get("page_break_silence_seconds", 1.0) or 1.0,
                ),
                "cleanup_temp": cleanup_temp,
                "tts_max_concurrency": tts_max_concurrency,
            }
            # Record load time for TTL management
            self._lecture_cfg_loaded_at = datetime.now(UTC).replace(tzinfo=None)
            logger.debug("Loaded lecture configuration (will refresh in %d minutes)", self._lecture_cfg_ttl_minutes)

        cfg = dict(self._lecture_cfg)

        # Allow per-request override of which language is spoken by TTS,
        # while still tying the pair to the global subtitle source/target.
        if tts_language is not None:
            mode = str(tts_language).lower()
            if mode in ("source", "target"):
                cfg["tts_language"] = mode

        if page_break_silence_seconds is not None:
            try:
                val = float(page_break_silence_seconds)
                if val >= 0:
                    cfg["page_break_silence_seconds"] = val
            except (TypeError, ValueError):
                pass

        return cfg

    def _get_deck_metadata(self, deck_id: str) -> Optional[ContentMetadata]:
        """
        Unified metadata retrieval from the primary MetadataStorage.
        """
        return self._metadata_storage.get(deck_id)

    def _deck_dir(self, deck_id: str) -> str:
        return os.path.join(self._workspace_root, self._sanitize_id(deck_id))

    def _require_task_manager(self) -> TaskManager:
        if self._task_manager is None:
            raise RuntimeError("TaskManager is required for background slide lecture jobs")
        return self._task_manager

    # ------------------------------------------------------------------
    # PDF rendering and transcript generation
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        filename = filename.strip().replace("\\", "/")
        filename = os.path.basename(filename)
        if not filename:
            filename = "slides.pdf"
        return filename

    @staticmethod
    def _sanitize_id(raw: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw.strip())
        return safe or "deck"

    @staticmethod
    def _get_pdf_page_count(pdf_path: str) -> int:
        try:
            import pypdfium2 as pdfium  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "pypdfium2 is required for PDF slide support. "
                "Install it with 'uv add pypdfium2'.",
            ) from exc

        doc = pdfium.PdfDocument(pdf_path)
        try:
            return len(doc)
        finally:
            doc.close()

    def _render_pages_to_images(
        self,
        *,
        pdf_path: str,
        pages_dir: str,
        expected_page_count: int,
    ) -> Dict[int, str]:
        """
        Render all pages of the PDF into PNG images.
        """
        try:
            import pypdfium2 as pdfium  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "pypdfium2 is required for PDF slide rendering. "
                "Install it with 'uv add pypdfium2'.",
            ) from exc

        ensure_directory(pages_dir)
        page_images: Dict[int, str] = {}

        doc = pdfium.PdfDocument(pdf_path)
        try:
            page_count = len(doc)
            if expected_page_count and expected_page_count != page_count:
                logger.warning(
                    "PDF page count mismatch for %s: meta=%s, actual=%s",
                    pdf_path,
                    expected_page_count,
                    page_count,
                )

            for index in range(page_count):
                page = doc[index]
                # Use a modest upscale factor to keep text readable.
                try:
                    bitmap = page.render(scale=2.0)
                    pil_image = bitmap.to_pil()
                except Exception as exc:
                    logger.error(
                        "Failed to render page %s of %s: %s",
                        index + 1,
                        pdf_path,
                        exc,
                    )
                    continue

                page_idx = index + 1
                filename = f"page_{page_idx:03d}.png"
                path = os.path.join(pages_dir, filename)
                try:
                    pil_image.save(path)
                except Exception as exc:
                    logger.error(
                        "Failed to save rendered page %s for %s: %s",
                        page_idx,
                        pdf_path,
                        exc,
                    )
                    continue

                page_images[page_idx] = path
        finally:
            doc.close()

        return page_images

    def _persist_page_images(
        self,
        deck_id: str,
        page_image_paths: Dict[int, str],
    ) -> None:
        """
        Copy rendered page images into a stable screenshots directory so they
        remain available after temp workspaces are cleaned up.
        """
        if not page_image_paths:
            return

        try:
            screenshots_dir = self._content_service.ensure_content_dir(
                str(deck_id),
                "screenshots",
            )
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning(
                "Failed to ensure screenshots dir for deck %s: %s",
                deck_id,
                exc,
            )
            return

        for page_index, src_path in sorted(page_image_paths.items()):
            if not src_path or not os.path.exists(src_path):
                continue

            filename = f"page_{page_index:03d}.png"
            dest_path = os.path.join(screenshots_dir, filename)
            try:
                # Copy rather than move so the generation pipeline can keep
                # using the temp files freely.
                shutil.copy2(src_path, dest_path)
                self._content_service.register_artifact(
                    str(deck_id),
                    dest_path,
                    kind="screenshot:slide_page",
                    media_type="image/png",
                    metadata={"page_index": page_index},
                )
            except Exception as exc:  # pragma: no cover - best-effort persistence
                logger.warning(
                    "Failed to persist page image %s for deck %s: %s",
                    src_path,
                    deck_id,
                    exc,
                )

    # ------------------------------------------------------------------
    # TTS, timeline, and SRT
    # ------------------------------------------------------------------
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        millis = int(round(max(0.0, seconds) * 1000.0))
        hours, rem = divmod(millis, 3600_000)
        minutes, rem = divmod(rem, 60_000)
        secs, ms = divmod(rem, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

    def _write_monolingual_srt(
        self,
        *,
        segments: List[AudioSegmentInfo],
        subtitle_path: str,
        use_source: bool,
    ) -> None:
        lines: List[str] = []
        index = 1
        for seg in segments:
            text = seg.source if use_source else seg.target
            text = (text or "").strip()
            if not text:
                continue

            start_ts = self._format_timestamp(seg.start)
            end_ts = self._format_timestamp(seg.end)

            lines.append(str(index))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text)
            lines.append("")
            index += 1

        os.makedirs(os.path.dirname(subtitle_path), exist_ok=True)
        with open(subtitle_path, "w", encoding="utf-8") as f:
            if lines:
                f.write("\n".join(lines).strip() + "\n")
            else:
                f.write("")

    def _write_bilingual_srt(
        self,
        *,
        segments: List[AudioSegmentInfo],
        subtitle_path: str,
    ) -> None:
        lines: List[str] = []
        for idx, seg in enumerate(segments, start=1):
            start_ts = self._format_timestamp(seg.start)
            end_ts = self._format_timestamp(seg.end)

            source_text = seg.source.strip()
            target_text = seg.target.strip()

            text_lines = [source_text] if source_text else []
            if target_text:
                text_lines.append(target_text)

            if not text_lines:
                continue

            lines.append(str(idx))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.extend(text_lines)
            lines.append("")  # blank line between entries

        os.makedirs(os.path.dirname(subtitle_path), exist_ok=True)
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).strip() + "\n")

    def _cleanup_temp_files(self, ctx: SlideGenerationContext) -> None:
        """
        Clean up temporary workspace artifacts for a slide lecture.

        Removes:
        - Individual audio segments (seg_p*.wav)
        - Silence files (silence_*.wav)
        - Video segment directory
        - The per-deck temp workspace directory under outputs/temp

        Preserves:
        - Final video and subtitle outputs, which live outside the temp workspace
        """
        import glob

        try:
            # Clean up individual audio segments
            for pattern in ["seg_p*.wav", "silence_*.wav"]:
                for file_path in glob.glob(os.path.join(ctx.audio_dir, pattern)):
                    try:
                        os.remove(file_path)
                    except OSError as exc:
                        logger.debug("Failed to remove temp audio file %s: %s", file_path, exc)

            # Clean up video segments directory
            segments_dir = os.path.join(ctx.workspace_dir, "video_segments")
            if os.path.exists(segments_dir):
                shutil.rmtree(segments_dir)

            # Finally, remove the per-deck temp workspace directory entirely.
            # This keeps outputs/temp from accumulating stale per-job folders.
            workspace_dir = ctx.workspace_dir
            if os.path.isdir(workspace_dir):
                try:
                    shutil.rmtree(workspace_dir)
                    logger.debug(
                        "Removed temporary workspace directory for deck %s: %s",
                        ctx.deck_id,
                        workspace_dir,
                    )
                except OSError as exc:
                    logger.warning(
                        "Failed to remove temp workspace dir for deck %s at %s: %s",
                        ctx.deck_id,
                        workspace_dir,
                        exc,
                    )
            else:
                logger.debug(
                    "No temp workspace directory to remove for deck %s at %s",
                    ctx.deck_id,
                    workspace_dir,
                )

            logger.info("Cleaned up temporary artifacts for deck %s", ctx.deck_id)

        except Exception as exc:
            logger.warning(
                "Failed to cleanup temp files for deck %s: %s",
                ctx.deck_id,
                exc,
            )

    # Audio / video helper methods have been extracted into SpeechService and
    # VideoComposer. SlideLectureService now only orchestrates those components.
