"""
Factory for creating TTS (text-to-speech) service instances.

This mirrors the LLMFactory pattern and allows us to swap out
different TTS providers behind a common interface.
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from deeplecture.infra.rate_limiter import RateLimiter
from deeplecture.config.config import load_config

logger = logging.getLogger(__name__)


_TTS_FILTER_PATTERN = re.compile(r"[()*\-`]+")


def _filter_tts_text(text: str) -> str:
    """Normalize text before sending it to the TTS backend."""
    s = text.replace("\r", " ")
    s = s.replace("_", " ")
    s = _TTS_FILTER_PATTERN.sub("", s)
    return " ".join(s.split())


class TTS(ABC):
    """Abstract base class for TTS services."""

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """
        Preferred file extension (including leading dot) for synthesized audio.

        This is used by higher-level code to choose appropriate filenames for
        temporary files and ffmpeg processing (e.g. '.wav', '.mp3').
        """
        raise NotImplementedError

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """
        Synthesize speech audio for the given text.

        Args:
            text: Text to convert to speech.

        Returns:
            Raw audio bytes in the configured output format.
        """
        raise NotImplementedError


class FishAudioTTS(TTS):
    """
    TTS implementation backed by Fish Audio's Python SDK.

    This class only handles "text -> audio bytes". Higher-level concerns
    like subtitle alignment, per-sentence duration control, and ffmpeg
    post-processing are handled in the subtitle/voiceover.py module.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config is None:
            config = load_config()

        tts_cfg = (config or {}).get("tts") or {}
        provider = str(tts_cfg.get("provider", "fishaudio"))
        if provider != "fishaudio":
            raise ValueError(f"FishAudioTTS can only be used with provider='fishaudio', got {provider!r}")

        fish_cfg = tts_cfg.get("fishaudio", {}) or {}

        try:
            from fishaudio import FishAudio  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - handled at runtime
            raise ImportError(
                "Fish Audio Python SDK not found. Install it with "
                "'pip install \"fish-audio-sdk>=1.0.0,<2.0.0\"'."
            ) from exc

        # API configuration
        api_key = fish_cfg.get("api_key") or os.getenv("FISH_API_KEY", "")
        if not api_key:
            logger.warning(
                "No TTS API key found. Set tts.fishaudio.api_key in conf.yaml or"
                "FISH_API_KEY environment variable."
            )

        base_url = str(fish_cfg.get("base_url") or "https://api.fish.audio")

        # TTS model and default parameters
        self.model: str = str(fish_cfg.get("model", "s1"))
        self.reference_id: Optional[str] = (
            str(fish_cfg["reference_id"]).strip() or None
            if "reference_id" in fish_cfg
            else None
        )
        self.audio_format: str = str(fish_cfg.get("format", "wav"))
        self.latency: str = str(fish_cfg.get("latency", "balanced"))
        # Map Fish Audio format to a reasonable file extension.
        # Fish Audio supports: mp3, wav, pcm, opus.
        fmt = self.audio_format.lower()
        if fmt == "mp3":
            self._file_extension = ".mp3"
        elif fmt == "wav":
            self._file_extension = ".wav"
        elif fmt == "opus":
            self._file_extension = ".opus"
        else:
            # Default to .wav for unknown/pcm formats
            self._file_extension = ".wav"

        # Base speaking speed (0.5-2.0), clamped to Fish Audio's allowed range
        base_speed = float(fish_cfg.get("base_speed", 1.0))
        if base_speed <= 0:
            base_speed = 1.0
        self.base_speed: float = max(0.5, min(2.0, base_speed))

        # Underlying Fish Audio client
        self.client = FishAudio(api_key=api_key or None, base_url=base_url)  # type: ignore[call-arg]

        logger.debug("Initialized FishAudio TTS with model=%s, format=%s", self.model, self.audio_format)

    @property
    def file_extension(self) -> str:
        return self._file_extension

    def synthesize(self, text: str) -> bytes:
        """Generate speech audio bytes for the given text."""
        clean_text = _filter_tts_text(text)
        if not clean_text:
            return b""

        return self.client.tts.convert(  # type: ignore[union-attr]
            text=clean_text,
            reference_id=self.reference_id,
            format=self.audio_format,  # type: ignore[arg-type]
            latency=self.latency,  # type: ignore[arg-type]
            speed=self.base_speed,
            model=self.model,  # type: ignore[arg-type]
        )


