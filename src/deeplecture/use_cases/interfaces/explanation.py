"""Explanation storage protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExplanationStorageProtocol(Protocol):
    """
    Contract for explanation persistence.

    Implementations: FsExplanationStorage (repository layer)
    """

    def load(self, content_id: str) -> list[dict[str, Any]]:
        """Load explanation history for a content item."""
        ...

    def save(self, content_id: str, explanation: dict[str, Any]) -> None:
        """Append an explanation entry for a content item."""
        ...

    def delete(self, content_id: str, explanation_id: str) -> bool:
        """Delete an explanation entry by ID."""
        ...

    def update(self, content_id: str, explanation_id: str, updates: dict[str, Any]) -> bool:
        """Update an existing explanation entry by ID."""
        ...
