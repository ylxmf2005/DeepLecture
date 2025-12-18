"""TTS provider protocol - runtime model selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deeplecture.use_cases.interfaces.services import TTSProtocol


@dataclass(frozen=True, slots=True)
class TTSModelInfo:
    """Metadata for a configured TTS model (for frontend listings)."""

    name: str
    provider: str


class TTSProviderProtocol(Protocol):
    """
    Contract for resolving TTS instances at runtime.

    The provider applies defaults/validation and exposes model listing for
    config endpoints.
    """

    def get(self, model_id: str | None = None) -> TTSProtocol:
        """
        Return a TTS engine by model name.

        Args:
            model_id: Model name to use. If None, returns the default model.

        Returns:
            TTSProtocol instance (cached).

        Raises:
            ValueError: If model_id is not found in configuration.
        """
        ...

    def get_default_model_name(self) -> str:
        """Return the configured default model name."""
        ...

    def list_models(self) -> Sequence[TTSModelInfo]:
        """List all configured models (for /api/config)."""
        ...
