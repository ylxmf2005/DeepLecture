"""LLM and external service protocol definitions."""

from __future__ import annotations

from typing import Protocol


class LLMProtocol(Protocol):
    """Protocol for LLM completion service."""

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Complete a prompt using the LLM.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated text.
        """
        ...


class ASRProtocol(Protocol):
    """Protocol for automatic speech recognition service."""

    def transcribe(
        self,
        audio_path: str,
        *,
        language: str | None = None,
    ) -> list[dict]:
        """Transcribe audio to text segments.

        Args:
            audio_path: Path to audio file.
            language: Optional language hint.

        Returns:
            List of segment dictionaries with start, end, text.
        """
        ...


class TTSProtocol(Protocol):
    """Protocol for text-to-speech service."""

    def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        output_path: str | None = None,
    ) -> bytes | str:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize.
            voice: Optional voice identifier.
            output_path: Optional output file path.

        Returns:
            Audio bytes or path to output file.
        """
        ...
