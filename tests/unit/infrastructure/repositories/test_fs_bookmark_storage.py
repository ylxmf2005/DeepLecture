"""Unit tests for FsBookmarkStorage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deeplecture.infrastructure.repositories.fs_bookmark_storage import FsBookmarkStorage


class FakePathResolver:
    """Minimal path resolver for testing."""

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def build_content_path(self, content_id: str, *parts: str) -> str:
        return str(self._base / content_id / Path(*parts))


def _make_storage(tmp_path: Path) -> FsBookmarkStorage:
    """Create storage with temp directory."""
    return FsBookmarkStorage(FakePathResolver(tmp_path))


# =============================================================================
# Load Tests
# =============================================================================


class TestFsBookmarkStorageLoad:
    """Tests for load_all()."""

    @pytest.mark.unit
    def test_load_returns_none_when_no_file(self, tmp_path: Path) -> None:
        """load_all() returns None when bookmarks file does not exist."""
        storage = _make_storage(tmp_path)
        result = storage.load_all("video-123")
        assert result is None

    @pytest.mark.unit
    def test_load_returns_items(self, tmp_path: Path) -> None:
        """load_all() returns items from existing JSON file."""
        storage = _make_storage(tmp_path)
        bookmarks_dir = tmp_path / "video-123" / "bookmarks"
        bookmarks_dir.mkdir(parents=True)
        data = [{"id": "a", "timestamp": 10.0, "title": "T", "note": ""}]
        (bookmarks_dir / "bookmarks.json").write_text(json.dumps(data))

        result = storage.load_all("video-123")
        assert result is not None
        items, updated_at = result
        assert len(items) == 1
        assert items[0]["id"] == "a"
        assert updated_at is not None

    @pytest.mark.unit
    def test_load_handles_corrupted_json(self, tmp_path: Path) -> None:
        """load_all() returns empty list on corrupted JSON."""
        storage = _make_storage(tmp_path)
        bookmarks_dir = tmp_path / "video-123" / "bookmarks"
        bookmarks_dir.mkdir(parents=True)
        (bookmarks_dir / "bookmarks.json").write_text("{invalid json")

        result = storage.load_all("video-123")
        assert result is not None
        items, _updated_at = result
        assert items == []


# =============================================================================
# Save Tests
# =============================================================================


class TestFsBookmarkStorageSave:
    """Tests for save_all()."""

    @pytest.mark.unit
    def test_save_creates_file(self, tmp_path: Path) -> None:
        """save_all() creates the bookmarks file."""
        storage = _make_storage(tmp_path)
        items = [{"id": "b", "timestamp": 20.0, "title": "Bookmark", "note": ""}]

        updated_at = storage.save_all("video-123", items)
        assert updated_at is not None

        # Verify file was written
        file_path = tmp_path / "video-123" / "bookmarks" / "bookmarks.json"
        assert file_path.exists()
        loaded = json.loads(file_path.read_text())
        assert len(loaded) == 1
        assert loaded[0]["id"] == "b"

    @pytest.mark.unit
    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """save_all() atomically replaces existing content."""
        storage = _make_storage(tmp_path)

        # First save
        storage.save_all("video-123", [{"id": "first"}])
        # Second save with different data
        storage.save_all("video-123", [{"id": "second"}, {"id": "third"}])

        file_path = tmp_path / "video-123" / "bookmarks" / "bookmarks.json"
        loaded = json.loads(file_path.read_text())
        assert len(loaded) == 2
        assert loaded[0]["id"] == "second"

    @pytest.mark.unit
    def test_save_empty_list(self, tmp_path: Path) -> None:
        """save_all() handles empty list correctly."""
        storage = _make_storage(tmp_path)
        storage.save_all("video-123", [])

        file_path = tmp_path / "video-123" / "bookmarks" / "bookmarks.json"
        loaded = json.loads(file_path.read_text())
        assert loaded == []
