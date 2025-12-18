"""
Service decorators for rate limiting and retry.

Provides decorator classes that wrap LLM and TTS services
to add cross-cutting concerns without modifying the base implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deeplecture.infrastructure.shared.retry import with_retry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from deeplecture.infrastructure.shared.rate_limiter import RateLimiter
    from deeplecture.infrastructure.shared.retry import RetryConfig
    from deeplecture.use_cases.interfaces.services import LLMProtocol, TTSProtocol


class RateLimitedLLM:
    """
    LLM decorator that enforces rate limiting.

    Acquires a token from the rate limiter before each API call.
    """

    def __init__(self, inner: LLMProtocol, limiter: RateLimiter) -> None:
        self._inner = inner
        self._limiter = limiter

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        self._limiter.acquire()
        return self._inner.complete(prompt, system_prompt=system_prompt, **kwargs)

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs,
    ) -> Iterator[str]:
        self._limiter.acquire()
        yield from self._inner.stream(prompt, system_prompt=system_prompt, **kwargs)


class RetryableLLM:
    """
    LLM decorator that adds retry logic with exponential backoff.

    Retries failed API calls according to the retry configuration.
    """

    def __init__(self, inner: LLMProtocol, config: RetryConfig) -> None:
        self._inner = inner
        self._config = config

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        retryable = with_retry(
            self._inner.complete,
            config=self._config,
            logger_name="deeplecture.llm",
        )
        return retryable(prompt, system_prompt=system_prompt, **kwargs)

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        **kwargs,
    ) -> Iterator[str]:
        # Note: Retry on stream is applied at connection level only
        # Once streaming starts, retries are not applied mid-stream
        retryable = with_retry(
            self._inner.stream,
            config=self._config,
            logger_name="deeplecture.llm",
        )
        yield from retryable(prompt, system_prompt=system_prompt, **kwargs)


class RateLimitedTTS:
    """
    TTS decorator that enforces rate limiting.

    Acquires a token from the rate limiter before each synthesis call.
    """

    def __init__(self, inner: TTSProtocol, limiter: RateLimiter) -> None:
        self._inner = inner
        self._limiter = limiter

    def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        self._limiter.acquire()
        return self._inner.synthesize(text, voice=voice)

    def synthesize_to_file(self, text: str, output_path: Path, *, voice: str | None = None) -> None:
        self._limiter.acquire()
        self._inner.synthesize_to_file(text, output_path, voice=voice)


class RetryableTTS:
    """
    TTS decorator that adds retry logic with exponential backoff.

    Retries failed TTS synthesis according to the retry configuration.
    """

    def __init__(self, inner: TTSProtocol, config: RetryConfig) -> None:
        self._inner = inner
        self._config = config

    def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        retryable = with_retry(
            self._inner.synthesize,
            config=self._config,
            logger_name="deeplecture.tts",
        )
        return retryable(text, voice=voice)

    def synthesize_to_file(self, text: str, output_path: Path, *, voice: str | None = None) -> None:
        retryable = with_retry(
            self._inner.synthesize_to_file,
            config=self._config,
            logger_name="deeplecture.tts",
        )
        retryable(text, output_path, voice=voice)
