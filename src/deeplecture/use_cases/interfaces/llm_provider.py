"""LLM provider protocol - runtime model selection.

This protocol sits between UseCases and concrete LLM implementations.

Key point: UseCases must NOT construct infrastructure clients (OpenAI, etc.).
They request an LLM instance by model_id and let the provider:
- validate model names
- apply defaults
- cache/reuse instances
- expose model listing for config endpoints
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deeplecture.use_cases.interfaces.services import LLMProtocol


@dataclass(frozen=True, slots=True)
class LLMModelInfo:
    """Metadata for a configured LLM model (for frontend listings)."""

    name: str
    provider: str
    model: str


class LLMProviderProtocol(Protocol):
    """
    Contract for resolving LLM instances at runtime.

    The provider is responsible for mapping model_id to a concrete
    LLMProtocol implementation, applying defaults and validation.
    """

    def get(self, model_id: str | None = None) -> LLMProtocol:
        """
        Return an LLM instance by model name.

        Args:
            model_id: Model name to use. If None, returns the default model.

        Returns:
            LLMProtocol instance (cached).

        Raises:
            ValueError: If model_id is not found in configuration.
        """
        ...

    def get_default_model_name(self) -> str:
        """Return the configured default model name."""
        ...

    def list_models(self) -> Sequence[LLMModelInfo]:
        """List all configured models (for /api/config)."""
        ...
