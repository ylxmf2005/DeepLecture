"""
Application Settings using Pydantic Settings.

Loads configuration from config/conf.yaml with environment variable overrides.
Maps all conf.yaml sections to typed Python configuration.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic_settings import PydanticBaseSettingsSource

try:
    from pydantic_settings import YamlConfigSettingsSource
except ImportError:
    YamlConfigSettingsSource = None  # type: ignore


# =============================================================================
# SERVER CONFIGURATION
# =============================================================================


class ServerConfig(BaseModel):
    """Server-level configuration."""

    max_upload_bytes: int = 10737418240  # 10GB
    max_note_image_bytes: int = 104857600  # 100MB
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    rate_limit_storage_uri: str = "memory://"
    api_key: str = ""
    run_worker: bool = True


class RateLimitsConfig(BaseModel):
    """Rate limiting configuration."""

    default_per_day: int = 100000
    default_per_hour: int = 10000
    upload_per_minute: int = 100
    generate_per_hour: int = 1000
    trusted_proxies: list[str] = Field(default_factory=list)


# =============================================================================
# LLM CONFIGURATION
# =============================================================================


class LLMModelConfig(BaseModel):
    """Single LLM model configuration."""

    name: str
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
    max_tokens: int = 65536
    temperature: float = 0.7


class LLMConfig(BaseModel):
    """LLM service configuration."""

    max_rpm: int = 600
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 60.0
    models: list[LLMModelConfig] = Field(default_factory=list)
    task_models: dict[str, str] = Field(default_factory=dict)

    def get_model(self, name: str) -> LLMModelConfig | None:
        """Get model config by name."""
        for model in self.models:
            if model.name == name:
                return model
        return None


# =============================================================================
# TTS CONFIGURATION
# =============================================================================


class FishAudioConfig(BaseModel):
    """FishAudio TTS provider configuration."""

    api_key: str = ""
    base_url: str = "https://api.fish.audio"
    model: str = "s1"
    reference_id: str = ""
    base_speed: float = 1.0
    format: str = "wav"
    latency: str = "balanced"


class EdgeTTSConfig(BaseModel):
    """Edge TTS provider configuration."""

    voice: str = "zh-CN-XiaoxiaoNeural"


class TTSModelConfig(BaseModel):
    """Single TTS model configuration."""

    name: str
    provider: str
    fishaudio: FishAudioConfig | None = None
    edge_tts: EdgeTTSConfig | None = None


class TTSConfig(BaseModel):
    """TTS service configuration."""

    max_rpm: int = 150
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 60.0
    sample_rate: int = 44100
    max_sentence_duration: float = 8.0
    models: list[TTSModelConfig] = Field(default_factory=list)
    task_models: dict[str, str] = Field(default_factory=dict)

    def get_model(self, name: str) -> TTSModelConfig | None:
        """Get model config by name."""
        for model in self.models:
            if model.name == name:
                return model
        return None


# =============================================================================
# ASR (WHISPER) CONFIGURATION
# =============================================================================


class WhisperCppConfig(BaseModel):
    """Whisper.cpp ASR configuration."""

    model_name: str = "large-v3-turbo"
    model_path: str = ""
    whisper_bin: str = ""
    whisper_cpp_dir: str = "whisper.cpp"
    auto_download: bool = True
    flash_attn: bool = True
    beam_size: int = 1
    best_of: int = 1


class FasterWhisperConfig(BaseModel):
    """Faster Whisper ASR configuration."""

    model_size: str = "large-v3-turbo"
    device: str = "auto"
    compute_type: str = "auto"
    download_root: str = ""


class TranslationConfig(BaseModel):
    """
    Subtitle translation configuration (legacy).

    NOTE: In the Clean Architecture flow, translation is part of the unified
    "enhance + translate" workflow. This remains only to keep YAML compatibility
    during migration (config/conf.yaml still contains `subtitle.translation`).
    """

    batch_size: int = 10
    # NOTE: target_language removed - must be passed from frontend request


class EnhancementConfig(BaseModel):
    """
    Subtitle enhancement configuration (legacy).

    NOTE: This exists only to keep YAML compatibility during migration.
    Business parameters are mapped into `SubtitleEnhanceTranslateConfig`.
    Execution parameters (e.g., max_concurrency) are mapped into TasksConfig.parallelism.
    """

    merge_window: int = 3
    overlap: int = 1
    max_output_chars: int = 160
    background_max_chars: int = 8000
    temperature: float = 0.2
    batch_size: int = 50


class SubtitleEnhanceTranslateConfig(BaseModel):
    """Unified subtitle enhancement + translation configuration (business-level)."""

    merge_window: int = 3
    overlap: int = 1
    max_output_chars: int = 160
    background_max_chars: int = 8000
    temperature: float = 0.2
    batch_size: int = 50


class TimelineConfig(BaseModel):
    """Timeline generation configuration."""

    # NOTE: output_language removed - must be passed from frontend request
    temperature: float = 0.3


class SubtitleConfig(BaseModel):
    """Subtitle processing configuration (system-level only)."""

    engine: Literal["whisper_cpp", "faster_whisper"] = "whisper_cpp"
    # NOTE: source_language removed - must be passed from frontend request
    use_mock: bool = False
    whisper_cpp: WhisperCppConfig = Field(default_factory=WhisperCppConfig)
    faster_whisper: FasterWhisperConfig = Field(default_factory=FasterWhisperConfig)
    # New unified config used by Clean Architecture use cases
    enhance_translate: SubtitleEnhanceTranslateConfig = Field(default_factory=SubtitleEnhanceTranslateConfig)

    # Legacy YAML sections (migration-only)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    enhancement: EnhancementConfig = Field(default_factory=EnhancementConfig)
    timeline: TimelineConfig = Field(default_factory=TimelineConfig)

    @model_validator(mode="after")
    def _migrate_legacy_subtitle_configs(self) -> SubtitleConfig:
        # If user didn't explicitly set `enhance_translate`, populate it from legacy sections.
        # Precedence: enhancement fields > translation.batch_size > defaults.
        if "enhance_translate" not in self.model_fields_set:
            et = SubtitleEnhanceTranslateConfig()

            if self.enhancement is not None:
                et = SubtitleEnhanceTranslateConfig(
                    merge_window=self.enhancement.merge_window,
                    overlap=self.enhancement.overlap,
                    max_output_chars=self.enhancement.max_output_chars,
                    background_max_chars=self.enhancement.background_max_chars,
                    temperature=self.enhancement.temperature,
                    batch_size=self.enhancement.batch_size,
                )

            # If enhancement wasn't provided but translation was, at least carry batch_size.
            if self.translation is not None and (
                self.enhancement is None or "enhancement" not in self.model_fields_set
            ):
                try:
                    legacy_batch = int(self.translation.batch_size)
                except Exception:
                    legacy_batch = et.batch_size
                if legacy_batch > 0:
                    et.batch_size = legacy_batch

            self.enhance_translate = et

        return self


# =============================================================================
# SLIDES CONFIGURATION
# =============================================================================


class SlideLectureConfig(BaseModel):
    """Slide lecture generation configuration (business-level only).

    NOTE: Execution parameters (tts_max_workers, video_workers) moved to
    TaskParallelismConfig. tts_language moved to SlideGenerationRequest DTO.
    """

    cleanup_temp: bool = False
    neighbor_images: str = "next"
    page_break_silence_seconds: float = 1.0
    summary_lookback_pages: int = -1
    transcript_lookback_pages: int = 3
    sample_rate: int = 44100


class SlideExplanationConfig(BaseModel):
    """Slide explanation configuration."""

    subtitle_context_window_seconds: float = 30.0


class SlidesConfig(BaseModel):
    """Slides processing configuration."""

    lecture: SlideLectureConfig = Field(default_factory=SlideLectureConfig)
    explanation: SlideExplanationConfig = Field(default_factory=SlideExplanationConfig)


# =============================================================================
# VOICEOVER CONFIGURATION
# =============================================================================


class VoiceoverConfig(BaseModel):
    """Voiceover generation configuration."""

    sample_rate: int = 44100
    failure_threshold_ratio: float = 0.5
    silence_fallback_duration: float = 0.5
    # Retry policy for TTS synthesis
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 60.0

    def calculate_retry_wait_time(self, attempt: int) -> float:
        """Calculate wait time for given attempt (exponential backoff)."""
        wait = self.retry_min_wait * (2 ** (attempt - 1))
        return min(wait, self.retry_max_wait)


# -----------------------------------------------------------------------------
# Task execution parallelism (intra-usecase fan-out)
# -----------------------------------------------------------------------------


class TaskParallelismConfig(BaseModel):
    """
    Execution-level parallelism limits (infrastructure concerns).

    Controls internal fan-out concurrency for workflows that run
    many independent subtasks (LLM calls, TTS, video generation, etc.).

    Attributes:
        default: Default parallelism for all batch operations
    """

    default: int = 8


class TasksConfig(BaseModel):
    """
    In-process background task configuration.

    Attributes:
        enabled: Whether background task processing is enabled.
        workers: Number of worker threads.
        queue_max_size: Maximum pending tasks in queue.
        default_timeout_seconds: Default task execution timeout.
        completed_task_ttl_seconds: How long to retain completed tasks.
        cleanup_interval_seconds: Interval for expired task cleanup.
        sse_subscriber_queue_size: Max events per SSE subscriber.
        parallelism: Limits for intra-usecase fan-out parallelism.
    """

    enabled: bool = True
    workers: int = 4
    queue_max_size: int = 1000
    default_timeout_seconds: int = 3600  # 1 hour
    completed_task_ttl_seconds: int = 3600  # 1 hour
    cleanup_interval_seconds: int = 300  # 5 minutes
    sse_subscriber_queue_size: int = 100
    parallelism: TaskParallelismConfig = Field(default_factory=TaskParallelismConfig)


# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # Specific logger levels (override global level)
    loggers: dict[str, str] = {}


class AppConfig(BaseModel):
    """Application-level configuration."""

    debug: bool = False
    data_dir: str = "data"
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# =============================================================================
# ASK CONFIGURATION
# =============================================================================


class AskConfig(BaseModel):
    """Q&A (ask) use case configuration."""

    max_history_messages: int = 8


# =============================================================================
# READ-ALOUD CONFIGURATION
# =============================================================================


class ReadAloudVoiceConfig(BaseModel):
    """Mapping from language code to Edge TTS voice identifier."""

    language: str  # ISO 639-1, e.g. "en", "zh"
    voice: str  # Edge TTS voice ID, e.g. "en-US-AriaNeural"


class DeepLConfig(BaseModel):
    """DeepL translation API configuration."""

    auth_key: str = ""  # Empty = not configured


class ReadAloudConfig(BaseModel):
    """Note read-aloud feature configuration."""

    voices: list[ReadAloudVoiceConfig] = Field(default_factory=list)
    default_voice: str = "en-US-AriaNeural"
    tts_model: str = "edge-default"
    min_sentence_length: int = 2
    max_concurrent_tts: int = 3
    deepl: DeepLConfig = Field(default_factory=DeepLConfig)

    def get_voice(self, language: str) -> str:
        """Get TTS voice for a language, falling back to default."""
        lang = language.lower().split("-")[0]  # "en-US" → "en"
        for v in self.voices:
            if v.language.lower() == lang:
                return v.voice
        return self.default_voice


# =============================================================================
# NOTE CONFIGURATION
# =============================================================================


class NoteConfig(BaseModel):
    """Note generation configuration.

    Attributes:
        default_context_mode: Default context source for note generation.
            - "subtitle": Use only subtitle/transcript text
            - "slide": Use only slide/PDF text
            - "both": Use both subtitle and slide sources
    """

    default_context_mode: Literal["subtitle", "slide", "both"] = "both"


# =============================================================================
# MAIN SETTINGS
# =============================================================================


class Settings(BaseSettings):
    """Main application settings loaded from config/conf.yaml."""

    model_config = SettingsConfigDict(
        yaml_file="config/conf.yaml",
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    # All configuration sections from conf.yaml
    server: ServerConfig = Field(default_factory=ServerConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    ask: AskConfig = Field(default_factory=AskConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)
    slides: SlidesConfig = Field(default_factory=SlidesConfig)
    voiceover: VoiceoverConfig = Field(default_factory=VoiceoverConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)
    note: NoteConfig = Field(default_factory=NoteConfig)
    read_aloud: ReadAloudConfig = Field(default_factory=ReadAloudConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Configure settings sources with YAML support."""
        # Silence unused parameter warnings - required by pydantic-settings signature
        del dotenv_settings, file_secret_settings
        if YamlConfigSettingsSource is not None:
            return (
                init_settings,
                env_settings,
                YamlConfigSettingsSource(settings_cls),
            )
        return (init_settings, env_settings)

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to dictionary."""
        return self.model_dump()

    def get_data_dir(self) -> Path:
        """Get data directory path."""
        return Path(self.app.data_dir)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Force reload settings from disk."""
    get_settings.cache_clear()
    return get_settings()
