"""Test paper storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class TestPaperStorageProtocol(Protocol):
    """Test paper persistence contract."""

    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None:
        """Load test paper data from storage."""
        ...

    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime:
        """Save test paper data to storage."""
        ...

    def exists(self, content_id: str, language: str | None = None) -> bool:
        """Check if test paper exists."""
        ...
