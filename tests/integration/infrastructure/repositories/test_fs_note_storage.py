"""Integration tests for FsNoteStorage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from deeplecture.infrastructure.repositories.fs_note_storage import FsNoteStorage
from deeplecture.infrastructure.repositories.path_resolver import PathResolver


class TestFsNoteStorage:
    """Integration tests for FsNoteStorage."""

    @pytest.fixture
    def path_resolver(self, test_data_dir: Path) -> PathResolver:
        """Create PathResolver with test directories."""
        return PathResolver(
            content_dir=test_data_dir / "content",
            temp_dir=test_data_dir / "temp",
            upload_dir=test_data_dir / "uploads",
        )

    @pytest.fixture
    def storage(self, path_resolver: PathResolver) -> FsNoteStorage:
        """Create FsNoteStorage with test path resolver."""
        return FsNoteStorage(path_resolver)

    @pytest.mark.integration
    def test_save_and_load(self, storage: FsNoteStorage) -> None:
        """save() should persist note that can be loaded."""
        content = "# Lecture Notes\n\nThis is the main content."

        storage.save("test-123", content)
        result = storage.load("test-123")

        assert result is not None
        loaded_content, updated_at = result
        assert loaded_content == content
        assert updated_at is not None

    @pytest.mark.integration
    def test_load_nonexistent(self, storage: FsNoteStorage) -> None:
        """load() should return None for nonexistent note."""
        result = storage.load("nonexistent-id")
        assert result is None

    @pytest.mark.integration
    def test_exists_true(self, storage: FsNoteStorage) -> None:
        """exists() should return True for saved note."""
        storage.save("test-exists", "content")
        assert storage.exists("test-exists") is True

    @pytest.mark.integration
    def test_exists_false(self, storage: FsNoteStorage) -> None:
        """exists() should return False for nonexistent note."""
        assert storage.exists("nonexistent-id") is False

    @pytest.mark.integration
    def test_save_returns_timestamp(self, storage: FsNoteStorage) -> None:
        """save() should return the modification timestamp."""
        result = storage.save("test-ts", "content")
        assert result is not None

    @pytest.mark.integration
    def test_overwrite_existing(self, storage: FsNoteStorage) -> None:
        """save() should overwrite existing note."""
        storage.save("test-overwrite", "original content")
        storage.save("test-overwrite", "new content")

        result = storage.load("test-overwrite")
        assert result is not None
        content, _ = result
        assert content == "new content"

    @pytest.mark.integration
    def test_unicode_content(self, storage: FsNoteStorage) -> None:
        """Storage should handle Unicode content correctly."""
        content = "# 讲座笔记\n\n这是中文内容。\n\n日本語テスト 🎯"

        storage.save("test-unicode", content)
        result = storage.load("test-unicode")

        assert result is not None
        loaded_content, _ = result
        assert loaded_content == content

    @pytest.mark.integration
    def test_path_traversal_protection(self, storage: FsNoteStorage) -> None:
        """Storage should reject path traversal attempts."""
        with pytest.raises(ValueError):
            storage.save("../evil", "malicious content")

    @pytest.mark.integration
    def test_empty_content(self, storage: FsNoteStorage) -> None:
        """Storage should handle empty content."""
        storage.save("test-empty", "")
        result = storage.load("test-empty")

        assert result is not None
        content, _ = result
        assert content == ""

    @pytest.mark.integration
    def test_large_content(self, storage: FsNoteStorage) -> None:
        """Storage should handle large content."""
        large_content = "# Large Note\n\n" + ("Lorem ipsum dolor sit amet. " * 1000)

        storage.save("test-large", large_content)
        result = storage.load("test-large")

        assert result is not None
        loaded_content, _ = result
        assert loaded_content == large_content
