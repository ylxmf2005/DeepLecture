"""Prompt registry protocol for runtime prompt selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass
class PromptSpec:
    """Specification for a prompt to send to LLM."""

    user_prompt: str
    system_prompt: str | None = None


@dataclass
class PromptInfo:
    """Information about a registered prompt."""

    func_id: str  # Functional identifier (e.g., "note_outline")
    impl_id: str  # Implementation identifier (e.g., "default", "v2")
    description: str


# Type alias for prompt builder functions
PromptBuilder = Callable[..., PromptSpec]


class PromptBuilderProtocol(Protocol):
    """Protocol for prompt builder."""

    def build(self, **kwargs: Any) -> PromptSpec:
        """Build a prompt specification.

        Args:
            **kwargs: Builder-specific arguments.

        Returns:
            PromptSpec with user and system prompts.
        """
        ...


class PromptRegistryProtocol(Protocol):
    """Protocol for prompt registry with runtime selection."""

    def get(self, func_id: str, impl_id: str | None = None) -> PromptBuilderProtocol:
        """Get a prompt builder.

        Args:
            func_id: Functional identifier (e.g., "note_outline").
            impl_id: Optional implementation identifier. If None, uses default.

        Returns:
            PromptBuilder instance.
        """
        ...

    def list_prompts(self, func_id: str | None = None) -> list[PromptInfo]:
        """List registered prompts.

        Args:
            func_id: Optional filter by function identifier.

        Returns:
            List of prompt info.
        """
        ...

    def register(
        self,
        func_id: str,
        impl_id: str,
        builder: PromptBuilderProtocol,
        *,
        description: str = "",
        is_default: bool = False,
    ) -> None:
        """Register a prompt builder.

        Args:
            func_id: Functional identifier.
            impl_id: Implementation identifier.
            builder: Prompt builder instance.
            description: Optional description.
            is_default: Whether this is the default implementation.
        """
        ...
