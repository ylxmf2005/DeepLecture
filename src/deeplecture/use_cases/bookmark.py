"""Bookmark management use case."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from deeplecture.domain.errors import BookmarkNotFoundError, ContentNotFoundError
from deeplecture.use_cases.dto.bookmark import (
    BookmarkItem,
    BookmarkListResult,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.bookmark import CreateBookmarkRequest, UpdateBookmarkRequest
    from deeplecture.use_cases.interfaces import (
        BookmarkStorageProtocol,
        MetadataStorageProtocol,
    )

UTC = timezone.utc


class BookmarkUseCase:
    """
    Bookmark management (CRUD).

    Provides:
    - List bookmarks (sorted by timestamp)
    - Create bookmark at a video timestamp
    - Update bookmark title/note/timestamp
    - Delete bookmark
    """

    def __init__(
        self,
        *,
        bookmark_storage: BookmarkStorageProtocol,
        metadata_storage: MetadataStorageProtocol,
    ) -> None:
        self._bookmarks = bookmark_storage
        self._metadata = metadata_storage

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def list_bookmarks(self, content_id: str) -> BookmarkListResult:
        """
        List all bookmarks for a content item, sorted by timestamp.

        Args:
            content_id: Content identifier

        Returns:
            BookmarkListResult with sorted items
        """
        result = self._bookmarks.load_all(content_id)
        if not result:
            return BookmarkListResult(content_id=content_id, bookmarks=[])

        raw_items, _updated_at = result
        items = [BookmarkItem.from_dict(d) for d in raw_items]
        items.sort(key=lambda b: b.timestamp)

        return BookmarkListResult(content_id=content_id, bookmarks=items)

    def create_bookmark(self, request: CreateBookmarkRequest) -> BookmarkItem:
        """
        Create a new bookmark.

        Args:
            request: Creation request with content_id, timestamp, title, note

        Returns:
            The created BookmarkItem

        Raises:
            ContentNotFoundError: Content not found
        """
        self._ensure_content_exists(request.content_id)

        now = datetime.now(UTC)
        item = BookmarkItem(
            id=str(uuid.uuid4()),
            timestamp=request.timestamp,
            title=request.title,
            note=request.note,
            created_at=now,
            updated_at=now,
        )

        # Load existing, append, save
        items = self._load_items(request.content_id)
        items.append(item)
        self._save_items(request.content_id, items)

        return item

    def update_bookmark(self, request: UpdateBookmarkRequest) -> BookmarkItem:
        """
        Update an existing bookmark.

        Args:
            request: Update request with content_id, bookmark_id, and optional fields

        Returns:
            The updated BookmarkItem

        Raises:
            BookmarkNotFoundError: Bookmark ID not found
        """
        items = self._load_items(request.content_id)
        target = self._find_by_id(items, request.bookmark_id)

        if request.title is not None:
            target.title = request.title
        if request.note is not None:
            target.note = request.note
        if request.timestamp is not None:
            target.timestamp = request.timestamp

        target.updated_at = datetime.now(UTC)

        self._save_items(request.content_id, items)
        return target

    def delete_bookmark(self, content_id: str, bookmark_id: str) -> None:
        """
        Delete a bookmark.

        Args:
            content_id: Content identifier
            bookmark_id: Bookmark UUID to delete

        Raises:
            BookmarkNotFoundError: Bookmark ID not found
        """
        items = self._load_items(content_id)
        original_len = len(items)
        items = [b for b in items if b.id != bookmark_id]

        if len(items) == original_len:
            raise BookmarkNotFoundError(bookmark_id)

        self._save_items(content_id, items)

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _ensure_content_exists(self, content_id: str) -> None:
        """Verify content exists in metadata storage."""
        if self._metadata.get(content_id) is None:
            raise ContentNotFoundError(content_id)

    def _load_items(self, content_id: str) -> list[BookmarkItem]:
        """Load bookmark items from storage."""
        result = self._bookmarks.load_all(content_id)
        if not result:
            return []
        raw_items, _updated_at = result
        return [BookmarkItem.from_dict(d) for d in raw_items]

    def _save_items(self, content_id: str, items: list[BookmarkItem]) -> None:
        """Save bookmark items to storage."""
        self._bookmarks.save_all(content_id, [b.to_dict() for b in items])

    @staticmethod
    def _find_by_id(items: list[BookmarkItem], bookmark_id: str) -> BookmarkItem:
        """Find a bookmark by ID or raise."""
        for item in items:
            if item.id == bookmark_id:
                return item
        raise BookmarkNotFoundError(bookmark_id)
