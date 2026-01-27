"""LLM provider - runtime model selection with caching.

Implements LLMProviderProtocol:
- Validates model_id against configured models
- Caches wrapped instances by model name
- Shares rate limiter across all models
- Applies retry configuration from settings
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from deeplecture.infrastructure.gateways.openai import OpenAILLM
from deeplecture.infrastructure.shared.decorators import RateLimitedLLM, RetryableLLM
from deeplecture.infrastructure.shared.rate_limiter import RateLimiter
from deeplecture.infrastructure.shared.retry import RetryConfig
from deeplecture.use_cases.interfaces.llm_provider import LLMModelInfo

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from deeplecture.config.settings import LLMConfig, LLMModelConfig
    from deeplecture.use_cases.interfaces.services import LLMProtocol


class LLMProvider:
    """
    LLM provider with runtime model selection.

    Thread-safe caching of wrapped LLM instances.
    All models share a single rate limiter (global RPM budget).
    """

    def __init__(
        self,
        config: LLMConfig,
        allowed_image_roots: frozenset[Path],
    ) -> None:
        self._config = config
        self._allowed_image_roots = allowed_image_roots

        # Build name → config mapping
        self._models_by_name: dict[str, LLMModelConfig] = {}
        for model_cfg in config.models:
            if model_cfg.name in self._models_by_name:
                raise ValueError(f"Duplicate LLM model name: {model_cfg.name!r}")
            self._models_by_name[model_cfg.name] = model_cfg

        # Shared infrastructure
        self._rate_limiter = RateLimiter(max_rpm=config.max_rpm)
        self._retry_config = RetryConfig(
            max_retries=config.max_retries,
            min_wait=config.retry_min_wait,
            max_wait=config.retry_max_wait,
        )

        # Instance cache
        self._instances: dict[str, LLMProtocol] = {}
        self._lock = threading.RLock()

    def get(self, model_id: str | None = None) -> LLMProtocol:
        """
        Get LLM instance by model name.

        Args:
            model_id: Model name from config. None uses default.

        Returns:
            Wrapped LLMProtocol instance (rate-limited + retryable).

        Raises:
            ValueError: If model_id not found or no models configured.
        """
        name = model_id if model_id else self.get_default_model_name()
        model_cfg = self._models_by_name.get(name)
        if model_cfg is None:
            valid = ", ".join(self._models_by_name.keys()) or "<none>"
            raise ValueError(f"Unknown LLM model: {name!r}. Available: {valid}")

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
                "LLM not configured: no models in settings.llm.models. " "Add model configuration to config/conf.yaml"
            )
        return self._config.models[0].name

    def list_models(self) -> Sequence[LLMModelInfo]:
        """List all configured LLM models."""
        return tuple(LLMModelInfo(name=cfg.name, provider=cfg.provider, model=cfg.model) for cfg in self._config.models)

    def _build(self, cfg: LLMModelConfig) -> LLMProtocol:
        """Build wrapped LLM instance."""
        base = OpenAILLM(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            connect_timeout=self._config.connect_timeout,
            allowed_image_roots=self._allowed_image_roots,
        )
        rate_limited = RateLimitedLLM(base, self._rate_limiter)
        return RetryableLLM(rate_limited, self._retry_config)
