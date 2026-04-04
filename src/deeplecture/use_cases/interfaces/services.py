"""Service protocols - contracts for external services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from deeplecture.use_cases.dto.subtitle import ASRTranscriptionResult


class LLMProtocol(Protocol):
    """
    Contract for Large Language Model services.

    Implementations: OpenAILLM, AnthropicLLM, etc.
    """

    def complete(self, prompt: str, *, system_prompt: str | None = None, **kwargs) -> str:
        """Generate completion for prompt."""
        ...

    def stream(self, prompt: str, *, system_prompt: str | None = None, **kwargs) -> Iterator[str]:
        """Stream completion chunks."""
        ...


class ASRProtocol(Protocol):
    """
    Contract for Automatic Speech Recognition services.

    Implementations: WhisperEngine, FasterWhisperEngine
    """

    def transcribe(self, audio_path: Path, *, language: str = "en") -> ASRTranscriptionResult:
        """
        Transcribe audio file to segments.

        Args:
            audio_path: Path to audio/video file
            language: Language code for transcription

        Returns:
            Transcribed segments plus the resolved language used for storage
        """
        ...


class TTSProtocol(Protocol):
    """
    Contract for Text-to-Speech services.

    Implementations: FishTTS, EdgeTTS
    """

    def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        """
        Synthesize text to audio.

        Args:
            text: Text to synthesize
            voice: Voice identifier

        Returns:
            Audio data as bytes (WAV format)
        """
        ...

    def synthesize_to_file(self, text: str, output_path: Path, *, voice: str | None = None) -> None:
        """Synthesize text and save to file."""
        ...
