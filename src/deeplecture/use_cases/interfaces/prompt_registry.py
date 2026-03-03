"""Prompt registry protocol - runtime prompt selection by function ID.

Prompts are indexed by func_id (e.g., "note_outline", "timeline_segmentation").
Each func_id can have multiple implementations (impl_id).

The registry owns:
- mapping from (func_id, impl_id) to a PromptBuilder
- defaults and fallback behavior
- listing for config endpoints
- a preview mechanism for UI (get_prompt_text)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class PromptSpec:
    """Concrete prompt payload to pass into an LLM."""

    user_prompt: str
    system_prompt: str | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class PromptInfo:
    """Metadata for prompt listing (for frontend config + selection)."""

    impl_id: str
    name: str
    description: str | None = None
    is_default: bool = False


class PromptBuilder(Protocol):
    """
    Contract for building prompts.

    Each implementation represents one version/style of a prompt function.
    Implementations should be small, pure, and deterministic.
    """

    @property
    def impl_id(self) -> str:
        """Stable identifier used by API/UI (e.g., 'default', 'detailed')."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name for UI."""
        ...

    @property
    def description(self) -> str | None:
        """Optional UI description."""
        ...

    def build(self, **kwargs: Any) -> PromptSpec:
        """
        Build the prompt for actual execution.

        Args:
            **kwargs: Task-specific parameters (e.g., language, context, etc.)

        Returns:
            PromptSpec with user_prompt and optional system_prompt.
        """
        ...

    def get_preview_text(self) -> str:
        """
        Return a safe preview text (no user data) for UI display.

        This is shown in Settings when user selects different prompt styles.
        """
        ...

    def get_raw_templates(self) -> dict[str, str]:
        """Return raw system/user template strings for editor pre-filling."""
        ...


class PromptRegistryProtocol(Protocol):
    """Contract for prompt selection and discovery by func_id."""

    def get(self, func_id: str, impl_id: str | None = None) -> PromptBuilder:
        """
        Get a prompt builder for (func_id, impl_id).

        Args:
            func_id: Function identifier (e.g., "note_outline", "ask_video")
            impl_id: Implementation identifier. If None, returns the default.

        Returns:
            PromptBuilder instance.

        Raises:
            ValueError: If func_id or impl_id is not found.
        """
        ...

    def get_default_impl_id(self, func_id: str) -> str:
        """Get the default implementation ID for a function."""
        ...

    def list_func_ids(self) -> Sequence[str]:
        """List all known func_ids that have prompt implementations."""
        ...

    def list_implementations(self, func_id: str) -> Sequence[PromptInfo]:
        """List available implementations for a func_id."""
        ...

    def get_prompt_text(self, func_id: str, impl_id: str) -> str:
        """
        Return a human-readable preview text for UI.

        This is the preview shown when user browses prompt options.
        """
        ...

    def get_all_defaults(self) -> Mapping[str, str]:
        """
        Return all func_id -> default_impl_id mappings.

        Used for config endpoint to provide defaults to frontend.
        """
        ...
