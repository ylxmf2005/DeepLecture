"""
Configuration management for DeepLecture using Pydantic Settings.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Type

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

try:
    from pydantic_settings import YamlConfigSettingsSource
except ImportError:
    YamlConfigSettingsSource = None  # type: ignore

class ServerConfig(BaseModel):
    """Server and API configuration."""
    max_upload_bytes: int = 10 * 1024 * 1024 * 1024  # 10GB
    max_note_image_bytes: int = 100 * 1024 * 1024  # 100MB
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    rate_limit_storage_uri: str = "memory://"
    api_key: str = ""
    run_worker: bool = True


class RateLimitsConfig(BaseModel):
    """HTTP API rate limits - set very high to avoid hitting them in normal use."""
    default_per_day: int = 100000
    default_per_hour: int = 10000
    upload_per_minute: int = 100
    generate_per_hour: int = 1000


class AppConfig(BaseModel):
    debug: bool = False
    data_dir: str = "data"


class LLMModelConfig(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 2000
    temperature: float = 0.7


class LLMConfig(BaseModel):
    max_rpm: int = 10000  # Very high - won't hit in normal use
    max_retries: int = 3
    retry_min_wait: float = 1.0  # Exponential backoff minimum (seconds)
    retry_max_wait: float = 60.0  # Exponential backoff maximum (seconds)
    models: List[LLMModelConfig] = Field(default_factory=list)
    task_models: Dict[str, str] = Field(default_factory=lambda: {"default": "gemini-flash"})


class SlideLectureConfig(BaseModel):
    cleanup_temp: bool = False
    neighbor_images: Literal["next", "previous", "both", "none"] = "next"
    page_break_silence_seconds: float = 1.0
    summary_lookback_pages: int = -1
    transcript_lookback_pages: int = 3
    tts_language: Literal["source", "target"] = "source"


class SlideExplanationConfig(BaseModel):
    """Configuration for slide/screenshot explanation feature."""
    subtitle_context_window_seconds: float = 30.0


class SlidesConfig(BaseModel):
    lecture: SlideLectureConfig = Field(default_factory=SlideLectureConfig)
    explanation: SlideExplanationConfig = Field(default_factory=SlideExplanationConfig)


class WhisperCppConfig(BaseModel):
    model_path: str = "whisper.cpp/models/ggml-medium.bin"
    whisper_bin: str = "whisper.cpp/build/bin/whisper-cli"
    # Acceleration options (auto-detected if not specified)
    threads: Optional[int] = None  # None = auto-detect based on hardware
    flash_attn: bool = True  # Enable Flash Attention for Metal/CUDA
    beam_size: int = 5
    best_of: int = 5


class FasterWhisperConfig(BaseModel):
    model_size: str = "medium"
    device: str = "auto"
    compute_type: str = "auto"
    download_root: str = ""


class TranslationConfig(BaseModel):
    batch_size: int = 10
    target_language: str = "zh"


class EnhancementConfig(BaseModel):
    merge_window: int = 3
    overlap: int = 1
    max_output_chars: int = 160
    background_max_chars: int = 8000
    temperature: float = 0.2


class TimelineConfig(BaseModel):
    output_language: str = "zh"
    temperature: float = 0.3


class SubtitleConfig(BaseModel):
    engine: Literal["whisper_cpp", "faster_whisper"] = "whisper_cpp"
    source_language: str = "en"
    use_mock: bool = False
    whisper_cpp: WhisperCppConfig = Field(default_factory=WhisperCppConfig)
    faster_whisper: FasterWhisperConfig = Field(default_factory=FasterWhisperConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    enhancement: EnhancementConfig = Field(default_factory=EnhancementConfig)
    timeline: TimelineConfig = Field(default_factory=TimelineConfig)


class FishAudioConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.fish.audio"
    model: str = "s1"
    reference_id: str = ""
    base_speed: float = 1.0
    format: str = "wav"
    latency: str = "balanced"


class EdgeTTSConfig(BaseModel):
    voice: str = "zh-CN-XiaoxiaoNeural"


class TTSProviderConfig(BaseModel):
    name: str
    provider: Literal["fishaudio", "edge_tts"]
    fishaudio: Optional[FishAudioConfig] = None
    edge_tts: Optional[EdgeTTSConfig] = None


class TTSConfig(BaseModel):
    max_rpm: int = 10000  # Very high - won't hit in normal use
    max_retries: int = 3
    retry_min_wait: float = 1.0  # Exponential backoff minimum (seconds)
    retry_max_wait: float = 60.0  # Exponential backoff maximum (seconds)
    sample_rate: int = 44100
    max_sentence_duration: float = 8.0
    models: List[TTSProviderConfig] = Field(default_factory=list)
    task_models: Dict[str, str] = Field(default_factory=lambda: {"default": "edge-default"})


class NotesConfig(BaseModel):
    pass  # Placeholder for future notes-specific settings


class TasksConfig(BaseModel):
    timeout_seconds: Optional[int] = None


# ============================================================================
# Main Settings
# ============================================================================


class Settings(BaseSettings):
    """Main application settings loaded from config/conf.yaml."""

    model_config = SettingsConfigDict(
        yaml_file="config/conf.yaml",
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    server: ServerConfig = Field(default_factory=ServerConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    slides: SlidesConfig = Field(default_factory=SlidesConfig)
    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    tasks: TasksConfig = Field(default_factory=TasksConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Configure settings sources with YAML support."""
        if YamlConfigSettingsSource is not None:
            return (
                init_settings,
                env_settings,
                YamlConfigSettingsSource(settings_cls),
            )
        return (init_settings, env_settings)

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for backward compatibility."""
        return self.model_dump()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def load_config() -> Dict[str, Any]:
    """Load configuration as dictionary (backward compatibility)."""
    return get_settings().to_dict()


def reload_settings() -> Settings:
    """Force reload settings from disk."""
    get_settings.cache_clear()
    return get_settings()