class EdgeTTSTTS(TTS):
    """
    TTS implementation backed by edge-tts (Microsoft Edge online TTS).

    This is useful for local testing as it does not require a paid API key.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config is None:
            config = load_config()

        tts_cfg = (config or {}).get("tts") or {}

        provider = str(tts_cfg.get("provider", "edge_tts"))
        if provider != "edge_tts":
            raise ValueError(f"EdgeTTSTTS can only be used with provider='edge_tts', got {provider!r}")

        try:
            import edge_tts  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - handled at runtime
            raise ImportError(
                "edge-tts is not installed. Install it with 'pip install edge-tts'. "
                "See https://github.com/rany2/edge-tts for details."
            ) from exc

        self._edge_tts = edge_tts

        edge_cfg = tts_cfg.get("edge_tts", {}) or {}
        # Default voice: a multilingual English voice; user can override to zh-CN-XiaoxiaoNeural, etc.
        self.voice: str = str(edge_cfg.get("voice", "en-US-AvaMultilingualNeural"))

        logger.debug("Initialized Edge TTS with voice=%s", self.voice)

        # Edge TTS default format is MP3; we standardize on mp3 container.
        self._file_extension = ".mp3"

    @property
    def file_extension(self) -> str:
        return self._file_extension

    def synthesize(self, text: str) -> bytes:
        """Generate speech audio bytes for the given text using edge-tts."""
        clean_text = _filter_tts_text(text)
        if not clean_text:
            return b""

        # edge-tts is async-first but exposes synchronous helpers.
        communicate = self._edge_tts.Communicate(clean_text, self.voice)

        # Use save_sync into a temporary mp3 file so that we get a fully
        # well-formed container instead of concatenated raw frames.
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=self._file_extension, delete=False) as tmp:
            tmp_path = tmp.name

        try:
            communicate.save_sync(tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                # Best-effort cleanup; ignore if removal fails.
                pass


class RateLimitedTTS(TTS):
    """
    TTS decorator that enforces a RateLimiter around synthesize calls.

    This keeps provider-specific implementations untouched while ensuring
    all outbound TTS requests respect a shared max RPM configuration.
    """

    def __init__(self, inner: TTS, limiter: RateLimiter) -> None:
        self._inner = inner
        self._limiter = limiter

    @property
    def file_extension(self) -> str:
        return self._inner.file_extension

    def synthesize(self, text: str) -> bytes:
        self._limiter.acquire()
        return self._inner.synthesize(text)


class TTSRegistry:
    """
    Registry for configured TTS providers and task-to-provider mappings.

    Mirrors the LLM ModelRegistry pattern to allow multiple providers
    to coexist with hot-swappable task routing while remaining backward
    compatible with the legacy single-provider config.
    """

    def __init__(self, tts_config: Optional[Dict[str, Any]] = None) -> None:
        if tts_config is None:
            cfg = load_config()
            if isinstance(cfg, dict):
                tts_config = cfg.get("tts") or {}
            else:
                tts_config = {}

        self._tts_config: Dict[str, Any] = tts_config or {}
        self._providers: Dict[str, Dict[str, Any]] = {}
        self._task_models: Dict[str, str] = {}
        self._default_provider_name = "default"
        self._build_registry()

    def _build_registry(self) -> None:
        cfg = self._tts_config or {}

        base: Dict[str, Any] = {}
        for key, value in cfg.items():
            if key in ("providers", "task_models", "task_providers"):
                continue
            base[key] = value

        raw_providers = cfg.get("providers")
        if isinstance(raw_providers, list):
            for entry in raw_providers:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "").strip()
                if not name:
                    continue
                provider_type = str(entry.get("provider") or "").strip()
                if not provider_type:
                    continue
                provider_cfg: Dict[str, Any] = dict(base)
                provider_cfg.update(entry)
                self._providers[name] = provider_cfg

        if not self._providers:
            raise ValueError(
                "No TTS providers configured. Please add at least one provider "
                "to the 'tts.providers' list in your config file."
            )

        # Support both task_models (new) and task_providers (legacy)
        task_cfg = cfg.get("task_models") or cfg.get("task_providers")
        default_from_task: Optional[str] = None
        if isinstance(task_cfg, dict):
            raw_default = task_cfg.get("default")
            default_from_task = str(raw_default or "").strip() or None

        if default_from_task and default_from_task in self._providers:
            self._default_provider_name = default_from_task
        else:
            self._default_provider_name = next(iter(self._providers))

        if isinstance(task_cfg, dict):
            for task, provider in task_cfg.items():
                task_name = str(task or "").strip()
                provider_name = str(provider or "").strip()
                if not task_name or not provider_name:
                    continue
                if provider_name not in self._providers:
                    logger.warning(
                        "Ignoring TTS task mapping for %s -> %s: provider not registered",
                        task_name,
                        provider_name,
                    )
                    continue
                self._task_models[task_name] = provider_name

    def get_provider_config(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Resolve provider config by name, falling back to default."""
        if not self._providers:
            return {}
        target = name or self._default_provider_name
        cfg = self._providers.get(target)
        if cfg is not None:
            return cfg
        return self._providers[self._default_provider_name]

    def get_task_provider_config(self, task: str) -> Dict[str, Any]:
        """Resolve provider config for a task, fallback to default."""
        if not self._providers:
            return {}
        task_name = str(task or "").strip()
        provider_name = self._task_models.get(task_name) or self._default_provider_name
        cfg = self._providers.get(provider_name)
        if cfg is not None:
            return cfg
        return self._providers[self._default_provider_name]

    def list_providers(self) -> List[Dict[str, str]]:
        """Return provider metadata suitable for API responses."""
        return [
            {
                "name": name,
                "provider": cfg.get("provider", ""),
            }
            for name, cfg in self._providers.items()
        ]

    def get_task_models(self) -> Dict[str, str]:
        """Return the task-to-provider mapping."""
        return dict(self._task_models)

    # Backward compatibility alias
    get_task_providers = get_task_models

    def get_default_provider_name(self) -> str:
        """Return the logical default provider name."""
        return self._default_provider_name

    def update_task_models(self, new_mappings: Dict[str, str]) -> None:
        """Hot-update task-to-provider mappings."""
        for task, provider in new_mappings.items():
            task_name = str(task or "").strip()
            provider_name = str(provider or "").strip()
            if not task_name or not provider_name:
                continue
            if provider_name in self._providers:
                self._task_models[task_name] = provider_name

    # Backward compatibility alias
    update_task_providers = update_task_models


