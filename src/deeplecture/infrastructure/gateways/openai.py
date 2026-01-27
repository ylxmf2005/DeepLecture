"""
OpenAI-compatible LLM implementation.

Implements LLMProtocol for text generation.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from openai import OpenAI

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

logger = logging.getLogger(__name__)

# Allowed image extensions for security
_ALLOWED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})
_IMAGE_MIME_BY_EXT: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class OpenAILLM:
    """
    OpenAI-compatible LLM service.

    Implements LLMProtocol.

    Supports:
    - OpenAI API
    - Any OpenAI-compatible API (via base_url)
    - Vision models (image input)
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
        temperature: float = 0.7,
        connect_timeout: float = 30.0,
        allowed_image_roots: frozenset[Path] | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._allowed_image_roots = allowed_image_roots

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        # Use custom timeout with longer connect timeout for third-party APIs
        client_kwargs["timeout"] = httpx.Timeout(
            connect=connect_timeout,
            read=600.0,
            write=600.0,
            pool=600.0,
        )

        self._client = OpenAI(**client_kwargs)

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        image_path: str | Sequence[str] | None = None,
    ) -> str:
        """
        Generate completion for prompt.

        Implements LLMProtocol.
        """
        messages = self._build_messages(prompt, system_prompt, image_path)
        temp = temperature if temperature is not None else self._temperature

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore
            temperature=temp,
        )

        return response.choices[0].message.content or ""

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """
        Stream completion chunks.

        Implements LLMProtocol.
        """
        messages = self._build_messages(prompt, system_prompt)
        temp = temperature if temperature is not None else self._temperature

        stream = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore
            temperature=temp,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _build_messages(
        self,
        prompt: str,
        system_prompt: str | None = None,
        image_path: str | Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Build message list for API call."""
        messages: list[dict[str, Any]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build user content
        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        if image_path:
            paths = [image_path] if isinstance(image_path, str) else list(image_path)
            for p in paths:
                image_url = self._encode_image(p)
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    }
                )

        messages.append({"role": "user", "content": user_content})
        return messages

    def _encode_image(self, path: str) -> str:
        """
        Encode image to data URL or return as-is if URL.

        Security: Validates that the path:
        1. Is a URL (http/https) - passed through as-is
        2. Is an absolute path under allowed roots (if configured)
        3. Has an allowed image extension
        4. Does not contain path traversal sequences

        Raises:
            ValueError: If path is invalid or not allowed
        """
        if path.startswith(("http://", "https://")):
            return path

        # Validate local file path
        resolved = Path(path).resolve()

        # Check for path traversal
        if ".." in path:
            raise ValueError(f"Path traversal not allowed: {path}")

        # Check extension
        ext = resolved.suffix.lower()
        if ext not in _ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(f"Invalid image extension: {ext}")

        # Verify path exists and is a file
        if not resolved.is_file():
            raise ValueError(f"Image file not found: {path}")

        # Check against allowed roots if configured
        if self._allowed_image_roots and not any(
            self._is_path_under(resolved, root) for root in self._allowed_image_roots
        ):
            raise ValueError(f"Image path not in allowed directories: {path}")

        with open(resolved, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        mime = _IMAGE_MIME_BY_EXT.get(ext, "image/jpeg")
        return f"data:{mime};base64,{encoded}"

    @staticmethod
    def _is_path_under(path: Path, root: Path) -> bool:
        """Check if path is under root directory."""
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
