"""TTS provider protocol for runtime voice selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces.services import TTSProtocol


@dataclass
class TTSModelInfo:
    """Information about a TTS voice/model."""

    voice_id: str
    display_name: str
    provider: str  # openai, elevenlabs, etc.
    language: str
    gender: str | None = None


class TTSProviderProtocol(Protocol):
    """Protocol for runtime TTS voice selection."""

    def get(self, voice_id: str | None = None) -> TTSProtocol:
        """Get a TTS instance.

        Args:
            voice_id: Optional voice identifier. If None, uses default.

        Returns:
            TTS instance.
        """
        ...

    def list_voices(self, language: str | None = None) -> list[TTSModelInfo]:
        """List available voices.

        Args:
            language: Optional filter by language.

        Returns:
            List of available voice info.
        """
        ...

    @property
    def default_voice(self) -> str:
        """Default voice identifier."""
        ...
