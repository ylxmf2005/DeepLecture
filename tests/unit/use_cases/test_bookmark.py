"""Unit tests for BookmarkUseCase."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.use_cases.bookmark import BookmarkNotFoundError, BookmarkUseCase
from deeplecture.use_cases.dto.bookmark import (
    BookmarkItem,
    CreateBookmarkRequest,
    UpdateBookmarkRequest,
)

UTC = timezone.utc
NOW = datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC)


def _make_storage(items: list[dict] | None = None) -> MagicMock:
    """Create a mock bookmark storage."""
    storage = MagicMock()
    if items is None:
        storage.load_all.return_value = None
    else:
        storage.load_all.return_value = (items, NOW)
    storage.save_all.return_value = NOW
    return storage


def _make_metadata(exists: bool = True) -> MagicMock:
    """Create a mock metadata storage."""
    meta = MagicMock()
    if exists:
        meta.get.return_value = MagicMock(type="video")
    else:
        meta.get.return_value = None
    return meta


def _make_usecase(
    items: list[dict] | None = None,
    content_exists: bool = True,
) -> tuple[BookmarkUseCase, MagicMock]:
    """Create a BookmarkUseCase with mocked dependencies."""
    storage = _make_storage(items)
    metadata = _make_metadata(content_exists)
    uc = BookmarkUseCase(bookmark_storage=storage, metadata_storage=metadata)
    return uc, storage


def _sample_bookmark_dict(
    *,
    id: str = "aaaa-bbbb",
    timestamp: float = 120.5,
    title: str = "Test Bookmark",
    note: str = "Some note",
) -> dict:
    return {
        "id": id,
        "timestamp": timestamp,
        "title": title,
        "note": note,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }


# =============================================================================
# List Tests
# =============================================================================


class TestListBookmarks:
    """Tests for list_bookmarks()."""

    @pytest.mark.unit
    def test_empty_when_no_file(self) -> None:
        """list_bookmarks() returns empty list when no file exists."""
        uc, _storage = _make_usecase(items=None)
        result = uc.list_bookmarks("video-123")
        assert result.content_id == "video-123"
        assert result.bookmarks == []

    @pytest.mark.unit
    def test_empty_list(self) -> None:
        """list_bookmarks() returns empty list for empty file."""
        uc, _storage = _make_usecase(items=[])
        result = uc.list_bookmarks("video-123")
        assert result.bookmarks == []

    @pytest.mark.unit
    def test_returns_sorted_by_timestamp(self) -> None:
        """list_bookmarks() sorts items by timestamp ascending."""
        items = [
            _sample_bookmark_dict(id="b", timestamp=300.0),
            _sample_bookmark_dict(id="a", timestamp=100.0),
            _sample_bookmark_dict(id="c", timestamp=200.0),
        ]
        uc, _storage = _make_usecase(items=items)
        result = uc.list_bookmarks("video-123")
        timestamps = [b.timestamp for b in result.bookmarks]
        assert timestamps == [100.0, 200.0, 300.0]


# =============================================================================
# Create Tests
# =============================================================================


class TestCreateBookmark:
    """Tests for create_bookmark()."""

    @pytest.mark.unit
    def test_create_appends_and_saves(self) -> None:
        """create_bookmark() appends to existing list and saves."""
        existing = [_sample_bookmark_dict(id="existing")]
        uc, storage = _make_usecase(items=existing)

        req = CreateBookmarkRequest(
            content_id="video-123",
            timestamp=60.0,
            title="My Bookmark",
            note="Important section",
        )
        result = uc.create_bookmark(req)

        assert result.timestamp == 60.0
        assert result.title == "My Bookmark"
        assert result.note == "Important section"
        assert result.id  # UUID generated

        # Verify save was called with 2 items
        storage.save_all.assert_called_once()
        saved_items = storage.save_all.call_args[0][1]
        assert len(saved_items) == 2

    @pytest.mark.unit
    def test_create_on_empty_storage(self) -> None:
        """create_bookmark() works when no bookmarks file exists yet."""
        uc, storage = _make_usecase(items=None)

        req = CreateBookmarkRequest(
            content_id="video-123",
            timestamp=30.0,
            title="First Bookmark",
        )
        result = uc.create_bookmark(req)

        assert result.title == "First Bookmark"
        storage.save_all.assert_called_once()
        saved_items = storage.save_all.call_args[0][1]
        assert len(saved_items) == 1

    @pytest.mark.unit
    def test_create_raises_content_not_found(self) -> None:
        """create_bookmark() raises ContentNotFoundError for invalid content."""
        uc, _storage = _make_usecase(content_exists=False)

        req = CreateBookmarkRequest(content_id="nonexistent", timestamp=10.0)
        with pytest.raises(Exception, match="nonexistent"):
            uc.create_bookmark(req)


# =============================================================================
# Update Tests
# =============================================================================


class TestUpdateBookmark:
    """Tests for update_bookmark()."""

    @pytest.mark.unit
    def test_update_title_only(self) -> None:
        """update_bookmark() updates only the specified fields."""
        items = [_sample_bookmark_dict(id="target-id", title="Old Title")]
        uc, storage = _make_usecase(items=items)

        req = UpdateBookmarkRequest(
            content_id="video-123",
            bookmark_id="target-id",
            title="New Title",
        )
        result = uc.update_bookmark(req)

        assert result.title == "New Title"
        assert result.note == "Some note"  # Unchanged
        storage.save_all.assert_called_once()

    @pytest.mark.unit
    def test_update_note(self) -> None:
        """update_bookmark() can update note field."""
        items = [_sample_bookmark_dict(id="target-id")]
        uc, _storage = _make_usecase(items=items)

        req = UpdateBookmarkRequest(
            content_id="video-123",
            bookmark_id="target-id",
            note="Updated note content",
        )
        result = uc.update_bookmark(req)
        assert result.note == "Updated note content"

    @pytest.mark.unit
    def test_update_timestamp(self) -> None:
        """update_bookmark() can update timestamp."""
        items = [_sample_bookmark_dict(id="target-id", timestamp=100.0)]
        uc, _storage = _make_usecase(items=items)

        req = UpdateBookmarkRequest(
            content_id="video-123",
            bookmark_id="target-id",
            timestamp=200.0,
        )
        result = uc.update_bookmark(req)
        assert result.timestamp == 200.0

    @pytest.mark.unit
    def test_update_not_found(self) -> None:
        """update_bookmark() raises BookmarkNotFoundError for missing ID."""
        items = [_sample_bookmark_dict(id="other-id")]
        uc, _storage = _make_usecase(items=items)

        req = UpdateBookmarkRequest(
            content_id="video-123",
            bookmark_id="nonexistent-id",
            title="X",
        )
        with pytest.raises(BookmarkNotFoundError):
            uc.update_bookmark(req)


# =============================================================================
# Delete Tests
# =============================================================================


class TestDeleteBookmark:
    """Tests for delete_bookmark()."""

    @pytest.mark.unit
    def test_delete_removes_item(self) -> None:
        """delete_bookmark() removes the item and saves."""
        items = [
            _sample_bookmark_dict(id="keep"),
            _sample_bookmark_dict(id="delete-me"),
        ]
        uc, storage = _make_usecase(items=items)

        uc.delete_bookmark("video-123", "delete-me")

        storage.save_all.assert_called_once()
        saved_items = storage.save_all.call_args[0][1]
        assert len(saved_items) == 1
        assert saved_items[0]["id"] == "keep"

    @pytest.mark.unit
    def test_delete_not_found(self) -> None:
        """delete_bookmark() raises BookmarkNotFoundError for missing ID."""
        items = [_sample_bookmark_dict(id="existing")]
        uc, _storage = _make_usecase(items=items)

        with pytest.raises(BookmarkNotFoundError):
            uc.delete_bookmark("video-123", "nonexistent")


# =============================================================================
# DTO Tests
# =============================================================================


class TestBookmarkItem:
    """Tests for BookmarkItem dataclass."""

    @pytest.mark.unit
    def test_to_dict_roundtrip(self) -> None:
        """BookmarkItem.to_dict() and from_dict() are symmetric."""
        item = BookmarkItem(
            id="test-id",
            timestamp=42.5,
            title="Test",
            note="Note",
            created_at=NOW,
            updated_at=NOW,
        )
        d = item.to_dict()
        restored = BookmarkItem.from_dict(d)

        assert restored.id == item.id
        assert restored.timestamp == item.timestamp
        assert restored.title == item.title
        assert restored.note == item.note

    @pytest.mark.unit
    def test_from_dict_defaults(self) -> None:
        """BookmarkItem.from_dict() handles missing fields gracefully."""
        item = BookmarkItem.from_dict({})
        assert item.id == ""
        assert item.timestamp == 0.0
        assert item.title == ""
        assert item.note == ""
