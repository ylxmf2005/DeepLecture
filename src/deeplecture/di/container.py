"""
Composition Root - Dependency assembly.

The single place that knows all concrete implementations.
Organized by Clean Architecture layers (inner → outer dependency order).
"""

from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from deeplecture.config import get_settings
from deeplecture.infrastructure import (
    ClaudeCodeGateway,
    FFmpegAudioProcessor,
    FFmpegVideoMerger,
    FFmpegVideoProcessor,
    FsArtifactStorage,
    FsAskStorage,
    FsCheatsheetStorage,
    FsExplanationStorage,
    FsFactVerificationStorage,
    FsFileStorage,
    FsNoteStorage,
    FsQuizStorage,
    FsSubtitleStorage,
    FsTimelineStorage,
    FsVoiceoverStorage,
    LLMProvider,
    PathResolver,
    PdfiumMerger,
    PdfiumRenderer,
    PdfiumTextExtractor,
    RateLimiter,
    RetryConfig,
    SQLiteMetadataStorage,
    SQLiteTaskStorage,
    TaskConfig,
    TaskManager,
    ThreadPoolParallelRunner,
    TTSProvider,
    WhisperASR,
    WorkerPool,
    YtdlpDownloader,
)
from deeplecture.presentation.sse import EventPublisher
from deeplecture.use_cases.ask import AskUseCase
from deeplecture.use_cases.cheatsheet import CheatsheetUseCase
from deeplecture.use_cases.content import ContentUseCase
from deeplecture.use_cases.explanation import ExplanationUseCase
from deeplecture.use_cases.fact_verification import FactVerificationUseCase
from deeplecture.use_cases.note import NoteUseCase
from deeplecture.use_cases.prompts import create_default_registry
from deeplecture.use_cases.quiz import QuizUseCase
from deeplecture.use_cases.slide_lecture import SlideLectureUseCase
from deeplecture.use_cases.subtitle import SubtitleUseCase
from deeplecture.use_cases.timeline import TimelineUseCase
from deeplecture.use_cases.upload import UploadUseCase
from deeplecture.use_cases.voiceover import VoiceoverUseCase

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import (
        EventPublisherProtocol,
        FileStorageProtocol,
    )
    from deeplecture.use_cases.prompts import PromptRegistry


