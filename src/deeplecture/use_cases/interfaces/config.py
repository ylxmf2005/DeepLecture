"""Content configuration storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.domain.entities.config import ContentConfig


class ContentConfigStorageProtocol(Protocol):
    """Contract for per-video configuration persistence."""

    def load(self, content_id: str) -> ContentConfig | None:
        """Load per-video config. Returns None if not configured."""
        ...

    def save(self, content_id: str, config: ContentConfig) -> None:
        """Save per-video config (full replacement)."""
        ...

    def delete(self, content_id: str) -> None:
        """Delete per-video config."""
        ...
