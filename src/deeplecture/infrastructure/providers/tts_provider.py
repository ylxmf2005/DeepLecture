"""TTS provider - runtime model selection with caching.

Implements TTSProviderProtocol:
- Validates model_id against configured models
- Caches wrapped instances by model name
- Shares rate limiter across all models
- Applies retry configuration from settings
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from deeplecture.infrastructure.gateways.tts import EdgeTTS, FishAudioTTS
from deeplecture.infrastructure.shared.decorators import RateLimitedTTS, RetryableTTS
from deeplecture.infrastructure.shared.rate_limiter import RateLimiter
from deeplecture.infrastructure.shared.retry import RetryConfig
from deeplecture.use_cases.interfaces.tts_provider import TTSModelInfo

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deeplecture.config.settings import TTSConfig, TTSModelConfig
    from deeplecture.use_cases.interfaces.services import TTSProtocol


class TTSProvider:
    """
    TTS provider with runtime model selection.

    Thread-safe caching of wrapped TTS instances.
    All models share a single rate limiter (global RPM budget).
    """

    def __init__(self, config: TTSConfig) -> None:
        self._config = config

        # Build name → config mapping
        self._models_by_name: dict[str, TTSModelConfig] = {}
        for model_cfg in config.models:
            if model_cfg.name in self._models_by_name:
                raise ValueError(f"Duplicate TTS model name: {model_cfg.name!r}")
            self._models_by_name[model_cfg.name] = model_cfg

        # Shared infrastructure
        self._rate_limiter = RateLimiter(max_rpm=config.max_rpm)
        self._retry_config = RetryConfig(
            max_retries=config.max_retries,
            min_wait=config.retry_min_wait,
            max_wait=config.retry_max_wait,
        )

        # Instance cache
        self._instances: dict[str, TTSProtocol] = {}
        self._lock = threading.RLock()

    def get(self, model_id: str | None = None) -> TTSProtocol:
        """
        Get TTS instance by model name.

        Args:
            model_id: Model name from config. None uses default.

        Returns:
            Wrapped TTSProtocol instance (rate-limited + retryable).

        Raises:
            ValueError: If model_id not found or no models configured.
        """
        name = model_id if model_id else self.get_default_model_name()
        model_cfg = self._models_by_name.get(name)
        if model_cfg is None:
            valid = ", ".join(self._models_by_name.keys()) or "<none>"
            raise ValueError(f"Unknown TTS model: {name!r}. Available: {valid}")

        # Double-checked locking for thread safety
        if name in self._instances:
            return self._instances[name]

        with self._lock:
            if name not in self._instances:
                self._instances[name] = self._build(model_cfg)
            return self._instances[name]

    def get_default_model_name(self) -> str:
        """Return first model name from config."""
        if not self._config.models:
            raise ValueError(
                "TTS not configured: no models in settings.tts.models. " "Add model configuration to config/conf.yaml"
            )
        return self._config.models[0].name

    def list_models(self) -> Sequence[TTSModelInfo]:
        """List all configured TTS models."""
        return tuple(TTSModelInfo(name=cfg.name, provider=cfg.provider) for cfg in self._config.models)

    def _build(self, cfg: TTSModelConfig) -> TTSProtocol:
        """Build wrapped TTS instance based on provider type."""
        provider = (cfg.provider or "").lower()

        if provider == "fishaudio":
            if cfg.fishaudio is None:
                raise ValueError(f"TTS model {cfg.name!r} has provider='fishaudio' but no fishaudio config")
            fish_cfg = cfg.fishaudio
            base: TTSProtocol = FishAudioTTS(
                api_key=fish_cfg.api_key or None,
                base_url=fish_cfg.base_url,
                model=fish_cfg.model,
                reference_id=fish_cfg.reference_id or None,
                audio_format=fish_cfg.format,
                latency=fish_cfg.latency,
                speed=fish_cfg.base_speed,
            )
        else:
            # Default to EdgeTTS
            edge_cfg = cfg.edge_tts
            voice = edge_cfg.voice if edge_cfg else "zh-CN-XiaoxiaoNeural"
            base = EdgeTTS(voice=voice)

        rate_limited = RateLimitedTTS(base, self._rate_limiter)
        return RetryableTTS(rate_limited, self._retry_config)
