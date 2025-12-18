"""Integration tests for SQLiteMetadataStorage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from deeplecture.domain import ContentMetadata, ContentType
from deeplecture.infrastructure.repositories.sqlite_metadata import SQLiteMetadataStorage


class TestSQLiteMetadataStorage:
    """Integration tests for SQLiteMetadataStorage."""

    @pytest.fixture
    def storage(self, test_data_dir: Path) -> SQLiteMetadataStorage:
        """Create SQLiteMetadataStorage with test database."""
        db_path = test_data_dir / "metadata.db"
        return SQLiteMetadataStorage(db_path)

    @pytest.fixture
    def sample_metadata(self) -> ContentMetadata:
        """Create sample metadata for testing."""
        return ContentMetadata(
            id="test-123",
            type=ContentType.VIDEO,
            original_filename="lecture.mp4",
            source_file="/data/content/test-123/source.mp4",
        )

    @pytest.mark.integration
    def test_save_and_get(self, storage: SQLiteMetadataStorage, sample_metadata: ContentMetadata) -> None:
        """save() should persist metadata that can be retrieved with get()."""
        storage.save(sample_metadata)
        retrieved = storage.get(sample_metadata.id)

        assert retrieved is not None
        assert retrieved.id == sample_metadata.id
        assert retrieved.type == sample_metadata.type
        assert retrieved.original_filename == sample_metadata.original_filename

    @pytest.mark.integration
    def test_get_nonexistent(self, storage: SQLiteMetadataStorage) -> None:
        """get() should return None for nonexistent content."""
        result = storage.get("nonexistent-id")
        assert result is None

    @pytest.mark.integration
    def test_exists_true(self, storage: SQLiteMetadataStorage, sample_metadata: ContentMetadata) -> None:
        """exists() should return True for saved content."""
        storage.save(sample_metadata)
        assert storage.exists(sample_metadata.id) is True

    @pytest.mark.integration
    def test_exists_false(self, storage: SQLiteMetadataStorage) -> None:
        """exists() should return False for nonexistent content."""
        assert storage.exists("nonexistent-id") is False

    @pytest.mark.integration
    def test_delete_existing(self, storage: SQLiteMetadataStorage, sample_metadata: ContentMetadata) -> None:
        """delete() should remove existing content and return True."""
        storage.save(sample_metadata)
        result = storage.delete(sample_metadata.id)

        assert result is True
        assert storage.exists(sample_metadata.id) is False

    @pytest.mark.integration
    def test_delete_nonexistent(self, storage: SQLiteMetadataStorage) -> None:
        """delete() should return False for nonexistent content."""
        result = storage.delete("nonexistent-id")
        assert result is False

    @pytest.mark.integration
    def test_list_all(self, storage: SQLiteMetadataStorage) -> None:
        """list_all() should return all saved metadata."""
        metadata1 = ContentMetadata(
            id="test-1",
            type=ContentType.VIDEO,
            original_filename="lecture1.mp4",
            source_file="/data/1.mp4",
        )
        metadata2 = ContentMetadata(
            id="test-2",
            type=ContentType.SLIDE,
            original_filename="slides.pdf",
            source_file="/data/2.pdf",
        )

        storage.save(metadata1)
        storage.save(metadata2)

        result = storage.list_all()
        ids = [m.id for m in result]

        assert len(result) == 2
        assert "test-1" in ids
        assert "test-2" in ids

    @pytest.mark.integration
    def test_save_upsert(self, storage: SQLiteMetadataStorage, sample_metadata: ContentMetadata) -> None:
        """save() should update existing content (upsert behavior)."""
        storage.save(sample_metadata)

        # Update and save again
        updated = ContentMetadata(
            id=sample_metadata.id,
            type=ContentType.VIDEO,
            original_filename="updated.mp4",
            source_file=sample_metadata.source_file,
        )
        storage.save(updated)

        retrieved = storage.get(sample_metadata.id)
        assert retrieved is not None
        assert retrieved.original_filename == "updated.mp4"

    @pytest.mark.integration
    def test_timestamps_preserved(self, storage: SQLiteMetadataStorage) -> None:
        """Timestamps should be preserved through save/load cycle."""
        now = datetime.now(timezone.utc)
        metadata = ContentMetadata(
            id="test-ts",
            type=ContentType.VIDEO,
            original_filename="test.mp4",
            source_file="/data/test.mp4",
            created_at=now,
            updated_at=now,
        )

        storage.save(metadata)
        retrieved = storage.get("test-ts")

        assert retrieved is not None
        # Compare with tolerance for microseconds
        assert abs((retrieved.created_at - now).total_seconds()) < 1
        assert abs((retrieved.updated_at - now).total_seconds()) < 1
