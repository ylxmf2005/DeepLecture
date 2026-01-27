"""LLM provider protocol for runtime model selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces.services import LLMProtocol


@dataclass
class LLMModelInfo:
    """Information about an LLM model."""

    model_id: str
    display_name: str
    provider: str  # openai, anthropic, etc.
    context_window: int
    supports_json: bool = True


class LLMProviderProtocol(Protocol):
    """Protocol for runtime LLM model selection."""

    def get(self, model_id: str | None = None) -> LLMProtocol:
        """Get an LLM instance.

        Args:
            model_id: Optional model identifier. If None, uses default.

        Returns:
            LLM instance.
        """
        ...

    def list_models(self) -> list[LLMModelInfo]:
        """List available models.

        Returns:
            List of available model info.
        """
        ...

    @property
    def default_model(self) -> str:
        """Default model identifier."""
        ...