class TTSFactory:
    """Factory for creating TTS service instances."""

    def __init__(
        self,
        registry: Optional[TTSRegistry] = None,
        limiter: Optional[RateLimiter] = None,
    ) -> None:
        cfg = load_config() or {}
        tts_cfg = cfg.get("tts") or {}

        # Use provided limiter or create one from config
        if limiter is not None:
            self._limiter = limiter
        else:
            # Fallback: create limiter from tts.max_rpm config
            max_rpm = int(tts_cfg.get("max_rpm", 60) or 60)
            self._limiter = RateLimiter(max_rpm=max_rpm)

        self._registry = registry or TTSRegistry(tts_cfg)

    def get_tts(
        self,
        config: Optional[Dict[str, Any]] = None,
        provider_name: Optional[str] = None,
    ) -> TTS:
        """
        Get a TTS service instance.

        Args:
            config: Optional configuration override. When provided, the
                registry is bypassed and the config is used as-is.
            provider_name: Optional logical provider name registered in
                the TTS registry. Ignored if ``config`` is provided.
        """
        if config is not None:
            base = self._create_tts_from_config(config)
            return RateLimitedTTS(base, self._limiter)

        provider_cfg = self._registry.get_provider_config(provider_name)
        base = self._create_tts_from_config({"tts": provider_cfg})
        return RateLimitedTTS(base, self._limiter)

    def get_tts_for_task(self, task_name: str) -> TTS:
        """
        Get a TTS instance associated with a logical task name using the
        registry's task-to-provider mapping.
        """
        provider_cfg = self._registry.get_task_provider_config(task_name)
        base = self._create_tts_from_config({"tts": provider_cfg})
        return RateLimitedTTS(base, self._limiter)

    def get_registry(self) -> TTSRegistry:
        """Expose the registry for inspection/testing."""
        return self._registry

    def update_task_models(self, new_mappings: Dict[str, str]) -> None:
        """Hot-update task-to-provider mappings."""
        self._registry.update_task_models(new_mappings)

    # Backward compatibility alias
    update_task_providers = update_task_models

    def _create_tts_from_config(self, config: Dict[str, Any]) -> TTS:
        tts_cfg = (config or {}).get("tts") or {}
        provider = str(tts_cfg.get("provider", "fishaudio"))

        if provider == "fishaudio":
            return FishAudioTTS(config)
        if provider == "edge_tts":
            return EdgeTTSTTS(config)
        raise ValueError(f"Unsupported TTS provider: {provider}")