class Container:
    """
    Dependency container for Clean Architecture.

    Properties are organized by layer (inner → outer):
    1. Config & Path Resolution
    2. Repository (Persistence)
    3. Infrastructure (External Adapters)
    4. Use Cases (Application Logic)

    Usage:
        container = get_container()
        usecase = container.subtitle_usecase
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache: dict[str, object] = {}
        self._lock = threading.RLock()

    def _get_or_create(self, key: str, factory: object) -> object:
        """Thread-safe cache access with double-checked locking."""
        if key in self._cache:
            return self._cache[key]
        with self._lock:
            if key not in self._cache:
                self._cache[key] = factory() if callable(factory) else factory
            return self._cache[key]

    # =========================================================================
    # 1. CONFIG & PATH RESOLUTION
    # =========================================================================

    def _data_dir(self) -> Path:
        return self._settings.get_data_dir()

    @property
    def path_resolver(self) -> PathResolver:
        """Path resolution for all filesystem operations."""
        if "path_resolver" not in self._cache:
            data_dir = self._data_dir()
            self._cache["path_resolver"] = PathResolver(
                content_dir=data_dir / "content",
                temp_dir=data_dir / "temp",
                upload_dir=data_dir / "uploads",
            )
        return self._cache["path_resolver"]  # type: ignore[return-value]

    # =========================================================================
    # 2. REPOSITORY (Persistence Layer)
    # =========================================================================

    @property
    def metadata_storage(self) -> SQLiteMetadataStorage:
        """SQLite-based metadata persistence."""
        if "metadata" not in self._cache:
            self._cache["metadata"] = SQLiteMetadataStorage(self._data_dir() / "metadata.db")
        return self._cache["metadata"]  # type: ignore[return-value]

    @property
    def task_storage(self) -> SQLiteTaskStorage:
        """SQLite-based task state persistence for crash recovery."""
        if "task_storage" not in self._cache:
            self._cache["task_storage"] = SQLiteTaskStorage(self._data_dir() / "tasks.db")
        return self._cache["task_storage"]  # type: ignore[return-value]

    @property
    def subtitle_storage(self) -> FsSubtitleStorage:
        """Filesystem-based subtitle persistence."""
        if "subtitle" not in self._cache:
            self._cache["subtitle"] = FsSubtitleStorage(self._data_dir() / "content")
        return self._cache["subtitle"]  # type: ignore[return-value]

    @property
    def artifact_storage(self) -> FsArtifactStorage:
        """Filesystem-based artifact registry."""
        if "artifact" not in self._cache:
            self._cache["artifact"] = FsArtifactStorage(self.path_resolver)
        return self._cache["artifact"]  # type: ignore[return-value]

    @property
    def timeline_storage(self) -> FsTimelineStorage:
        """Filesystem-based timeline persistence."""
        if "timeline" not in self._cache:
            self._cache["timeline"] = FsTimelineStorage(self.path_resolver)
        return self._cache["timeline"]  # type: ignore[return-value]

    @property
    def ask_storage(self) -> FsAskStorage:
        """Filesystem-based conversation persistence (ask)."""
        if "ask_storage" not in self._cache:
            self._cache["ask_storage"] = FsAskStorage(self.path_resolver)
        return self._cache["ask_storage"]  # type: ignore[return-value]

    @property
    def note_storage(self) -> FsNoteStorage:
        """Filesystem-based notes persistence."""
        if "note_storage" not in self._cache:
            self._cache["note_storage"] = FsNoteStorage(self.path_resolver)
        return self._cache["note_storage"]  # type: ignore[return-value]

    @property
    def cheatsheet_storage(self) -> FsCheatsheetStorage:
        """Filesystem-based cheatsheet persistence."""
        if "cheatsheet_storage" not in self._cache:
            self._cache["cheatsheet_storage"] = FsCheatsheetStorage(self.path_resolver)
        return self._cache["cheatsheet_storage"]  # type: ignore[return-value]

    @property
    def quiz_storage(self) -> FsQuizStorage:
        """Filesystem-based quiz persistence."""
        if "quiz_storage" not in self._cache:
            self._cache["quiz_storage"] = FsQuizStorage(self.path_resolver)
        return self._cache["quiz_storage"]  # type: ignore[return-value]

    @property
    def explanation_storage(self) -> FsExplanationStorage:
        """Filesystem-based explanation history persistence."""
        if "explanation_storage" not in self._cache:
            self._cache["explanation_storage"] = FsExplanationStorage(self._data_dir() / "content")
        return self._cache["explanation_storage"]  # type: ignore[return-value]

    @property
    def voiceover_storage(self) -> FsVoiceoverStorage:
        """Filesystem-based voiceover manifest persistence."""
        if "voiceover_storage" not in self._cache:
            self._cache["voiceover_storage"] = FsVoiceoverStorage(self.path_resolver)
        return self._cache["voiceover_storage"]  # type: ignore[return-value]

    @property
    def fact_verification_storage(self) -> FsFactVerificationStorage:
        """Filesystem-based fact verification report persistence."""
        if "fact_verification_storage" not in self._cache:
            self._cache["fact_verification_storage"] = FsFactVerificationStorage(self.path_resolver)
        return self._cache["fact_verification_storage"]  # type: ignore[return-value]

    # =========================================================================
    # 3. INFRASTRUCTURE (External Adapters)
    # =========================================================================

    @property
    def llm_rate_limiter(self) -> RateLimiter:
        """Rate limiter for LLM API calls."""
        return self._get_or_create(  # type: ignore[return-value]
            "llm_rate_limiter",
            lambda: RateLimiter(max_rpm=self._settings.llm.max_rpm),
        )

    @property
    def llm_retry_config(self) -> RetryConfig:
        """Retry configuration for LLM calls."""
        if "llm_retry_config" not in self._cache:
            self._cache["llm_retry_config"] = RetryConfig(
                max_retries=self._settings.llm.max_retries,
                min_wait=self._settings.llm.retry_min_wait,
                max_wait=self._settings.llm.retry_max_wait,
            )
        return self._cache["llm_retry_config"]  # type: ignore[return-value]

    @property
    def tts_rate_limiter(self) -> RateLimiter:
        """Rate limiter for TTS API calls."""
        return self._get_or_create(  # type: ignore[return-value]
            "tts_rate_limiter",
            lambda: RateLimiter(max_rpm=self._settings.tts.max_rpm),
        )

    @property
    def tts_retry_config(self) -> RetryConfig:
        """Retry configuration for TTS calls."""
        if "tts_retry_config" not in self._cache:
            self._cache["tts_retry_config"] = RetryConfig(
                max_retries=self._settings.tts.max_retries,
                min_wait=self._settings.tts.retry_min_wait,
                max_wait=self._settings.tts.retry_max_wait,
            )
        return self._cache["tts_retry_config"]  # type: ignore[return-value]

    @property
    def event_publisher(self) -> EventPublisherProtocol:
        """SSE event broadcaster for real-time notifications."""
        return self._get_or_create(  # type: ignore[return-value]
            "event_publisher",
            lambda: EventPublisher(max_queue_size=self._settings.tasks.sse_subscriber_queue_size),
        )

    @property
    def task_manager(self) -> TaskManager:
        """Task manager with SSE broadcasting and durable persistence."""

        def _create() -> TaskManager:
            cfg = self._settings.tasks
            task_config = TaskConfig(
                workers=cfg.workers,
                queue_max_size=cfg.queue_max_size,
                default_timeout_seconds=cfg.default_timeout_seconds,
                completed_task_ttl_seconds=cfg.completed_task_ttl_seconds,
                cleanup_interval_seconds=cfg.cleanup_interval_seconds,
            )
            return TaskManager(
                config=task_config,
                event_publisher=self.event_publisher,
                task_storage=self.task_storage,
            )

        return self._get_or_create("task_manager", _create)  # type: ignore[return-value]

    @property
    def worker_pool(self) -> WorkerPool:
        """Worker pool for task execution."""
        return self._get_or_create(  # type: ignore[return-value]
            "worker_pool",
            lambda: WorkerPool(self.task_manager),
        )

    @property
    def parallel_runner(self) -> ThreadPoolParallelRunner:
        """ThreadPool-based parallel runner for intra-usecase fan-out."""
        return self._get_or_create(  # type: ignore[return-value]
            "parallel_runner",
            lambda: ThreadPoolParallelRunner(self._settings.tasks.parallelism),
        )

    @property
    def asr(self) -> WhisperASR:
        """Whisper.cpp ASR adapter."""
        if "asr" not in self._cache:
            cfg = self._settings.subtitle.whisper_cpp
            self._cache["asr"] = WhisperASR(
                model_name=cfg.model_name,
                whisper_cpp_dir=Path(cfg.whisper_cpp_dir) if cfg.whisper_cpp_dir else None,
                auto_download=cfg.auto_download,
            )
        return self._cache["asr"]  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # PROVIDERS (Runtime model selection)
    # -------------------------------------------------------------------------

    @property
    def llm_provider(self) -> LLMProvider:
        """LLM provider for runtime model selection."""
        if "llm_provider" not in self._cache:
            data_dir = self._data_dir().resolve()
            self._cache["llm_provider"] = LLMProvider(
                config=self._settings.llm,
                allowed_image_roots=frozenset(
                    {
                        data_dir / "content",
                        data_dir / "temp",
                        data_dir / "uploads",
                    }
                ),
            )
        return self._cache["llm_provider"]  # type: ignore[return-value]

    @property
    def tts_provider(self) -> TTSProvider:
        """TTS provider for runtime model selection."""
        if "tts_provider" not in self._cache:
            self._cache["tts_provider"] = TTSProvider(config=self._settings.tts)
        return self._cache["tts_provider"]  # type: ignore[return-value]

    @property
    def prompt_registry(self) -> PromptRegistry:
        """Prompt registry for runtime prompt selection."""
        if "prompt_registry" not in self._cache:
            self._cache["prompt_registry"] = create_default_registry()
        return self._cache["prompt_registry"]  # type: ignore[return-value]

    @property
    def audio_processor(self) -> FFmpegAudioProcessor:
        """FFmpeg audio processing adapter."""
        if "audio_processor" not in self._cache:
            self._cache["audio_processor"] = FFmpegAudioProcessor()
        return self._cache["audio_processor"]  # type: ignore[return-value]

    @property
    def video_processor(self) -> FFmpegVideoProcessor:
        """FFmpeg video processing adapter with path security."""
        if "video_processor" not in self._cache:
            data_dir = self._data_dir()
            self._cache["video_processor"] = FFmpegVideoProcessor(
                allowed_roots={
                    data_dir / "content",
                    data_dir / "temp",
                    data_dir / "uploads",
                },
            )
        return self._cache["video_processor"]  # type: ignore[return-value]

    @property
    def video_merger(self) -> FFmpegVideoMerger:
        """FFmpeg video merge adapter with path security."""
        if "video_merger" not in self._cache:
            data_dir = self._data_dir()
            self._cache["video_merger"] = FFmpegVideoMerger(
                allowed_roots={
                    data_dir / "content",
                    data_dir / "temp",
                    data_dir / "uploads",
                },
            )
        return self._cache["video_merger"]  # type: ignore[return-value]

    @property
    def pdf_merger(self) -> PdfiumMerger:
        """PDF merge adapter (pypdfium2)."""
        if "pdf_merger" not in self._cache:
            data_dir = self._data_dir()
            self._cache["pdf_merger"] = PdfiumMerger(
                allowed_roots={
                    data_dir / "content",
                    data_dir / "temp",
                    data_dir / "uploads",
                },
            )
        return self._cache["pdf_merger"]  # type: ignore[return-value]

    @property
    def pdf_renderer(self) -> PdfiumRenderer:
        """PDF page rendering adapter (pypdfium2)."""
        if "pdf_renderer" not in self._cache:
            self._cache["pdf_renderer"] = PdfiumRenderer(file_storage=self._file_storage)
        return self._cache["pdf_renderer"]  # type: ignore[return-value]

    @property
    def pdf_text_extractor(self) -> PdfiumTextExtractor:
        """PDF text extraction adapter (pypdfium2)."""
        if "pdf_text_extractor" not in self._cache:
            self._cache["pdf_text_extractor"] = PdfiumTextExtractor(file_storage=self._file_storage)
        return self._cache["pdf_text_extractor"]  # type: ignore[return-value]

    @property
    def video_downloader(self) -> YtdlpDownloader:
        """yt-dlp video download adapter (downloads to temp/downloads)."""
        if "video_downloader" not in self._cache:
            downloads_dir = self.path_resolver.ensure_temp_dir("downloads")
            self._cache["video_downloader"] = YtdlpDownloader(output_folder=downloads_dir)
        return self._cache["video_downloader"]  # type: ignore[return-value]

    @property
    def claude_code(self) -> ClaudeCodeGateway:
        """Claude Code CLI gateway for fact verification."""
        if "claude_code" not in self._cache:
            self._cache["claude_code"] = ClaudeCodeGateway()
        return self._cache["claude_code"]  # type: ignore[return-value]

    # =========================================================================
    # 4. USE CASES (Application Logic)
    # =========================================================================

    @property
    def content_usecase(self) -> ContentUseCase:
        """Content management use case."""
        if "content_uc" not in self._cache:
            self._cache["content_uc"] = ContentUseCase(
                metadata_storage=self.metadata_storage,
                artifact_storage=self.artifact_storage,
            )
        return self._cache["content_uc"]  # type: ignore[return-value]

    @property
    def subtitle_usecase(self) -> SubtitleUseCase:
        """Subtitle processing use case."""
        if "subtitle_uc" not in self._cache:
            self._cache["subtitle_uc"] = SubtitleUseCase(
                metadata_storage=self.metadata_storage,
                subtitle_storage=self.subtitle_storage,
                asr=self.asr,
                llm_provider=self.llm_provider,
                prompt_registry=self.prompt_registry,
                config=self._settings.subtitle.enhance_translate,
                parallel_runner=self.parallel_runner,
            )
        return self._cache["subtitle_uc"]  # type: ignore[return-value]

    @property
    def timeline_usecase(self) -> TimelineUseCase:
        """Timeline generation and retrieval use case."""
        if "timeline_uc" not in self._cache:
            self._cache["timeline_uc"] = TimelineUseCase(
                metadata_storage=self.metadata_storage,
                subtitle_storage=self.subtitle_storage,
                timeline_storage=self.timeline_storage,
                llm_provider=self.llm_provider,
                prompt_registry=self.prompt_registry,
                config=self._settings.subtitle.timeline,
                parallel_runner=self.parallel_runner,
            )
        return self._cache["timeline_uc"]  # type: ignore[return-value]

    @property
    def explanation_usecase(self) -> ExplanationUseCase:
        """Slide/frame explanation generation use case."""
        if "explanation_uc" not in self._cache:
            self._cache["explanation_uc"] = ExplanationUseCase(
                metadata_storage=self.metadata_storage,
                subtitle_storage=self.subtitle_storage,
                explanation_storage=self.explanation_storage,
                llm_provider=self.llm_provider,
                prompt_registry=self.prompt_registry,
            )
        return self._cache["explanation_uc"]  # type: ignore[return-value]

    @property
    def ask_usecase(self) -> AskUseCase:
        """Q&A (ask) conversation use case."""
        if "ask_uc" not in self._cache:
            self._cache["ask_uc"] = AskUseCase(
                metadata_storage=self.metadata_storage,
                ask_storage=self.ask_storage,
                subtitle_storage=self.subtitle_storage,
                llm_provider=self.llm_provider,
                prompt_registry=self.prompt_registry,
                config=self._settings.ask,
            )
        return self._cache["ask_uc"]  # type: ignore[return-value]

    @property
    def note_usecase(self) -> NoteUseCase:
        """Note generation and retrieval use case."""
        if "note_uc" not in self._cache:
            self._cache["note_uc"] = NoteUseCase(
                metadata_storage=self.metadata_storage,
                note_storage=self.note_storage,
                subtitle_storage=self.subtitle_storage,
                path_resolver=self.path_resolver,
                llm_provider=self.llm_provider,
                prompt_registry=self.prompt_registry,
                parallel_runner=self.parallel_runner,
                pdf_text_extractor=self.pdf_text_extractor,
            )
        return self._cache["note_uc"]  # type: ignore[return-value]

    @property
    def cheatsheet_usecase(self) -> CheatsheetUseCase:
        """Cheatsheet generation and retrieval use case."""
        if "cheatsheet_uc" not in self._cache:
            self._cache["cheatsheet_uc"] = CheatsheetUseCase(
                cheatsheet_storage=self.cheatsheet_storage,
                subtitle_storage=self.subtitle_storage,
                path_resolver=self.path_resolver,
                llm_provider=self.llm_provider,
                prompt_registry=self.prompt_registry,
            )
        return self._cache["cheatsheet_uc"]  # type: ignore[return-value]

    @property
    def quiz_usecase(self) -> QuizUseCase:
        """Quiz generation and retrieval use case."""
        if "quiz_uc" not in self._cache:
            self._cache["quiz_uc"] = QuizUseCase(
                quiz_storage=self.quiz_storage,
                subtitle_storage=self.subtitle_storage,
                llm_provider=self.llm_provider,
                path_resolver=self.path_resolver,
                prompt_registry=self.prompt_registry,
            )
        return self._cache["quiz_uc"]  # type: ignore[return-value]

    @property
    def slide_lecture_usecase(self) -> SlideLectureUseCase:
        """Slide lecture generation use case."""
        if "slide_lecture_uc" not in self._cache:
            self._cache["slide_lecture_uc"] = SlideLectureUseCase(
                audio_processor=self.audio_processor,
                video_processor=self.video_processor,
                file_storage=self._file_storage,
                pdf_renderer=self.pdf_renderer,
                llm_provider=self.llm_provider,
                tts_provider=self.tts_provider,
                prompt_registry=self.prompt_registry,
                path_resolver=self.path_resolver,
                metadata_storage=self.metadata_storage,
                subtitle_storage=self.subtitle_storage,
                config=self._settings.slides.lecture,
                parallel_runner=self.parallel_runner,
            )
        return self._cache["slide_lecture_uc"]  # type: ignore[return-value]

    @property
    def upload_usecase(self) -> UploadUseCase:
        """Upload and merge use case (with download/merge adapters)."""
        if "upload_uc" not in self._cache:
            self._cache["upload_uc"] = UploadUseCase(
                metadata_storage=self.metadata_storage,
                file_storage=self._file_storage,
                path_resolver=self.path_resolver,
                video_downloader=self.video_downloader,
                video_merger=self.video_merger,
                pdf_merger=self.pdf_merger,
                task_queue=self.task_manager,
            )
        return self._cache["upload_uc"]  # type: ignore[return-value]

    @property
    def voiceover_usecase(self) -> VoiceoverUseCase:
        """Voiceover generation use case."""
        if "voiceover_uc" not in self._cache:
            self._cache["voiceover_uc"] = VoiceoverUseCase(
                audio=self.audio_processor,
                file_storage=self._file_storage,
                subtitle_storage=self.subtitle_storage,
                tts_provider=self.tts_provider,
                parallel_runner=self.parallel_runner,
                config=self._settings.voiceover,
            )
        return self._cache["voiceover_uc"]  # type: ignore[return-value]

    @property
    def fact_verification_usecase(self) -> FactVerificationUseCase:
        """Fact verification use case (Claude Code + WebSearch)."""
        if "fact_verification_uc" not in self._cache:
            self._cache["fact_verification_uc"] = FactVerificationUseCase(
                metadata_storage=self.metadata_storage,
                subtitle_storage=self.subtitle_storage,
                verification_storage=self.fact_verification_storage,
                claude_code=self.claude_code,
            )
        return self._cache["fact_verification_uc"]  # type: ignore[return-value]

    @property
    def _file_storage(self) -> FileStorageProtocol:
        """File storage adapter with path security (internal use)."""

        def _create() -> FsFileStorage:
            data_dir = self._data_dir()
            return FsFileStorage(
                allowed_roots=frozenset(
                    {
                        data_dir / "content",
                        data_dir / "temp",
                        data_dir / "uploads",
                    }
                )
            )

        return self._get_or_create("file_storage", _create)  # type: ignore[return-value]

    @property
    def file_storage(self) -> FileStorageProtocol:
        """File storage adapter with path security (public API)."""
        return self._file_storage


# =============================================================================
# CONTAINER LIFECYCLE
# =============================================================================


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Get global container instance (process-level singleton)."""
    return Container()


def reset_container() -> None:
    """Reset container for testing."""
    get_container.cache_clear()
