"""
Anthropic Claude LLM implementation.

Implements LLMProtocol for text generation using Claude models.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from anthropic import Anthropic

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

# Env vars that the Anthropic SDK auto-reads, which can conflict
# with explicit api_key when using a proxy endpoint.
_ANTHROPIC_ENV_VARS = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")


class AnthropicLLM:
    """
    Anthropic Claude LLM service.

    Implements LLMProtocol.

    Supports:
    - Anthropic API
    - Any Anthropic-compatible API (via base_url)
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        # Temporarily clear Anthropic env vars to prevent the SDK from
        # picking up ANTHROPIC_AUTH_TOKEN (sets Authorization: Bearer header)
        # which conflicts with the explicit api_key (sets x-api-key header),
        # causing "multiple conflicting API keys" errors on proxy endpoints.
        saved = {k: os.environ.pop(k) for k in _ANTHROPIC_ENV_VARS if k in os.environ}
        try:
            self._client = Anthropic(**client_kwargs)
        finally:
            os.environ.update(saved)

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> str:
        """
        Generate completion for prompt.

        Implements LLMProtocol.
        """
        temp = temperature if temperature is not None else self._temperature

        message_kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": temp,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            message_kwargs["system"] = system_prompt

        response = self._client.messages.create(**message_kwargs)

        # Extract text from response content blocks
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "".join(text_parts)

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> Iterator[str]:
        """
        Stream completion chunks.

        Implements LLMProtocol.
        """
        temp = temperature if temperature is not None else self._temperature

        message_kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": temp,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            message_kwargs["system"] = system_prompt

        with self._client.messages.stream(**message_kwargs) as stream:
            yield from stream.text_stream
