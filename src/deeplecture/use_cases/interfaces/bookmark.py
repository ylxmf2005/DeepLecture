"""Bookmark storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class BookmarkStorageProtocol(Protocol):
    """
    Contract for bookmark storage.

    Implementations: FsBookmarkStorage (in repository layer)
    """

    def load_all(self, content_id: str) -> tuple[list[dict[str, Any]], datetime | None] | None:
        """
        Load all bookmarks for a content item.

        Args:
            content_id: Content identifier

        Returns:
            (items, updated_at) if file exists, None otherwise.
            Items are dicts sorted by timestamp ascending.
        """
        ...

    def save_all(self, content_id: str, items: list[dict[str, Any]]) -> datetime:
        """
        Save all bookmarks atomically.

        Args:
            content_id: Content identifier
            items: List of bookmark dicts to save

        Returns:
            Modification timestamp
        """
        ...
